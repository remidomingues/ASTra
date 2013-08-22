#!/usr/bin/env python

"""
@file	Route.py
@author  Remi Domingues
@date	23/07/2013

This script reads an input socket connected to the remote client and process a GET(1) command when received. A ROUTE(2) or ERROR(3) answer is then sent
The building/export or import of a graph (See Graph(10)) file is required for this purpose.
Junctions (See Graph(8)) and edges (See Graph(9)) dictionaries are also required.

Algorithm:
while 1:
	Waiting for a socket input data
	Processing request

(1) Routing request: GET routingAlgorithm geo src dest1 ... destN
		routingAlgorithm:
			if routingAlgorithm = DIJ, a Dijkstra algorithm is applied
			else if routingAlgorithm = DUA, a Duarouter subprocess is called for processing the routing request
		
		geo:
			if geo = 0, src = sumoEdgeId (same for every destination): the points must be defined by a SUMO edge ID
			else if geo = 1, src = lonSrc latSrc (same for every destination): the points must be defined by geographic coordinates
	
		dest1 ... destN:
			The number of destination points must be superior or equal to 1
			if more than one destination is given, the routing returned will start from src, then go to dest1, dest2...destN
			   
			   
(2) Routing response: ROU edge1 edge2 ... edgeN

(3) Error answer: ERR errorCode
        
(4) Error response when an invalid request is received : ERR 40
"""

import os
import traci
import socket
import traceback
import time
import Constants
import DuarouterRoute
import DijkstraRoute
import sys
import xml.sax
from Logger import Logger
from SharedFunctions import getOppositeEdge
from SharedFunctions import isJunction
from SharedFunctions import isDictionaryOutOfDate
from SharedFunctions import sendAck

"""
============================================================================================================================================
===                                            		  	   ROUTING REQUESTS MANAGEMENT 	      	                                         ===
============================================================================================================================================
"""
"""
Sends a routing(2) message to Client using the outputSocket
For this purpose, the route is converted to geographic coordinates by traci
"""
def sendRoute(route, outputSocket, mtraci):
	routeMsg = []
	routeMsg.append(Constants.ROUTING_RESPONSE_HEADER)
	
	for edge in route:
		routeMsg.append(Constants.SEPARATOR)
		routeMsg.append(str(edge))
		
	routeMsg.append(Constants.END_OF_MESSAGE)
		
	strmsg = ''.join(routeMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise Constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(Constants.PRINT_PREFIX_ROUTER, strmsg))


""" Sends an error(3) message to the remote client with an error code """
def sendRoutingError(outputSocket, errorCode):
	errorMsg = []
	errorMsg.append(Constants.ERROR_HEADER)
	errorMsg.append(Constants.SEPARATOR)
	errorMsg.append(errorCode)
	errorMsg.append(Constants.END_OF_MESSAGE)
		
	strmsg = ''.join(errorMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise Constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(Constants.PRINT_PREFIX_ROUTER, strmsg))


""" Return a list of edges from a list of continuous junctions """
def getRouteFromJunctions(junctions, junctionsDict):
	route = []
	
	for i in range(0, len(junctions) - 1):
		edge = list(junctionsDict[junctions[i]][1] & junctionsDict[junctions[i+1]][0])
		route.append(edge[0])
		
	return route


""" Return a SUMO edge ID from geographic coordinates """
def getEdgeFromCoords(lon, lat, mtraci):
	mtraci.acquire()
	try:
		edge = traci.simulation.convertRoad(lat, lon, True)[0]
	except:
		mtraci.release()
		raise
	mtraci.release()
	return edge


"""
- Transforms the source and destination coordinates to SUMO edges ID if geo is 1
- Resolves the routing demand by the specified algorithm
- Sends the route(2) back to Client
"""
def processRouteRequest(algorithm, geo, points, junctionsDict, graph, edgesDict, outputSocket, mtraci):
	if geo == Constants.GEOGRAPHIC_COORDS:
		edgesDest = []
		edgeSrc = getEdgeFromCoords(float(points[0]), float(points[1]), mtraci)
		
		i = 2
		while i < len(points):
			edgesDest.append(getEdgeFromCoords(float(points[i]), float(points[i+1]), mtraci))
			i += 2
	elif geo == Constants.EDGES_ID:
		edgeSrc = points[0]
		points.pop(0)
		edgesDest = points
	else:
		return sendRoutingError(outputSocket, Constants.ROUTE_INVALID_GEO)
	
	if algorithm == Constants.DIJKSTRA_REQUEST:
		returnCode, route = DijkstraRoute.processRouteRequest(edgeSrc, edgesDest, junctionsDict, graph, edgesDict)
	elif algorithm == Constants.DUAROUTER_REQUEST:
		returnCode, route = DuarouterRoute.processRouteRequest(edgeSrc, edgesDest, junctionsDict)
	else:
		return sendRoutingError(outputSocket, Constants.ROUTE_INVALID_ALGORITHM)
	
	if returnCode != 0:
		return sendRoutingError(outputSocket, returnCode)

	sendRoute(route, outputSocket, mtraci)


""" Reads an input socket connected to the remote client and process a GET(1) request when received. A ROUTE(2) or ERROR(3) response is then sent """
def run(mtraci, inputSocket, outputSocket, eShutdown, eRouteReady, eManagerReady, graph, junctionsDict, edgesDict):
	bufferSize = 1024
	
	eRouteReady.set()
	while not eManagerReady.is_set():
		time.sleep(Constants.SLEEP_SYNCHRONISATION)
	
	while not eShutdown.is_set():
		try:
			# Read the message from the input socket (blocked until a message is read)
			try:
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
						
					Logger.infoFile("{} Message received: {}".format(Constants.PRINT_PREFIX_ROUTER, cmd))
				
					# Routing request
					if commandSize >= 6 and command[0] == Constants.ROUTING_REQUEST_HEADER:
						try:
							command.pop(0)
							algorithm = command[0]
							command.pop(0)
							geo = command[0]
							command.pop(0)
							processRouteRequest(algorithm, geo, command, junctionsDict, graph, edgesDict, outputSocket, mtraci)
						except Exception as e:
							if e.__class__.__name__ != Constants.CLOSED_SOCKET_EXCEPTION and e.__class__.__name__ != Constants.TRACI_EXCEPTION:
								sendRoutingError(outputSocket, command[2], Constants.ROUTE_ROUTING_REQUEST_FAILED)
						
						
					# Error
					else:
						Logger.warning("{}Invalid command received: {}".format(Constants.PRINT_PREFIX_ROUTER, command))
						sendAck(Constants.PRINT_PREFIX_ROUTER, Constants.INVALID_MESSAGE, outputSocket)
				
		except Exception as e:
			if e.__class__.__name__ == Constants.CLOSED_SOCKET_EXCEPTION or e.__class__.__name__ == Constants.TRACI_EXCEPTION:
				Logger.info("{}Shutting down current thread".format(Constants.PRINT_PREFIX_ROUTER))
				sys.exit()
			else:
				Logger.error("{}A {} exception occurred:".format(Constants.PRINT_PREFIX_ROUTER, e.__class__.__name__))
				Logger.exception(e)
