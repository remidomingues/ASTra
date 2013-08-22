#!/usr/bin/env python

"""
@file	Vehicle.py
@author  Remi Domingues
@date	07/06/2013

This script reads an input socket connected to the remote client and process an request when received
		
(1) Add request: ADD vehicleId priority lat1 lon1 lat2 lon2 ... latN lonN
		priority = 0 (no priority) or 1 (priority vehicle)
	Followed by (2) Acknowledge response: ACK vehicleId ackCode (See Constants for the detailed acknowledge codes)

(3) Delete request: DEL vehicleId1 vehicleId2 ... vehicleId3
		If NO VEHICLE is specified, every vehicle will be deleted
		Followed by (12)

(4) Stress test request: MOC prefixId vehiclesNumber routeLength
	Followed by (12)

(5) Get vehicles speed request: SPE vehicleId1 vehicleId2 ... vehicleIdN
		If NO VEHICLE is specified, the response will contain every vehicle speed
		Followed by (6): SPE vehicleId1 speed1 vehicleId2 speed2 ... vehicleIdN speedN 

(7) Get vehicles geographic coordinates request: COO vehicleId1 vehicleId2 ... vehicleId3
		If NO VEHICLE is specified, the response will contain every vehicle geographic coordinates
		Followed by (8): COO vehicleId1 lon1 lat1 vehicleId2 lon2 lat2 ... vehicleIdN lonN latN

(9) Get arrived vehicles ID: ARR
		Followed by (10): ARR vehicleId1 ... vehicleIdN
        
(11) ERROR response when an invalid request is received : ERR 40

(12) Acknowledge response (14) : ACK returnCode
"""

import os, sys
import optparse
import subprocess
import socket
import time
import Constants
import traci
import traceback
from random import randint
from SharedFunctions import isJunction
from SharedFunctions import getFirstLaneFromEdge
from SharedFunctions import getEdgeFromLane
from SharedFunctions import sendAck
from Logger import Logger

""" Returns a route ID from a user vehicle ID """
def getRouteIdFromVehicleId(vehicleId, cRouteId):
	return (vehicleId + str(cRouteId)).encode()


""" Appends edgesNumber random following edges to the route given in parameter """
def appendEdge(route, edgesNumber, mtraci):
	for i in range(0, edgesNumber):
		edge = route[len(route) - 1]
		lane = edge + "_0"
		
		mtraci.acquire()
		links = traci.lane.getLinks(lane)
		mtraci.release()
		
		if len(links) == 0:
			return -1
		
		nextEdge = links[randint(0, len(links) - 1)][0].split('_')[0]
		route.append(nextEdge)
		
	return route


""" Sends an acknowledge(2) message to the remote client using an output socket """
def sendIdentifiedAck(vehicleId, errorCode, outputSocket):
	errorMsg = []
	errorMsg.append(Constants.ACK_HEADER)
	errorMsg.append(Constants.SEPARATOR)
	errorMsg.append(vehicleId)
	errorMsg.append(Constants.SEPARATOR)
	errorMsg.append(errorCode)
	errorMsg.append(Constants.END_OF_MESSAGE)
		
	strmsg = ''.join(errorMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise Constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(Constants.PRINT_PREFIX_VEHICLE, strmsg))


""" Returns a route (list of edges ID) from a ADD(1) command """
def getRouteFromCommand(command, commandSize):
	index = 3
	route = []
	
	while index < commandSize - 1:
		route.append(command[index])
		index += 1
		
	return route


""" Return true if the given route is linked by SUMO lanes, false else """
def isRouteValidForTraCI(mtraci, route):
	for i in range(0, len(route) - 1):
		inEdge = route[i]
		outEdge = route[i + 1]
		inLaneIndex = 0
		inLane = getFirstLaneFromEdge(inEdge)
		found = False
		
		while not found:
			try:
				mtraci.acquire()
				lanesOut = traci.lane.getLinks(inLane)
				mtraci.release()
			except:
				mtraci.release()
				return False
			
			laneOutIndex = 0
			
			while laneOutIndex < len(lanesOut) and not found:
				outLane = lanesOut[laneOutIndex][0]
				if getEdgeFromLane(outLane) == outEdge:
					found = True
				else:
					laneOutIndex += 1
			
			if not found:
				inLaneIndex += 1
				inLane = inLane[:len(inLane) - 1] + str(inLaneIndex)
				
	return True


""" Return true if each edge contained by the route given is linked with the previous and next edge of the route """
def isRouteValid(route, junctionsDict, edgesDict):
	for i in range(0, len(route) - 1):
		edge = route[i]
		edgeSucc = route[i + 1]
		nextJunction = edgesDict[edge][1]
		if not edgeSucc in junctionsDict[nextJunction][1] or not edge in junctionsDict[nextJunction][0]:
			return False
	return True
	

""" Adds a vehicle and its route to the SUMO simulation. An error may be sent to the remote client """
def addRouteToSumo(vehicleId, routeId, route, mtraci, outputSocket):
	if not isRouteValidForTraCI(mtraci, route):
		Logger.warning("{}Invalid route detected: {}".format(Constants.PRINT_PREFIX_VEHICLE, route))
		sendIdentifiedAck(vehicleId, Constants.VEHICLE_INVALID_ROUTE, outputSocket)
		return -1
	
	try:
		mtraci.acquire()
		traci.route.add(routeId, route)
		traci.vehicle.add(vehicleId, routeId, -2, 0, 0, 0, Constants.DEFAULT_VEHICLE_TYPE)
		if not(traci.vehicle.isRouteValid(vehicleId)):
			Logger.error("{}IMMINENT FAILURE: vehicle {} must be removed: invalid route returned by TraCI: {}".format(Constants.PRINT_PREFIX_VEHICLE, vehicleId, route))
			traci.vehicle.remove(vehicleId)
			mtraci.release()
			sendIdentifiedAck(vehicleId, Constants.VEHICLE_INVALID_ROUTE, outputSocket)
			return -1
		else:
			mtraci.release()
			
	except:
		mtraci.release()
		Logger.error("{}Vehicle {} or its route cannot be added to SUMO Simulation".format(Constants.PRINT_PREFIX_VEHICLE, vehicleId))
		raise
		
	return 0
	
	
""" If the vehicle received is priority, this one is append in the priority vehicles shared list protected by a mutex """
def savePriorityVehicles(mtraci, vehicleId, priority, priorityVehicles, mPriorityVehicles):
	if priority == Constants.PRIORITY_VEHICLE:
		mPriorityVehicles.acquire()
		priorityVehicles.append(vehicleId)
		mPriorityVehicles.release()
	
"""
- Transforms the coordinates to SUMO edges ID
- Adds a vehicle and its route to the SUMO simulation
- Saves this one as a priority vehicle if he is priority
"""
def addVehicle(command, commandSize, mtraci, cRouteId, outputSocket, priorityVehicles, mPriorityVehicles):
	vehicleId = command[1]
	priority = command[2]
	routeId = getRouteIdFromVehicleId(vehicleId, cRouteId)
	route = getRouteFromCommand(command, commandSize)
	if not route:
		return sendIdentifiedAck(vehicleId, Constants.VEHICLE_EMPTY_ROUTE, outputSocket)
	returnCode = addRouteToSumo(vehicleId, routeId, route, mtraci, outputSocket)
	if returnCode == 0:
		savePriorityVehicles(mtraci, vehicleId, priority, priorityVehicles, mPriorityVehicles)
	sendIdentifiedAck(vehicleId, Constants.ACK_OK, outputSocket)	
	

""" Removes the specified vehicles from the simulation """
def removeVehicles(vehicles, priorityVehicles, mPriorityVehicles, mtraci, outputSocket):
	returnCode = Constants.ACK_OK
	
	for vehicle in vehicles:
		mPriorityVehicles.acquire()
		if vehicleId in priorityVehicles:
			priorityVehicles.remove(vehicleId)
		mPriorityVehicles.release()
		
		try:
			mtraci.acquire()
			traci.vehicle.remove(vehicleId)
		except:
			returnCode = Constants.GRAPH_UNKNOWN_EDGE
		mtraci.release()
	
	sendAck(Constants.PRINT_PREFIX_VEHICLE, returnCode, outputSocket)
	

""" Adds vehiclesNumber vehicles to SUMO, linking each of these to a random route of routeSize edges """
def addRandomVehicles(vehicleIdPrefix, vehiclesNumber, routeSize, mtraci):
	Logger.info("{}Adding {} vehicles to the simulation...".format(Constants.PRINT_PREFIX_VEHICLE, vehiclesNumber))
	i = 0
	route = []
	mtraci.acquire()
	edges = traci.edge.getIDList()
	mtraci.release()
	edgesNumber = len(edges)
	
	while i < vehiclesNumber:
		vehicleId = vehicleIdPrefix + str(i)
		routeId = getRouteIdFromVehicleId(vehicleIdPrefix, i)
		
		#Building random route
		edgeSrc = edges[randint(0, edgesNumber)]
		route.append(edgeSrc)
		route = appendEdge(route, routeSize, mtraci)
		
		if route != -1:
			#Adding route and vehicle to SUMO
			mtraci.acquire()
			traci.route.add(routeId, route)
			traci.vehicle.add(vehicleId,routeId,-2,0,0,0,"DEFAULT_VEHTYPE")
			mtraci.release()
			route[:] = []
			i += 1
		else:
			route = []
			
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_VEHICLE))
	sendAck(Constants.PRINT_PREFIX_VEHICLE, returnCode, outputSocket)
	

""" Send the speed of the given vehicles to the distant client """
def sendVehiclesSpeed(vehiclesId, outputSocket, mtraci):
	speedMsg = []
	speedMsg.append(Constants.VEHICLE_SPEED_RESPONSE_HEADER)
		
	for vehicleId in vehiclesId:
		mtraci.acquire()
		speed = traci.vehicle.getSpeed(vehicleId)
		mtraci.release()
		
		speedMsg.append(Constants.SEPARATOR)
		speedMsg.append(vehicleId)
		speedMsg.append(Constants.SEPARATOR)
		speedMsg.append(str(speed))
		
	speedMsg.append(Constants.END_OF_MESSAGE)
		
	strmsg = ''.join(speedMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise Constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(Constants.PRINT_PREFIX_VEHICLE, strmsg))
	
	
""" Return a vehicle list without the cologne vehicles """
def getRegularVehicles(vehicles):
	regularVehicles = []
	for vehicle in vehicles:
		if not Constants.IGNORED_VEHICLES_REGEXP.match(vehicle) and not vehicle.startswith(Constants.BLOCKED_VEHICLE_ID_PREFIX):
			regularVehicles.append(vehicle)
	return regularVehicles
	

""" Gets every vehicles position from SUMO and send then these ones to the remote client by an output socket """
def sendVehiclesCoordinates(vehiclesId, mtraci, outputSocket):
		#If the simulated vehicles number we have to take into account is not 0
		vehiclesPos = []
		vehiclesPos.append(Constants.VEHICLE_COORDS_RESPONSE_HEADER)
		
		for vehicleId in vehiclesId:
			mtraci.acquire()
			coords = traci.vehicle.getPosition(vehicleId)
			coordsGeo = traci.simulation.convertGeo(coords[0], coords[1], False)
			mtraci.release()

			#Build the message to send by the output socket
			vehiclesPos.append(Constants.SEPARATOR)
			vehiclesPos.append(vehicleId)
			vehiclesPos.append(Constants.SEPARATOR)
			vehiclesPos.append(str(coordsGeo[0]))
			vehiclesPos.append(Constants.SEPARATOR)
			vehiclesPos.append(str(coordsGeo[1]))
		
		#Send the position of each vehicle by the output socket
		vehiclesPos.append(Constants.END_OF_MESSAGE)
		strmsg = ''.join(vehiclesPos)
		
		try:
			outputSocket.send(strmsg.encode())
		except:
			raise Constants.ClosedSocketException("The listening socket has been closed")
	

""" Gets all arrived vehicles ID from SUMO and send them to the remote client by output socket """
def sendArrivedVehicles(arrivedVehicles, mtraci, outputSocket):
	msgArrivedVehicles = []
	msgArrivedVehicles.append(Constants.VEHICLE_ARRIVED_RESPONSE_HEADER)
	
	for vehicleId in arrivedVehicles:				
		msgArrivedVehicles.append(Constants.SEPARATOR)
		msgArrivedVehicles.append(vehicleId)	

	msgArrivedVehicles.append(Constants.END_OF_MESSAGE)
	strmsg = ''.join(msgArrivedVehicles)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise Constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(Constants.PRINT_PREFIX_SIMULATOR, strmsg))
	

""" Reads an input socket connected to the remote client and process an add(1), delete(3) or stress(4) request when received """
def run(mtraci, inputSocket, outputSocket, eShutdown, priorityVehicles, mPriorityVehicles, eVehicleReady, eManagerReady):
	bufferSize = 32768
	cRouteId = 0
	
	eVehicleReady.set()
	while not eManagerReady.is_set():
		time.sleep(Constants.SLEEP_SYNCHRONISATION)
	
	while not eShutdown.is_set():
		try:
			try:
				# Read the message from the input socket (blocked until a message is read)
				buff = inputSocket.recv(bufferSize)
			except:
				raise Constants.ClosedSocketException("The listening socket has been closed")
			
			if len(buff) == 0:
					raise Constants.ClosedSocketException("The distant socket has been closed")
				
			listCommands = buff.decode().split(Constants.MESSAGES_SEPARATOR)
			
			for cmd in listCommands:
				if len(cmd) != 0:
					command = cmd.split(Constants.SEPARATOR)
					commandSize = len(command)
					
					for i in range(0, commandSize):
						command[i] = str(command[i])
						
					Logger.infoFile("{} Message received: {}".format(Constants.PRINT_PREFIX_VEHICLE, cmd))
					
					# Add the user ID and the route to the map
					if commandSize > 2 and command[0] == Constants.VEHICLE_ADD_REQUEST_HEADER:
						try:
							addVehicle(command, commandSize, mtraci, cRouteId, outputSocket, priorityVehicles, mPriorityVehicles)
						except Exception as e:
							sendIdentifiedAck(command[1], Constants.VEHICLE_INVALID_ROUTE, outputSocket)
							raise
						cRouteId += 1
						
						
					#Remove the specified vehicles from the simulation
					elif commandSize > 1 and command[0] == Constants.VEHICLE_DELETE_REQUEST_HEADER:
						if commandSize == 1:
							mtraci.acquire()
							vehicles = traci.vehicle.getIDList()
							mtraci.release()
							vehicles = getRegularVehicles(vehicles)
							removeVehicles(vehicles, priorityVehicles, mPriorityVehicles, mtraci, outputSocket)
						else:
							command.pop(0)
							removeVehicles(command, priorityVehicles, mPriorityVehicles, mtraci, outputSocket)
						
						
					#Stress test, add random vehicles to the simulation
					elif commandSize == 4 and command[0] == Constants.VEHICLE_ADD_RAND_REQUEST_HEADER:
						try:
							addRandomVehicles(command[1], int(command[2]), int(command[3]), mtraci, outputSocket)
						except:
							sendAck(Constants.PRINT_PREFIX_VEHICLE, Constants.VEHICLE_MOCK_FAILED, outputSocket)
						
						
					#Send vehicles speed to the remote client
					elif commandSize > 1 and command[0] == Constants.VEHICLE_SPEED_REQUEST_HEADER:
						if commandSize == 1:
							mtraci.acquire()
							vehicles = traci.vehicle.getIDList()
							mtraci.release()
							vehicles = getRegularVehicles(vehicles)
							sendVehiclesSpeed(vehicles, outputSocket, mtraci)
						else:
							command.pop(0)
							sendVehiclesSpeed(command, outputSocket, mtraci)
						
						
					#Send vehicles geographic coordinates to the remote client
					elif commandSize >= 1 and command[0] == Constants.VEHICLE_COORDS_REQUEST_HEADER:
						if commandSize == 1:
							mtraci.acquire()
							vehicles = traci.vehicle.getIDList()
							mtraci.release()
							vehicles = getRegularVehicles(vehicles)
							sendVehiclesCoordinates(vehicles, outputSocket, mtraci)
						else:
							command.pop(0)
							sendVehiclesCoordinates(command, outputSocket, mtraci)
						
						
					#Send arrived vehicles ID to the remote client
					elif commandSize == 1 and command[0] == Constants.VEHICLE_ARRIVED_REQUEST_HEADER:
						mtraci.acquire()
						arrivedVehicles = traci.simulation.getArrivedIDList()
						mtraci.release()
						arrivedVehicles = getRegularVehicles(arrivedVehicles)
						sendArrivedVehicles(vehicles, outputSocket, mtraci)
						
						
					# Error
					else:
						Logger.warning("{}Invalid command received: {}".format(Constants.PRINT_PREFIX_VEHICLE, command))
						sendAck(Constants.PRINT_PREFIX_VEHICLE, Constants.INVALID_MESSAGE, outputSocket)

		except Exception as e:
			if e.__class__.__name__ == Constants.CLOSED_SOCKET_EXCEPTION or e.__class__.__name__ == Constants.TRACI_EXCEPTION:
				Logger.info("{}Shutting down current thread".format(Constants.PRINT_PREFIX_VEHICLE))
				sys.exit()
			else:
				Logger.error("{}A {} exception occurred:".format(Constants.PRINT_PREFIX_VEHICLE, e.__class__.__name__))
				Logger.exception(e)
