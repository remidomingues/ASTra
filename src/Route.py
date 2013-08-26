#!/usr/bin/env python

"""
@file	route.py
@author  Remi Domingues
@date	23/07/2013

This script reads an input socket connected to the remote client and process a GET(1) command when received. A ROUTE(2) or ERROR(3) answer is then sent
The building/export or import of a graph (See Graph(10)) file is required for this purpose.
Junctions (See Graph(8)) and edges (See Graph(9)) dictionaries are also required.
Requests must be sent on the port 180003, responses are sent on the port 18004.

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
import constants
import duarouterRoute
import dijkstraRoute
import sys
import xml.sax
from logger import Logger
from sharedFunctions import getOppositeEdge
from sharedFunctions import isJunction
from sharedFunctions import isDictionaryOutOfDate
from sharedFunctions import sendAck

"""
============================================================================================================================================
===                                            		  	   ROUTING REQUESTS MANAGEMENT 	      	                                         ===
============================================================================================================================================
"""
def sendRoute(route, outputSocket, mtraci):
	"""
	Sends a routing(2) message to Client using the outputSocket
	For this purpose, the route is converted to geographic coordinates by traci
	"""
	routeMsg = []
	routeMsg.append(constants.ROUTING_RESPONSE_HEADER)
	
	for edge in route:
		routeMsg.append(constants.SEPARATOR)
		routeMsg.append(str(edge))
		
	routeMsg.append(constants.END_OF_MESSAGE)
		
	strmsg = ''.join(routeMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_ROUTER, strmsg))


def sendRoutingError(outputSocket, errorCode):
	"""
	Sends an error(3) message to the remote client with an error code
	"""
	errorMsg = []
	errorMsg.append(constants.ERROR_HEADER)
	errorMsg.append(constants.SEPARATOR)
	errorMsg.append(str(errorCode))
	errorMsg.append(constants.END_OF_MESSAGE)
		
	strmsg = ''.join(errorMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_ROUTER, strmsg))


def getRouteFromJunctions(junctions, junctionsDict):
	"""
	Return a list of edges from a list of continuous junctions
	"""
	route = []
	
	for i in range(0, len(junctions) - 1):
		edge = list(junctionsDict[junctions[i]][1] & junctionsDict[junctions[i + 1]][0])
		route.append(edge[0])
		
	return route


def getEdgeFromCoords(lon, lat, mtraci):
	"""
	Return a SUMO edge ID from geographic coordinates
	"""
	mtraci.acquire()
	try:
		edge = traci.simulation.convertRoad(lat, lon, True)[0]
	except:
		mtraci.release()
		raise
	mtraci.release()
	return edge


def processRouteRequest(algorithm, geo, points, junctionsDict, graphDict, edgesDict, outputSocket, mtraci):
	"""
	- Transforms the source and destination coordinates to SUMO edges ID if geo is 1
	- Resolves the routing demand by the specified algorithm
	- Sends the route(2) back to Client
	"""
	if geo == constants.GEOGRAPHIC_COORDS:
		edgesDest = []
		edgeSrc = getEdgeFromCoords(float(points[0]), float(points[1]), mtraci)
		
		i = 2
		while i < len(points):
			edgesDest.append(getEdgeFromCoords(float(points[i]), float(points[i + 1]), mtraci))
			i += 2
	elif geo == constants.EDGES_ID:
		edgeSrc = points[0]
		points.pop(0)
		edgesDest = points
	else:
		return sendRoutingError(outputSocket, constants.ROUTE_INVALID_GEO)
	
	if algorithm == constants.DIJKSTRA_REQUEST:
		returnCode, route = dijkstraRoute.processRouteRequest(edgeSrc, edgesDest, junctionsDict, graphDict, edgesDict)
	elif algorithm == constants.DUAROUTER_REQUEST:
		returnCode, route = duarouterRoute.processRouteRequest(edgeSrc, edgesDest, junctionsDict)
	else:
		return sendRoutingError(outputSocket, constants.ROUTE_INVALID_ALGORITHM)
	
	if returnCode != 0:
		return sendRoutingError(outputSocket, returnCode)

	sendRoute(route, outputSocket, mtraci)


def run(mtraci, inputSocket, outputSocket, eShutdown, eRouteReady, eManagerReady, graphDict, junctionsDict, edgesDict):
	"""
	See file description
	"""
	bufferSize = 1024
	
	eRouteReady.set()
	while not eManagerReady.is_set():
		time.sleep(constants.SLEEP_SYNCHRONISATION)
	
	while not eShutdown.is_set():
		try:
			# Read the message from the input socket (blocked until a message is read)
			try:
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
						
					Logger.infoFile("{} Message received: {}".format(constants.PRINT_PREFIX_ROUTER, cmd))
				
					# Routing request
					if commandSize >= 6 and command[0] == constants.ROUTING_REQUEST_HEADER:
						try:
							command.pop(0)
							algorithm = command[0]
							command.pop(0)
							geo = int(command[0])
							command.pop(0)
							processRouteRequest(algorithm, geo, command, junctionsDict, graphDict, edgesDict, outputSocket, mtraci)
						except Exception as e:
							if e.__class__.__name__ != constants.CLOSED_SOCKET_EXCEPTION and e.__class__.__name__ != constants.TRACI_EXCEPTION:
								sendRoutingError(outputSocket, constants.ROUTE_ROUTING_REQUEST_FAILED)
								raise
						
						
					# Error
					else:
						Logger.warning("{}Invalid command received: {}".format(constants.PRINT_PREFIX_ROUTER, command))
						sendAck(constants.PRINT_PREFIX_ROUTER, constants.INVALID_MESSAGE, outputSocket)
				
		except Exception as e:
			if e.__class__.__name__ == constants.CLOSED_SOCKET_EXCEPTION or e.__class__.__name__ == constants.TRACI_EXCEPTION:
				Logger.info("{}Shutting down current thread".format(constants.PRINT_PREFIX_ROUTER))
				sys.exit()
			else:
				Logger.error("{}A {} exception occurred:".format(constants.PRINT_PREFIX_ROUTER, e.__class__.__name__))
				Logger.exception(e)
