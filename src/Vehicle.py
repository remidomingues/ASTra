#!/usr/bin/env python

"""
@file	vehicle.py
@author  Remi Domingues
@date	07/06/2013

This script reads an input socket connected to the remote client and process an request when received
		
(1) Add request: ADD vehicleId priority lat1 lon1 lat2 lon2 ... latN lonN
		priority = 0 (no priority) or 1 (priority vehicle)
	Followed by (2) Acknowledge response: ACK vehicleId ackCode (See constants for the detailed acknowledge codes)

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
import constants
import traci
import traceback
from random import randint
from sharedFunctions import isJunction
from sharedFunctions import getFirstLaneFromEdge
from sharedFunctions import getEdgeFromLane
from sharedFunctions import sendAck
from logger import Logger

def getRouteIdFromVehicleId(vehicleId, cRouteId):
	"""
	Returns a route ID from a user vehicle ID
	"""
	return (vehicleId + str(cRouteId)).encode()


def appendEdge(route, edgesNumber, mtraci):
	"""
	Appends edgesNumber random following edges to the route given in parameter
	"""
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


def sendIdentifiedAck(vehicleId, errorCode, outputSocket):
	"""
	Sends an acknowledge(2) message to the remote client using an output socket
	"""
	errorMsg = []
	errorMsg.append(constants.ACKNOWLEDGE_HEADER)
	errorMsg.append(constants.SEPARATOR)
	errorMsg.append(vehicleId)
	errorMsg.append(constants.SEPARATOR)
	errorMsg.append(str(errorCode))
	errorMsg.append(constants.END_OF_MESSAGE)
		
	strmsg = ''.join(errorMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_VEHICLE, strmsg))


def isRouteValidForTraCI(mtraci, route):
	"""
	Returns true if the given route is linked by SUMO lanes, false else
	"""
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


def isRouteValid(route, junctionsDict, edgesDict):
	"""
	Return true if each edge contained by the route given is linked with the previous and next edge of the route
	"""
	for i in range(0, len(route) - 1):
		edge = route[i]
		edgeSucc = route[i + 1]
		nextJunction = edgesDict[edge][1]
		if not edgeSucc in junctionsDict[nextJunction][1] or not edge in junctionsDict[nextJunction][0]:
			return False
	return True
	

def addRouteToSumo(vehicleId, routeId, route, mtraci, outputSocket):
	"""
	Adds a vehicle and its route to the SUMO simulation. An error may be sent to the remote client
	"""
	if not isRouteValidForTraCI(mtraci, route):
		Logger.warning("{}Invalid route detected: {}".format(constants.PRINT_PREFIX_VEHICLE, route))
		return constants.VEHICLE_INVALID_ROUTE
	
	try:
		mtraci.acquire()
		traci.route.add(routeId, route)
		traci.vehicle.add(vehicleId, routeId, -2, 0, 0, 0, constants.DEFAULT_VEHICLE_TYPE)
		if not(traci.vehicle.isRouteValid(vehicleId)):
			Logger.error("{}IMMINENT FAILURE: vehicle {} must be removed: invalid route returned by TraCI: {}".format(constants.PRINT_PREFIX_VEHICLE, vehicleId, route))
			traci.vehicle.remove(vehicleId)
			mtraci.release()
			return constants.VEHICLE_INVALID_ROUTE
		else:
			mtraci.release()
			
	except:
		mtraci.release()
		Logger.error("{}Vehicle {} or its route cannot be added to SUMO Simulation".format(constants.PRINT_PREFIX_VEHICLE, vehicleId))
		raise
		
	return constants.ACK_OK
	
	
def savePriorityVehicles(mtraci, vehicleId, priority, priorityVehicles, mPriorityVehicles):
	"""
	If the vehicle received is priority, this one is append in the priority vehicles shared list protected by a mutex
	"""
	if priority == constants.PRIORITY_VEHICLE:
		mPriorityVehicles.acquire()
		priorityVehicles.append(vehicleId)
		mPriorityVehicles.release()
	
	
def addVehicle(vehicleId, priority, route, mtraci, cRouteId, outputSocket, priorityVehicles, mPriorityVehicles, vehicles, mVehicles):
	"""
	- Transforms the coordinates to SUMO edges ID
	- Adds a vehicle and its route to the SUMO simulation
	- Saves this one as a priority vehicle if he is priority
	"""
	if not route:
		return sendIdentifiedAck(vehicleId, constants.VEHICLE_EMPTY_ROUTE, outputSocket)
	
	routeId = getRouteIdFromVehicleId(vehicleId, cRouteId)
	returnCode = addRouteToSumo(vehicleId, routeId, route, mtraci, outputSocket)
	
	if returnCode == constants.ACK_OK:
		savePriorityVehicles(mtraci, vehicleId, priority, priorityVehicles, mPriorityVehicles)
		
		mVehicles.acquire()
		vehicles.append(vehicleId)
		mVehicles.release()
		
	sendIdentifiedAck(vehicleId, returnCode, outputSocket)	
	

def removeVehicles(vehiclesToDel, priorityVehicles, mPriorityVehicles, mtraci, outputSocket, vehicles, mVehicles):
	""" Removes the specified vehicles from the simulation """
	returnCode = constants.ACK_OK
	
	mVehicles.acquire()
	for vehicleToDel in vehiclesToDel:
		mPriorityVehicles.acquire()
		if vehicleToDel in priorityVehicles:
			priorityVehicles.remove(vehicleToDel)
		mPriorityVehicles.release()
		
		try:
			vehicles.remove(vehicleToDel)
		except:
			pass
		
		try:
			mtraci.acquire()
			traci.vehicle.remove(vehicleToDel)
		except:
			returnCode = constants.VEHICLE_DELETE_FAILED_UNKNOWN
		mtraci.release()
	mVehicles.release()
	
	sendAck(constants.PRINT_PREFIX_VEHICLE, returnCode, outputSocket)
	

def addRandomVehicles(vehicleIdPrefix, vehiclesNumber, routeSize, mtraci, vehicles, mVehicles):
	"""
	Adds vehiclesNumber vehicles to SUMO, linking each of these to a random route of routeSize edges
	"""
	Logger.info("{}Adding {} vehicles to the simulation...".format(constants.PRINT_PREFIX_VEHICLE, vehiclesNumber))
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
			mVehicles.acquire()
			vehicles.append(vehicleId)
			mtraci.acquire()
			traci.route.add(routeId, route)
			traci.vehicle.add(vehicleId,routeId,-2,0,0,0,"DEFAULT_VEHTYPE")
			mtraci.release()
			mVehicles.release()
			route[:] = []
			i += 1
		else:
			route = []
			
	Logger.info("{}Done".format(constants.PRINT_PREFIX_VEHICLE))
	sendAck(constants.PRINT_PREFIX_VEHICLE, returnCode, outputSocket)
	

def sendVehiclesSpeed(vehiclesId, outputSocket, mtraci, mVehicles):
	"""
	Sends the speed of the given vehicles to the distant client
	"""
	speedMsg = []
	speedMsg.append(constants.VEHICLE_SPEED_RESPONSE_HEADER)
	
	mVehicles.acquire()
	for vehicleId in vehiclesId:
		try:
			mtraci.acquire()
			speed = traci.vehicle.getSpeed(vehicleId)
			mtraci.release()
		
			speedMsg.append(constants.SEPARATOR)
			speedMsg.append(vehicleId)
			speedMsg.append(constants.SEPARATOR)
			speedMsg.append(str(speed))
		except:
			mtraci.release()
	mVehicles.release()
		
	speedMsg.append(constants.END_OF_MESSAGE)
		
	strmsg = ''.join(speedMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_VEHICLE, strmsg))
	
	
def getRegularVehicles(vehicles):
	"""
	Returns a vehicle list without the ignored vehicles (See constants)
	"""
	regularVehicles = []
	for vehicle in vehicles:
		if not constants.IGNORED_VEHICLES_REGEXP.match(vehicle):
			regularVehicles.append(vehicle)
	return regularVehicles
	

def sendVehiclesCoordinates(vehiclesId, mtraci, outputSocket, mVehicles):
	"""
	Gets every vehicles position from SUMO and send then these ones to the remote client by an output socket
	"""
	#If the simulated vehicles number we have to take into account is not 0
	vehiclesPos = []
	vehiclesPos.append(constants.VEHICLE_COORDS_RESPONSE_HEADER)
	
	mVehicles.acquire()
	for vehicleId in vehiclesId:
		try:
			mtraci.acquire()
			coords = traci.vehicle.getPosition(vehicleId)
			coordsGeo = traci.simulation.convertGeo(coords[0], coords[1], False)
			mtraci.release()
	
			#Build the message to send by the output socket
			vehiclesPos.append(constants.SEPARATOR)
			vehiclesPos.append(vehicleId)
			vehiclesPos.append(constants.SEPARATOR)
			vehiclesPos.append(str(coordsGeo[0]))
			vehiclesPos.append(constants.SEPARATOR)
			vehiclesPos.append(str(coordsGeo[1]))
		except:
			mtraci.release()
		
	mVehicles.release()
	
	#Send the position of each vehicle by the output socket
	vehiclesPos.append(constants.END_OF_MESSAGE)
	strmsg = ''.join(vehiclesPos)
	
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise constants.ClosedSocketException("The listening socket has been closed")
	

def sendArrivedVehicles(arrivedVehicles, mtraci, outputSocket):
	"""
	Gets all arrived vehicles ID from SUMO and send them to the remote client by output socket
	"""
	msgArrivedVehicles = []
	msgArrivedVehicles.append(constants.VEHICLE_ARRIVED_RESPONSE_HEADER)
	
	for vehicleId in arrivedVehicles:				
		msgArrivedVehicles.append(constants.SEPARATOR)
		msgArrivedVehicles.append(vehicleId)	

	msgArrivedVehicles.append(constants.END_OF_MESSAGE)
	strmsg = ''.join(msgArrivedVehicles)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_SIMULATOR, strmsg))
	

def run(mtraci, inputSocket, outputSocket, eShutdown, priorityVehicles, mPriorityVehicles, eVehicleReady, eManagerReady, vehicles, mVehicles):
	"""
	See file description
	"""
	bufferSize = 32768
	cRouteId = 0
	
	eVehicleReady.set()
	while not eManagerReady.is_set():
		time.sleep(constants.SLEEP_SYNCHRONISATION)
	
	while not eShutdown.is_set():
		try:
			try:
				# Read the message from the input socket (blocked until a message is read)
				buff = inputSocket.recv(bufferSize)
			except:
				raise constants.ClosedSocketException("The listening socket has been closed")
			
			if len(buff) == 0:
					raise constants.ClosedSocketException("The distant socket has been closed")
				
			listCommands = buff.decode().split(constants.MESSAGES_SEPARATOR)
			
			for cmd in listCommands:
				if len(cmd) != 0:
					command = cmd.split(constants.SEPARATOR)
					commandSize = len(command)
					
					for i in range(0, commandSize):
						command[i] = str(command[i])
						
					Logger.infoFile("{} Message received: {}".format(constants.PRINT_PREFIX_VEHICLE, cmd))
					
					# Add the user ID and the route to the map
					if commandSize > 2 and command[0] == constants.VEHICLE_ADD_REQUEST_HEADER:
						try:
							command.pop(0)
							vehicleId = command[0]
							command.pop(0)
							priority = command[0]
							command.pop(0)
							addVehicle(vehicleId, priority, command, mtraci, cRouteId, outputSocket, priorityVehicles, mPriorityVehicles, vehicles, mVehicles)
						except Exception as e:
							sendIdentifiedAck(command[1], constants.VEHICLE_INVALID_ROUTE, outputSocket)
							raise
						cRouteId += 1
						
						
					#Remove the specified vehicles from the simulation
					elif commandSize >= 1 and command[0] == constants.VEHICLE_DELETE_REQUEST_HEADER:
						if commandSize == 1:
							removeVehicles(list(vehicles), priorityVehicles, mPriorityVehicles, mtraci, outputSocket, vehicles, mVehicles)
						else:
							command.pop(0)
							removeVehicles(command, priorityVehicles, mPriorityVehicles, mtraci, outputSocket, vehicles, mVehicles)
						
						
					#Stress test, add random vehicles to the simulation
					elif commandSize == 4 and command[0] == constants.VEHICLE_ADD_RAND_REQUEST_HEADER:
						try:
							addRandomVehicles(command[1], int(command[2]), int(command[3]), mtraci, outputSocket, vehicles, mVehicles)
						except:
							sendAck(constants.PRINT_PREFIX_VEHICLE, constants.VEHICLE_MOCK_FAILED, outputSocket)
							raise
						
						
					#Send vehicles speed to the remote client
					elif commandSize >= 1 and command[0] == constants.VEHICLE_SPEED_REQUEST_HEADER:
						if commandSize == 1:
							sendVehiclesSpeed(vehicles, outputSocket, mtraci, mVehicles)
						else:
							command.pop(0)
							sendVehiclesSpeed(command, outputSocket, mtraci, mVehicles)
						
						
					#Send vehicles geographic coordinates to the remote client
					elif commandSize >= 1 and command[0] == constants.VEHICLE_COORDS_REQUEST_HEADER:
						if commandSize == 1:
							sendVehiclesCoordinates(vehicles, mtraci, outputSocket, mVehicles)
						else:
							command.pop(0)
							sendVehiclesCoordinates(command, mtraci, outputSocket, mVehicles)
						
						
					#Send arrived vehicles ID to the remote client
					elif commandSize == 1 and command[0] == constants.VEHICLE_ARRIVED_REQUEST_HEADER:
						mtraci.acquire()
						arrivedVehicles = traci.simulation.getArrivedIDList()
						mtraci.release()
						arrivedVehicles = getRegularVehicles(arrivedVehicles)
						sendArrivedVehicles(vehicles, outputSocket, mtraci)
						
						
					# Error
					else:
						Logger.warning("{}Invalid command received: {}".format(constants.PRINT_PREFIX_VEHICLE, command))
						sendAck(constants.PRINT_PREFIX_VEHICLE, constants.INVALID_MESSAGE, outputSocket)

		except Exception as e:
			if e.__class__.__name__ == constants.CLOSED_SOCKET_EXCEPTION or e.__class__.__name__ == constants.TRACI_EXCEPTION:
				Logger.info("{}Shutting down current thread".format(constants.PRINT_PREFIX_VEHICLE))
				sys.exit()
			else:
				Logger.error("{}A {} exception occurred:".format(constants.PRINT_PREFIX_VEHICLE, e.__class__.__name__))
				Logger.exception(e)
