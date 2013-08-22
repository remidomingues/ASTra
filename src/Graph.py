#!/usr/bin/env python

"""
@file	Graph.py
@author  Remi Domingues
@date	13/08/2013

This script reads an input socket connected to the remote client and process a request when received

Algorithm:
while 1:
	Waiting for a socket input data
	Processing one of the following requests and sending (if relevant) the corresponding response
		
Socket messages:
EDGES COORDINATES
(1) Get all edges coordinates (request): COO

(2) Get specified edges coordinates (request): COO edge1 edge2...edgeN

(3) Edges coordinates (response): COO edge1 lon1A lat1A lon1B lat1B...edgeN lonNA latNA lonNB latNB (N in [0-Y] (See Constants for Y value)
		These messages of followed by an end message (response): EDG END
		With A and B the edge extremities
		
		
EDGES LENGTH
(4) Get all edges length (request): LEN

(5) Get specified edges length (request): LEN edge1 edge2...edgeN

(6) Edges length (response): LEN edge1 length1...edgeN lengthN (N in [0-Y] (See Constants for Y value)
		These messages of followed by an end message (response): LEN END
		
		
EDGES CONGESTION
(7) Get all edges congestion (request): CON

(8) Get specified edges congestion (request): CON edge1 edge2...edgeN

(9) Edges congestion (response): CON edge1 congestion1...edgeN congestionN (N in [0-Y] (See Constants for Y value)
		These messages of followed by an end message (response): CON END
		With congestion = average speed on the edge during the last step / max speed on this step
		

EDGES SUCCESSORS (GRAPH)
(10) Get the graph (each edge linked with each edge successor) (request): SUC

(11) Get some specified edges successors (request): SUC edge1 edge2...edgeN

(12) Edges successors (response): SUCC,edge1 succ1 succ11 succ12,edge2 succ21 succ22,...,edgeN succN1 succN2 (N in [0-Y] (See Constants for Y value)
		These messages of followed by an end message (response): SUCC,END
		
		
BLOCK/UNBLOCK EDGE
(13) Block edges request: BLO edge1 nbLanes1 ... edgeN nbLanesN
		Note : if nbLanes = -1, every lane will be blocked

(14) Block edges request: UNB edge1 ... edgeN

(15) Acknowledge response (14): ACK returnCode


EDGE ID
(16) Get an edge ID from geographic coordinates request: EID lon lat

(17) Edge ID response : EID edgeId


ERROR
(18) Error response when an invalid request is received: ACK 40

		
Dictionaries:
(19) Junction dictionary:
		- Key=junctionId
		- Value=[Collection(edgesId predecessors of the junction), Set(edgesId successors of the junction)]
		
(20) EdgesDictionary:
		- Key=edgeId
		- Value=[junction predecessor, junctionSuccessor]
		
(21) Graph:
		- Key=edgeIf
		- Value=Dictionary:
					- Key=edgeId successor
					- Value=edge length between the two edges=successor edge length
"""

import os
import traci
import socket
import traceback
import time
import Constants
import traci
import traceback
from Logger import Logger
import xml.sax
from Logger import Logger
from SharedFunctions import getOppositeEdge
from SharedFunctions import isJunction
from SharedFunctions import isDictionaryOutOfDate
from SharedFunctions import sendAck
from Route import getEdgeFromCoords

"""
============================================================================================================================================
===                                              		JUNCTIONS DICTIONARY MANAGEMENT (4)    		                                     ===
============================================================================================================================================
"""
""" Writes the junctions dictionary in an output file """
def exportJunctionsDictionary(junctionsDict):
	Logger.info("{}Exporting junctions dictionary...".format(Constants.PRINT_PREFIX_DIJKSTRA))
	file = open(Constants.SUMO_JUNCTIONS_DICTIONARY_FILE, 'w')
	
	for pair in junctionsDict.items():
		file.write(pair[0])
		file.write(Constants.END_OF_LINE)
		
		size = len(pair[1][0])
		i = 1
		for value in pair[1][0]:
			file.write(value)
			if i != size: 
				file.write(Constants.SEPARATOR)
				i += 1
		file.write(Constants.END_OF_LINE)
		
		size = len(pair[1][1])
		i = 1
		for value in pair[1][1]:
			file.write(value)
			if i != size: 
				file.write(Constants.SEPARATOR)
				i += 1
		file.write(Constants.END_OF_LINE)
		
	file.close()
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_DIJKSTRA))
	
	
""" Reads the junctions dictionary from an input file """
def importJunctionsDictionary():
	Logger.info("{}Importing junctions dictionary...".format(Constants.PRINT_PREFIX_DIJKSTRA))
	file = open(Constants.SUMO_JUNCTIONS_DICTIONARY_FILE, 'r')
	junctionsDict = dict()
	
	key = file.readline()[0:-1]
	while key:
		value = [set(), set()]
		
		strvalues = file.readline()[0:-1]
		lvalues = strvalues.split(Constants.SEPARATOR)
		for v in lvalues:
			value[0].add(v)
			
		strvalues = file.readline()[0:-1]
		lvalues = strvalues.split(Constants.SEPARATOR)
		for v in lvalues:
			value[1].add(v)
			
		junctionsDict[key] = value
		key = file.readline()[0:-1]
	
	file.close()
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_DIJKSTRA))
	return junctionsDict



"""
============================================================================================================================================
===                                              			 EDGES DICTIONARY MANAGEMENT (5)   		                                     ===
============================================================================================================================================
"""
""" Writes the edges dictionary in an output file """
def exportEdgesDictionary(edgesDict):
	Logger.info("{}Exporting edges dictionary...".format(Constants.PRINT_PREFIX_DIJKSTRA))
	file = open(Constants.SUMO_EDGES_DICTIONARY_FILE, 'w')
	
	for pair in edgesDict.items():
		file.write(pair[0])
		file.write(Constants.SEPARATOR)
		file.write(pair[1][0])
		file.write(Constants.SEPARATOR)
		file.write(pair[1][1])
		file.write(Constants.END_OF_LINE)

	file.close()
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_DIJKSTRA))
	
	
""" Reads the edges dictionary from an input file """
def importEdgesDictionary():
	Logger.info("{}Importing edges dictionary...".format(Constants.PRINT_PREFIX_DIJKSTRA))
	file = open(Constants.SUMO_EDGES_DICTIONARY_FILE, 'r')
	edgesDict = dict()
	
	line = file.readline()[0:-1]
	while line:
		array = line.split(Constants.SEPARATOR)
		edgesDict[array[0]] = [array[1], array[2]]
		line = file.readline()[0:-1]
		
	file.close()
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_DIJKSTRA))
	return edgesDict



"""
============================================================================================================================================
===                                              			 GRAPH DICTIONARY MANAGEMENT (6)  		                                     ===
============================================================================================================================================
"""
""" Writes the graph in an output file """
def exportGraph(graph):
	Logger.info("{}Exporting graph...".format(Constants.PRINT_PREFIX_DIJKSTRA))
	file = open(Constants.SUMO_GRAPH_FILE, 'w')
	
	for pair in graph.items():
		file.write(pair[0])
		
		for valuePair in pair[1].items():
			file.write(Constants.SEPARATOR)
			file.write(valuePair[0])
			file.write(Constants.SEPARATOR)
			file.write(str(valuePair[1]))
			
		file.write(Constants.END_OF_LINE)
		
	file.close()
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_DIJKSTRA))
	
	
""" Reads the network graph from an input file """
def importGraph():
	Logger.info("{}Importing graph...".format(Constants.PRINT_PREFIX_DIJKSTRA))
	file = open(Constants.SUMO_GRAPH_FILE, 'r')
	graph = dict()
	
	line = file.readline()[0:-1]
	while line:
		lineArray = line.split(Constants.SEPARATOR)
		junctionNode = lineArray[0]
		graph[junctionNode] = dict()
		
		i = 1
		while i < len(lineArray):
			junctionSuccessor = lineArray[i]
			edgeLength = lineArray[i+1]
			graph[junctionNode][junctionSuccessor] = float(edgeLength)
			i += 2

		line = file.readline()[0:-1]
	
	file.close()
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_DIJKSTRA))
	return graph



"""
============================================================================================================================================
===                                     JUNCTIONS(4), EDGES(5) AND GRAPH(6) DICTIONARIES MANAGEMENT (5)   		                         ===
============================================================================================================================================
"""
"""
SAX handler used for parsing a SUMO network file in order to build
a graph, junctions and edges dictionary
"""
class NetworkHandler(xml.sax.ContentHandler):
	def __init__(self, graph, junctionsDict, edgesDict, mtraci):
		xml.sax.ContentHandler.__init__(self)
		self.junctionFrom = ''
		self.junctionTo = ''
		self.edgeId = ''
		self.graph = graph
		self.junctionsDict = junctionsDict
		self.edgesDict = edgesDict
		self.mtraci = mtraci

	def startElement(self, name, attrs):
		if name == Constants.XML_EDGE_ELEMENT:
			self.edgeId = str(attrs.get(Constants.XML_EDGE_ID))
			
			if self.edgeId[0] != ':':
				self.junctionFrom = str(attrs.get(Constants.XML_EDGE_FROM_JUNCTION))
				self.junctionTo = str(attrs.get(Constants.XML_EDGE_TO_JUNCTION))
				
				#Junctions dictionary
				if not self.junctionFrom in self.junctionsDict:
					self.junctionsDict[self.junctionFrom] = [set(), set()]
			
				if not self.junctionTo in self.junctionsDict:
					self.junctionsDict[self.junctionTo]= [set(), set()]
			
				self.junctionsDict[self.junctionTo][0].add(self.edgeId)
				self.junctionsDict[self.junctionFrom][1].add(self.edgeId)
				
				#Edges dictionary
				self.edgesDict[self.edgeId] = [self.junctionFrom, self.junctionTo]
			
				#Graph
				if not self.edgeId in self.graph:
					self.graph[self.edgeId] = dict()
					
					
		elif name == Constants.XML_LANE_ELEMENT:
			laneId = attrs.get(Constants.XML_LANE_ID)
			if laneId[0] != ':':
				laneId = str(laneId)
				self.mtraci.acquire()
				links = traci.lane.getLinks(laneId)
				self.mtraci.release()
				
				for successorLaneId in links:
					successorEdgeId = successorLaneId[0].split('_')[0]
					
					self.mtraci.acquire()
					length = traci.lane.getLength(successorLaneId[0])
					self.mtraci.release()
					
					self.graph[self.edgeId][successorEdgeId] = length


"""
Returns
- A graph built as a dictionary as {Key=junctionId, Value=Dict as{Key=junction successor, Value=edge length between the junctions}
- A junctions dictionary as {Key=junctionId, Value=[Set(edgesId predecessors of the junction), Set(edgesId successors of the junction)]
- An edges dictionary as {Key=edgeId, Value=[junction predecessor, junction successor]
"""
def buildGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci):
	Logger.info("{}Building graph, junctions dictionary and edges dictionary...".format(Constants.PRINT_PREFIX_DIJKSTRA))
	
	#Initializing variables
	graph = dict()
	junctionsDict = dict()
	edgesDict = dict()
		
	#Parsing XML network file
	parser = xml.sax.make_parser()
	parser.setContentHandler(NetworkHandler(graph, junctionsDict, edgesDict, mtraci))
	parser.parse(Constants.SUMO_NETWORK_FILE)
	#correctGraph(graph)
		
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_DIJKSTRA))
	return graph, junctionsDict, edgesDict


""" Returns the graph(*), junctions(**) and edges(***) dictionary. This one is obtained from a text file, updated if new map data are detected """
def getGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci):
	if isDictionaryOutOfDate(Constants.SUMO_JUNCTIONS_DICTIONARY_FILE, Constants.SUMO_NETWORK_FILE) or isDictionaryOutOfDate(Constants.SUMO_EDGES_DICTIONARY_FILE, Constants.SUMO_NETWORK_FILE) or isDictionaryOutOfDate(Constants.SUMO_GRAPH_FILE, Constants.SUMO_NETWORK_FILE):
		graph, junctionsDict, edgesDict = buildGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci)
		exportGraph(graph)
		exportJunctionsDictionary(junctionsDict)
		exportEdgesDictionary(edgesDict)
	else:
		graph = importGraph()
		junctionsDict = importJunctionsDictionary()
		edgesDict = importEdgesDictionary()
	return graph, junctionsDict, edgesDict



"""
============================================================================================================================================
===                                            		  	   GRAPH REQUESTS MANAGEMENT 	      	                                         ===
============================================================================================================================================
"""
""" Returns the information header corresponding to the given information type """
def getInformationHeader(informationType):
	if informationType == Constants.EDGES_COORDS:
		return  Constants.EDGES_COORDS_RESPONSE_HEADER
	elif informationType == Constants.EDGES_CONGESTION:
		return Constants.EDGES_CONGESTION_RESPONSE_HEADER
	elif informationType == Constants.EDGES_LENGTH:
		return Constants.EDGES_LENGTH_RESPONSE_HEADER
	elif informationType == Constants.EDGES_SUCCESSORS:
		return  Constants.SUCCESSORS_RESPONSE_HEADER
	
	
""" Returns the information end corresponding to the given information type """
def getInformationEnd(informationType):
	if informationType == Constants.EDGES_COORDS:
		return  Constants.EDGES_COORDS_END
	elif informationType == Constants.EDGES_LENGTH:
		return Constants.EDGES_LENGTH_END
	elif informationType == Constants.EDGES_CONGESTION:
		return Constants.EDGES_CONGESTION_END
	elif informationType == Constants.EDGES_SUCCESSORS:
		return  Constants.SUCCESSORS_END
	
	
""" Returns the edge list separator corresponding to the given information type """
def getEdgeListSeparator(informationType):
	if informationType == Constants.EDGES_SUCCESSORS:
		return Constants.SUCCESSORS_LIST_SEPARATOR
	return Constants.SEPARATOR
	
	
""" Returns the maximum edges number per message corresponding to the given information type """
def getMaximumEdgesPerMessage(informationType):
	if informationType == Constants.EDGES_COORDS:
		return  Constants.EDGES_NUMBER_PER_COORDS_MESSAGE
	elif informationType == Constants.EDGES_LENGTH:
		return Constants.EDGES_NUMBER_PER_LENGTH_MESSAGE
	elif informationType == Constants.EDGES_CONGESTION:
		return Constants.EDGES_NUMBER_PER_CONGESTION_MESSAGE
	elif informationType == Constants.EDGES_SUCCESSORS:
		return  Constants.SUCCESSORS_NUMBER_PER_MESSAGE


"""
Send information messages to Client, followed by and end message.
The dictionary must be the edgesDictionary if an edges coordinates () request is specified
The dictionary must be the graphDictionary if a graph () or successors () request is specified
"""
def sendEdgesDetails(edges, outputSocket, mtraci, informationType, dictionary):
	edgesNumber = 0
	edgesMsg = []
	
	informationHeader = getInformationHeader(informationType)
	informationEnd = getInformationEnd(informationType)
	edgeListSeparator = getEdgeListSeparator(informationType)
	maximumEdgesPerMsg = getMaximumEdgesPerMessage(informationType)
	
	#Adding specified header
	edgesMsg.append(informationHeader)
	
	for edge in edges:
		if edge[0] != ':':
			edgesMsg.append(edgeListSeparator)
			edgesMsg.append(edge)
			edgesMsg.append(Constants.SEPARATOR)
			
			#EDGES COORDINATES
			if(informationType == Constants.EDGES_COORDS):
				#Getting the two junctions ID linked with the current edge
				edgesJunctions = dictionary[edge]
				
				#Getting geographic coordinates of the two junctions center
				mtraci.acquire()
				predecessorCoords = traci.junction.getPosition(edgesJunctions[0])
				predecessorCoordsGeo = traci.simulation.convertGeo(predecessorCoords[0], predecessorCoords[1], False)
				successorCoords = traci.junction.getPosition(edgesJunctions[1])
				successorCoordsGeo = traci.simulation.convertGeo(successorCoords[0], successorCoords[1], False)
				mtraci.release()
	
				#Adding to the current message
				edgesMsg.append(str(predecessorCoordsGeo[0]))
				edgesMsg.append(Constants.SEPARATOR)
				edgesMsg.append(str(predecessorCoordsGeo[1]))
				edgesMsg.append(Constants.SEPARATOR)
				edgesMsg.append(str(successorCoordsGeo[0]))
				edgesMsg.append(Constants.SEPARATOR)
				edgesMsg.append(str(successorCoordsGeo[1]))
			
			#EDGES LENGTH
			elif(informationType == Constants.EDGES_LENGTH):
				lane = edge + '_0'
				
				#Getting edge length
				mtraci.acquire()
				length = traci.lane.getLength(lane)
				mtraci.release()
				
				#Adding to the current message
				edgesMsg.append(str(length))
			
			#EDGES CONGESTION
			elif(informationType == Constants.EDGES_CONGESTION):
				lane = edge + '_0'
				
				#Calculating congestion
				mtraci.acquire()
				congestion = traci.edge.getLastStepOccupancy(edge)
				mtraci.release()
				
				#Adding to the current message
				edgesMsg.append(str(congestion))
			
			#EDGES SUCCESSORS (GRAPH)
			elif(informationType == Constants.EDGES_SUCCESSORS):
				for edgeSucc in dictionary[edge]:
					edgesMsg.append(edgeSucc)
					edgesMsg.append(Constants.SEPARATOR)
			
			
			edgesNumber += 1
			
			#Sending the message if this one has reached the maximum edges number per message
			if edgesNumber == maximumEdgesPerMsg:
				edgesMsg.append(Constants.END_OF_MESSAGE)
				strmsg = ''.join(edgesMsg)
				try:
					outputSocket.send(strmsg.encode())
				except:
					raise Constants.ClosedSocketException("The listening socket has been closed")
				Logger.infoFile("{} Message sent: <{} edges information ({})>".format(Constants.PRINT_PREFIX_GRAPH, maximumEdgesPerMsg, informationType))
				
				edgesNumber = 0
				edgesMsg[:] = []
				
				#Adding specified header
				edgesMsg.append(informationHeader)
		
	if edgesNumber != 0:
		edgesMsg.append(Constants.END_OF_MESSAGE)
		
		strmsg = ''.join(edgesMsg)
		try:
			outputSocket.send(strmsg.encode())
		except:
			raise Constants.ClosedSocketException("The listening socket has been closed")
			Logger.infoFile("{} Message sent: <{} edges information ({})>".format(Constants.PRINT_PREFIX_GRAPH, edgesNumber, informationType))
		
	
	#Sending end of edges information messages
	edgesMsg[:] = []
	
	#Adding specified header
	edgesMsg.append(informationHeader)
	edgesMsg.append(edgeListSeparator)

	#Adding specified ending
	edgesMsg.append(informationEnd)
	edgesMsg.append(Constants.END_OF_MESSAGE)
	
	strmsg = ''.join(edgesMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise Constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(Constants.PRINT_PREFIX_GRAPH, strmsg))
	
	
""" Blocks edges in the SUMO simulated network by adding stopped vehicles """
def blockEdges(mtraci, edgesBlocked, idCpt, outputSocket):
	cpt = 1
	i = 0
	while i < len(edgesBlocked):
		edgeBlocked = edgesBlocked[i]
		i += 1
		nbLanesBlocked = int(edgesBlocked[i])
		i += 1
		
		routeId = Constants.BLOCKED_ROUTE_ID_PREFIX + str(idCpt + cpt)
		route = [edgeBlocked]
		laneIndex = 0
		laneBlocked = edgeBlocked + '_0'
		
		mtraci.acquire()
		traci.route.add(routeId, route)
		mtraci.release()
	    
		while laneIndex < nbLanesBlocked:
			vehicleId = Constants.BLOCKED_VEHICLE_ID_PREFIX + str(idCpt + cpt)
			#TODO: improve, we can use the lane number by adding it to a dictionary when parsing the network
			try:
			    mtraci.acquire()
			    laneLength = traci.lane.getLength(laneBlocked)
			    mtraci.release()
			except:
				mtraci.release()
				break
			   
			laneLength /= 2.0
	
			mtraci.acquire()
			traci.vehicle.add(vehicleId, routeId, -2, 0, 0, 0, Constants.DEFAULT_VEHICLE_TYPE)
			traci.vehicle.setStop(vehicleId, edgeBlocked, laneLength, laneIndex, 2147483646)
			mtraci.release()
			
			cpt += 1
			laneIndex += 1
			laneBlocked = laneBlocked[:-1] + str(laneIndex)
			
	sendAck(Constants.PRINT_PREFIX_GRAPH, Constants.ACK_OK, outputSocket)
	return cpt

				
""" Unblocks edges in the SUMO simulated network by removing blocked vehicle previously added """
def unblockEdges(mtraci, edgesBlocked):
	for edgeBlocked in edgeBlocked:
		try:
			mtraci.acquire()
			blockedVehicles = traci.edge.getLastStepVehicleIDs(edgeBlocked)
		except:
			mtraci.release()
			return sendAck(Constants.PRINT_PREFIX_GRAPH, Constants.GRAPH_UNKNOWN_EDGE, outputSocket)
		mtraci.release()
		
		for blockedVehicle in blockedVehicles:
			if blockedVehicle.startswith(Constants.BLOCKED_VEHICLE_ID_PREFIX):
				mtraci.acquire()
				traci.vehicle.remove(vehicleId)
				mtraci.release()
				
	sendAck(Constants.PRINT_PREFIX_GRAPH, Constants.ACK_OK, outputSocket)
	
	
""" Sends an edge ID calculated from geographic coordinates to the remote client """
def sendEdgeId(mtraci, lon, lat, outputSocket):
	edgeId = getEdgeFromCoords(lon, lat, mtraci)
	
	routeCoordsMsg = []
	routeCoordsMsg.append(Constants.EDGE_ID_RESPONSE_HEADER)
	routeCoordsMsg.append(Constants.SEPARATOR)
	routeCoordsMsg.append(edgeId)
	routeCoordsMsg.append(Constants.END_OF_MESSAGE)
		
	strmsg = ''.join(routeCoordsMsg)
	try:
		outputSocket.send(strmsg.encode())
	except:
		raise Constants.ClosedSocketException("The listening socket has been closed")
	Logger.infoFile("{} Message sent: {}".format(Constants.PRINT_PREFIX_GRAPH, strmsg))
		

""" Reads an input socket connected to the remote client and process a get coordinates(6), get congestion or block edge(7) request when received """
def run(mtraci, inputSocket, outputSocket, eShutdown, eGraphReady, eManagerReady, graph, junctionsDict, edgesDict):
	bufferSize = 32768
	blockedIdCpt = 0
						
	mtraci.acquire()
	edges = traci.edge.getIDList()
	mtraci.release()
	
	eGraphReady.set()
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
						
					Logger.infoFile("{} Message received: {}".format(Constants.PRINT_PREFIX_GRAPH, cmd))
						
					#===== EDGES COORDINATES =====
					# Send all edges coordinates to Client
					if commandSize == 1 and command[0] == Constants.ALL_EDGES_COORDS_REQUEST_HEADER:
						sendEdgesDetails(edges, outputSocket, mtraci, Constants.EDGES_COORDS, edgesDict)
					
					# Send the specified edges coordinates to Client	
					elif commandSize > 1 and command[0] == Constants.EDGES_COORDS_REQUEST_HEADER:
						command.pop(0)
						sendEdgesDetails(command, outputSocket, mtraci, Constants.EDGES_COORDS, edgesDict)
					
					
					#===== EDGES LENGTH =====
					# Send all edges length to Client
					elif commandSize == 1 and command[0] == Constants.ALL_EDGES_LENGTH_REQUEST_HEADER:
						sendEdgesDetails(edges, outputSocket, mtraci, Constants.EDGES_LENGTH, None)
					
					# Send the specified edges length to Client	
					elif commandSize > 1 and command[0] == Constants.EDGES_LENGTH_REQUEST_HEADER:
						command.pop(0)
						sendEdgesDetails(command, outputSocket, mtraci, Constants.EDGES_LENGTH, None)
					
					
					#===== EDGES CONGESTION =====
					# Send all edges congestion to Client
					elif commandSize == 1 and command[0] == Constants.ALL_EDGES_CONGESTION_REQUEST_HEADER:
						sendEdgesDetails(edges, outputSocket, mtraci, Constants.EDGES_CONGESTION, None)
					
					# Send the specified edges congestion to Client	
					elif commandSize > 1 and command[0] == Constants.EDGES_CONGESTION_REQUEST_HEADER:
						command.pop(0)
						sendEdgesDetails(command, outputSocket, mtraci, Constants.EDGES_CONGESTION, None)
					
					
					#===== EDGES SUCCESSORS (GRAPH) =====
					# Send the  graph dictionary to Client
					elif commandSize == 1 and command[0] == Constants.ALL_SUCCESSORS_REQUEST_HEADER:
						sendEdgesDetails(edges, outputSocket, mtraci, Constants.EDGES_SUCCESSORS, graph)
					
					# Send the specified edges successors with the corresponding distance to Client	
					elif commandSize > 1 and command[0] == Constants.SUCCESSORS_REQUEST_HEADER:
						command.pop(0)
						sendEdgesDetails(command, outputSocket, mtraci, Constants.EDGES_SUCCESSORS, graph)
						
						
					#===== BLOCK/UNBLOCK EDGES =====
					# Block edges in the SUMO simulation
					elif commandSize > 1 and command[0] == Constants.BLOCK_EDGE_REQUEST_HEADER:
						command.pop(0)
						blockedIdCpt += blockEdges(mtraci, command, blockedIdCpt, outputSocket)
						
					# Unblock edges in the SUMO simulation
					elif commandSize > 1 and command[0] == Constants.UNBLOCK_EDGE_REQUEST_HEADER:
						command.pop(0)
						unblockEdges(mtraci, command, outputSocket)
						
						
					#===== EDGE ID =====
					# Sending an edge ID from geographic coordinates
					elif commandSize == 3 and command[0] == Constants.EDGE_ID_REQUEST_HEADER:
						sendEdgeId(mtraci, command[1], command[2], outputSocket)
						
						
					#===== UNKNOWN REQUEST =====
					else:
						Logger.warning("{}Invalid command received: {}".format(Constants.PRINT_PREFIX_GRAPH, command))
						sendAck(Constants.PRINT_PREFIX_GRAPH, Constants.INVALID_MESSAGE, outputSocket)

		except Exception as e:
			if e.__class__.__name__ == Constants.CLOSED_SOCKET_EXCEPTION or e.__class__.__name__ == Constants.TRACI_EXCEPTION:
				Logger.info("{}Shutting down current thread".format(Constants.PRINT_PREFIX_GRAPH))
				sys.exit()
			else:
				Logger.error("{}A {} exception occurred:".format(Constants.PRINT_PREFIX_GRAPH, e.__class__.__name__))
				Logger.exception(e)
