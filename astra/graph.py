#!/usr/bin/env python

"""
@file    graph.py
@author  Remi Domingues
@date    13/08/2013

This script reads an input socket connected to the remote client and process a request when received.
Requests must be sent on the port 180001, responses are sent on the port 18002. 
        
Socket messages:
EDGES COORDINATES
(1) Get all edges coordinates (request): COO

(2) Get specified edges coordinates (request): COO edge1 edge2...edgeN

(3) Edges coordinates (response): COO edge1 lon1A lat1A lon1B lat1B...edgeN lonNA latNA lonNB latNB (N in [0-Y] if all edges were requested (See constants for Y value))
        If ALL EDGES were requested, these messages are followed by an end message (response): COO END
        With A and B the edge extremities
        
        
EDGES LENGTH
(4) Get all edges length (request): LEN

(5) Get specified edges length (request): LEN edge1 edge2...edgeN

(6) Edges length (response): LEN edge1 length1...edgeN lengthN (N in [0-Y] if all edges were requested (See constants for Y value))
        If ALL EDGES were requested, these messages are followed by an end message (response): LEN END
        
        
EDGES CONGESTION
(7) Get all edges congestion (request): CON

(8) Get specified edges congestion (request): CON edge1 edge2...edgeN

(9) Edges congestion (response): CON edge1 congestion1...edgeN congestionN (N in [0-Y] if all edges were requested (See constants for Y value))
        If ALL EDGES were requested, these messages are followed by an end message (response): CON END
        With congestion = average speed on the edge during the last step / max speed on this step
        

EDGES SUCCESSORS (GRAPH)
(10) Get the graph (each edge linked with each edge successor) (request): SUC

(11) Get some specified edges successors (request): SUC edge1 edge2...edgeN

(12) Edges successors (response): SUCC,edge1 succ1 succ11 succ12,edge2 succ21 succ22,...,edgeN succN1 succN2 (N in [0-Y] if all edges were requested (See constants for Y value))
        If ALL EDGES were requested, these messages are followed by an end message (response): SUCC,END
        
        
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

import sys
import traci
import time
import constants
from logger import Logger
import xml.sax
from sharedFunctions import isDictionaryOutOfDate
from sharedFunctions import sendAck
from route import getEdgeFromCoords

"""
============================================================================================================================================
===                                                      JUNCTIONS DICTIONARY MANAGEMENT (4)                                                 ===
============================================================================================================================================
"""
def exportJunctionsDictionary(junctionsDict):
    """
    Writes the junctions dictionary in an output file
    """
    Logger.info("{}Exporting junctions dictionary...".format(constants.PRINT_PREFIX_DIJKSTRA))
    junctionsFile = open(constants.SUMO_JUNCTIONS_DICTIONARY_FILE, 'w')
    
    for pair in junctionsDict.items():
        junctionsFile.write(pair[0])
        junctionsFile.write(constants.END_OF_LINE)
        
        size = len(pair[1][0])
        i = 1
        for value in pair[1][0]:
            junctionsFile.write(value)
            if i != size: 
                junctionsFile.write(constants.SEPARATOR)
                i += 1
        junctionsFile.write(constants.END_OF_LINE)
        
        size = len(pair[1][1])
        i = 1
        for value in pair[1][1]:
            junctionsFile.write(value)
            if i != size: 
                junctionsFile.write(constants.SEPARATOR)
                i += 1
        junctionsFile.write(constants.END_OF_LINE)
        
    junctionsFile.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_DIJKSTRA))
    
    
def importJunctionsDictionary():
    """
    Reads the junctions dictionary from an input file
    """
    Logger.info("{}Importing junctions dictionary...".format(constants.PRINT_PREFIX_DIJKSTRA))
    junctionsFile = open(constants.SUMO_JUNCTIONS_DICTIONARY_FILE, 'r')
    junctionsDict = dict()
    
    key = junctionsFile.readline()[0:-1]
    while key:
        value = [set(), set()]
        
        strvalues = junctionsFile.readline()[0:-1]
        lvalues = strvalues.split(constants.SEPARATOR)
        for v in lvalues:
            value[0].add(v)
            
        strvalues = junctionsFile.readline()[0:-1]
        lvalues = strvalues.split(constants.SEPARATOR)
        for v in lvalues:
            value[1].add(v)
            
        junctionsDict[key] = value
        key = junctionsFile.readline()[0:-1]
    
    junctionsFile.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_DIJKSTRA))
    return junctionsDict



"""
============================================================================================================================================
===                                                           EDGES DICTIONARY MANAGEMENT (5)                                                ===
============================================================================================================================================
"""
def exportEdgesDictionary(edgesDict):
    """
    Writes the edges dictionary in an output edgesFile
    """
    Logger.info("{}Exporting edges dictionary...".format(constants.PRINT_PREFIX_DIJKSTRA))
    edgesFile = open(constants.SUMO_EDGES_DICTIONARY_FILE, 'w')
    
    for pair in edgesDict.items():
        edgesFile.write(pair[0])
        edgesFile.write(constants.SEPARATOR)
        edgesFile.write(pair[1][0])
        edgesFile.write(constants.SEPARATOR)
        edgesFile.write(pair[1][1])
        edgesFile.write(constants.END_OF_LINE)

    edgesFile.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_DIJKSTRA))
    
    
def importEdgesDictionary():
    """
    Reads the edges dictionary from an input edgesFile
    """
    Logger.info("{}Importing edges dictionary...".format(constants.PRINT_PREFIX_DIJKSTRA))
    edgesFile = open(constants.SUMO_EDGES_DICTIONARY_FILE, 'r')
    edgesDict = dict()
    
    line = edgesFile.readline()[0:-1]
    while line:
        array = line.split(constants.SEPARATOR)
        edgesDict[array[0]] = [array[1], array[2]]
        line = edgesFile.readline()[0:-1]
        
    edgesFile.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_DIJKSTRA))
    return edgesDict



"""
============================================================================================================================================
===                                                           GRAPH DICTIONARY MANAGEMENT (6)                                               ===
============================================================================================================================================
"""
def exportGraph(graphDict):
    """
    Writes the graph in an output file
    """
    Logger.info("{}Exporting graph...".format(constants.PRINT_PREFIX_DIJKSTRA))
    graphFile = open(constants.SUMO_GRAPH_FILE, 'w')
    
    for pair in graphDict.items():
        graphFile.write(pair[0])
        
        for valuePair in pair[1].items():
            graphFile.write(constants.SEPARATOR)
            graphFile.write(valuePair[0])
            graphFile.write(constants.SEPARATOR)
            graphFile.write(str(valuePair[1]))
            
        graphFile.write(constants.END_OF_LINE)
        
    graphFile.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_DIJKSTRA))
    
    
def importGraph():
    """
    Reads the network graph from an input graphFile
    """
    Logger.info("{}Importing graph...".format(constants.PRINT_PREFIX_DIJKSTRA))
    graphFile = open(constants.SUMO_GRAPH_FILE, 'r')
    graphDict = dict()
    
    line = graphFile.readline()[0:-1]
    while line:
        lineArray = line.split(constants.SEPARATOR)
        junctionNode = lineArray[0]
        graphDict[junctionNode] = dict()
        
        i = 1
        while i < len(lineArray):
            junctionSuccessor = lineArray[i]
            edgeLength = lineArray[i + 1]
            graphDict[junctionNode][junctionSuccessor] = float(edgeLength)
            i += 2

        line = graphFile.readline()[0:-1]
    
    graphFile.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_DIJKSTRA))
    return graphDict



"""
============================================================================================================================================
===                                     JUNCTIONS(4), EDGES(5) AND GRAPH(6) DICTIONARIES MANAGEMENT (5)                                    ===
============================================================================================================================================
"""
class NetworkHandler(xml.sax.ContentHandler):
    """
    SAX handler used for parsing a SUMO network file in order to build
    a graph, junctions and edges dictionary
    """
    def __init__(self, graphDict, junctionsDict, edgesDict, mtraci):
        xml.sax.ContentHandler.__init__(self)
        self.junctionFrom = ''
        self.junctionTo = ''
        self.edgeId = ''
        self.graphDict = graphDict
        self.junctionsDict = junctionsDict
        self.edgesDict = edgesDict
        self.mtraci = mtraci

    def startElement(self, name, attrs):
        if name == constants.XML_EDGE_ELEMENT:
            self.edgeId = str(attrs.get(constants.XML_EDGE_ID))
            
            if self.edgeId[0] != ':':
                self.junctionFrom = str(attrs.get(constants.XML_EDGE_FROM_JUNCTION))
                self.junctionTo = str(attrs.get(constants.XML_EDGE_TO_JUNCTION))
                
                # Junctions dictionary
                if not self.junctionFrom in self.junctionsDict:
                    self.junctionsDict[self.junctionFrom] = [set(), set()]
            
                if not self.junctionTo in self.junctionsDict:
                    self.junctionsDict[self.junctionTo] = [set(), set()]
            
                self.junctionsDict[self.junctionTo][0].add(self.edgeId)
                self.junctionsDict[self.junctionFrom][1].add(self.edgeId)
                
                # Edges dictionary
                self.edgesDict[self.edgeId] = [self.junctionFrom, self.junctionTo]
            
                # Graph
                if not self.edgeId in self.graphDict:
                    self.graphDict[self.edgeId] = dict()
                    
                    
        elif name == constants.XML_LANE_ELEMENT:
            laneId = attrs.get(constants.XML_LANE_ID)
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
                    
                    self.graphDict[self.edgeId][successorEdgeId] = length


def buildGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci):
    """
    Returns
    - A graph built as a dictionary as {Key=junctionId, Value=Dict as{Key=junction successor, Value=edge length between the junctions}
    - A junctions dictionary as {Key=junctionId, Value=[Set(edgesId predecessors of the junction), Set(edgesId successors of the junction)]
    - An edges dictionary as {Key=edgeId, Value=[junction predecessor, junction successor]
    """
    Logger.info("{}Building graph, junctions dictionary and edges dictionary...".format(constants.PRINT_PREFIX_DIJKSTRA))
    
    # Initializing variables
    graphDict = dict()
    junctionsDict = dict()
    edgesDict = dict()
        
    # Parsing XML network file
    parser = xml.sax.make_parser()
    parser.setContentHandler(NetworkHandler(graphDict, junctionsDict, edgesDict, mtraci))
    parser.parse(constants.SUMO_NETWORK_FILE)
        
    Logger.info("{}Done".format(constants.PRINT_PREFIX_DIJKSTRA))
    return graphDict, junctionsDict, edgesDict


def getGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci):
    """
    Returns the graph(*), junctions(**) and edges(***) dictionary. This one is obtained from a text file, updated if new map data are detected
    """
    if isDictionaryOutOfDate(constants.SUMO_JUNCTIONS_DICTIONARY_FILE, constants.SUMO_NETWORK_FILE) or isDictionaryOutOfDate(constants.SUMO_EDGES_DICTIONARY_FILE, constants.SUMO_NETWORK_FILE) or isDictionaryOutOfDate(constants.SUMO_GRAPH_FILE, constants.SUMO_NETWORK_FILE):
        graphDict, junctionsDict, edgesDict = buildGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci)
        exportGraph(graphDict)
        exportJunctionsDictionary(junctionsDict)
        exportEdgesDictionary(edgesDict)
    else:
        graphDict = importGraph()
        junctionsDict = importJunctionsDictionary()
        edgesDict = importEdgesDictionary()
    return graphDict, junctionsDict, edgesDict



"""
============================================================================================================================================
===                                                             GRAPH REQUESTS MANAGEMENT                                                        ===
============================================================================================================================================
"""
def getInformationHeader(informationType):
    """
    Returns the information header corresponding to the given information type
    """
    if informationType == constants.EDGES_COORDS:
        return  constants.EDGES_COORDS_RESPONSE_HEADER
    elif informationType == constants.EDGES_CONGESTION:
        return constants.EDGES_CONGESTION_RESPONSE_HEADER
    elif informationType == constants.EDGES_LENGTH:
        return constants.EDGES_LENGTH_RESPONSE_HEADER
    elif informationType == constants.EDGES_SUCCESSORS:
        return  constants.SUCCESSORS_RESPONSE_HEADER
    
    
def getInformationEnd(informationType):
    """
    Returns the information end corresponding to the given information type
    """
    if informationType == constants.EDGES_COORDS:
        return  constants.EDGES_COORDS_END
    elif informationType == constants.EDGES_LENGTH:
        return constants.EDGES_LENGTH_END
    elif informationType == constants.EDGES_CONGESTION:
        return constants.EDGES_CONGESTION_END
    elif informationType == constants.EDGES_SUCCESSORS:
        return  constants.SUCCESSORS_END
    
    
def getEdgeListSeparator(informationType):
    """
    Returns the edge list separator corresponding to the given information type
    """
    if informationType == constants.EDGES_SUCCESSORS:
        return constants.SUCCESSORS_LIST_SEPARATOR
    return constants.SEPARATOR
    
    
def getMaximumEdgesPerMessage(informationType):
    """
    Returns the maximum edges number per message corresponding to the given information type
    """
    if informationType == constants.EDGES_COORDS:
        return  constants.EDGES_NUMBER_PER_COORDS_MESSAGE
    elif informationType == constants.EDGES_LENGTH:
        return constants.EDGES_NUMBER_PER_LENGTH_MESSAGE
    elif informationType == constants.EDGES_CONGESTION:
        return constants.EDGES_NUMBER_PER_CONGESTION_MESSAGE
    elif informationType == constants.EDGES_SUCCESSORS:
        return  constants.SUCCESSORS_NUMBER_PER_MESSAGE


def sendEdgesDetails(edges, outputSocket, mtraci, informationType, dictionary, uniqueMsg):
    """
    Send information messages to Client, followed by and end message.
    The dictionary must be the edgesDictionary if an edges coordinates () request is specified
    The dictionary must be the graphDictionary if a graph () or successors () request is specified
    """    
    edgesNumber = 0
    edgesMsg = []
    
    informationHeader = getInformationHeader(informationType)
    informationEnd = getInformationEnd(informationType)
    edgeListSeparator = getEdgeListSeparator(informationType)
    maximumEdgesPerMsg = getMaximumEdgesPerMessage(informationType)
    
    # Adding specified header
    edgesMsg.append(informationHeader)
    
    for edge in edges:
        if edge[0] != ':':
            edgesMsg.append(edgeListSeparator)
            edgesMsg.append(edge)
            edgesMsg.append(constants.SEPARATOR)
            
            # EDGES COORDINATES
            if(informationType == constants.EDGES_COORDS):
                # Getting the two junctions ID linked with the current edge
                edgesJunctions = dictionary[edge]
                
                # Getting geographic coordinates of the two junctions center
                mtraci.acquire()
                predecessorCoords = traci.junction.getPosition(edgesJunctions[0])
                predecessorCoordsGeo = traci.simulation.convertGeo(predecessorCoords[0], predecessorCoords[1], False)
                successorCoords = traci.junction.getPosition(edgesJunctions[1])
                successorCoordsGeo = traci.simulation.convertGeo(successorCoords[0], successorCoords[1], False)
                mtraci.release()
    
                # Adding to the current message
                edgesMsg.append(str(predecessorCoordsGeo[0]))
                edgesMsg.append(constants.SEPARATOR)
                edgesMsg.append(str(predecessorCoordsGeo[1]))
                edgesMsg.append(constants.SEPARATOR)
                edgesMsg.append(str(successorCoordsGeo[0]))
                edgesMsg.append(constants.SEPARATOR)
                edgesMsg.append(str(successorCoordsGeo[1]))
            
            # EDGES LENGTH
            elif(informationType == constants.EDGES_LENGTH):
                lane = edge + '_0'
                
                # Getting edge length
                mtraci.acquire()
                length = traci.lane.getLength(lane)
                mtraci.release()
                
                # Adding to the current message
                edgesMsg.append(str(length))
            
            # EDGES CONGESTION
            elif(informationType == constants.EDGES_CONGESTION):
            
                #Calculating congestion
                mtraci.acquire()
                congestion = traci.edge.getLastStepOccupancy(edge)
                mtraci.release()
                
                # Adding to the current message
                edgesMsg.append(str(congestion))
            
            # EDGES SUCCESSORS (GRAPH)
            elif(informationType == constants.EDGES_SUCCESSORS):
                for edgeSucc in dictionary[edge]:
                    edgesMsg.append(edgeSucc)
                    edgesMsg.append(constants.SEPARATOR)
            
            
            edgesNumber += 1
            
            # Sending the message if this one has reached the maximum edges number per message
            if not uniqueMsg and edgesNumber == maximumEdgesPerMsg:
                edgesMsg.append(constants.END_OF_MESSAGE)
                strmsg = ''.join(edgesMsg)
                try:
                    outputSocket.send(strmsg.encode())
                except:
                    raise constants.ClosedSocketException("The listening socket has been closed")
                Logger.infoFile("{} Message sent: <{} edges information ({})>".format(constants.PRINT_PREFIX_GRAPH, maximumEdgesPerMsg, informationType))
                
                edgesNumber = 0
                edgesMsg[:] = []
                
                # Adding specified header
                edgesMsg.append(informationHeader)
        
        
    edgesMsg.append(constants.END_OF_MESSAGE)
    
    strmsg = ''.join(edgesMsg)
    try:
        outputSocket.send(strmsg.encode())
    except:
        raise constants.ClosedSocketException("The listening socket has been closed")
        Logger.infoFile("{} Message sent: <{} edges information ({})>".format(constants.PRINT_PREFIX_GRAPH, edgesNumber, informationType))
        
    
    if not uniqueMsg: 
        # Sending end of edges information messages
        edgesMsg[:] = []
    
        # Adding specified header
        edgesMsg.append(informationHeader)
        edgesMsg.append(edgeListSeparator)
    
        # Adding specified ending
        edgesMsg.append(informationEnd)
        edgesMsg.append(constants.END_OF_MESSAGE)
        
        strmsg = ''.join(edgesMsg)
        try:
            outputSocket.send(strmsg.encode())
        except:
            raise constants.ClosedSocketException("The listening socket has been closed")
        Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_GRAPH, strmsg))
    
    
def blockEdges(mtraci, edgesBlocked, idCpt, outputSocket):
    """
    Blocks edges in the SUMO simulated network by adding stopped vehicles
    """
    cpt = 1
    i = 0
    returnCode = constants.ACK_OK
    
    while i < len(edgesBlocked):
        try:
            edgeBlocked = edgesBlocked[i]
            i += 1
            nbLanesBlocked = int(edgesBlocked[i])
            i += 1
        except:
            sendAck(constants.PRINT_PREFIX_GRAPH, constants.GRAPH_INVALID_BLOCK_MSG, outputSocket)
            return cpt
        
        routeId = constants.BLOCKED_ROUTE_ID_PREFIX + str(idCpt + cpt)
        route = [edgeBlocked]
        laneIndex = 0
        laneBlocked = edgeBlocked + '_0'
        
        try:
            mtraci.acquire()
            traci.route.add(routeId, route)
            mtraci.release()
        except:
            mtraci.release()
            sendAck(constants.PRINT_PREFIX_GRAPH, constants.GRAPH_UNKNOWN_EDGE, outputSocket)
            return cpt
            
        while laneIndex != nbLanesBlocked - 1:
            vehicleId = constants.BLOCKED_VEHICLE_ID_PREFIX + str(idCpt + cpt)
            # TODO: improve, we can use the lane number by adding it to a dictionary when parsing the network
            try:
                mtraci.acquire()
                laneLength = traci.lane.getLength(laneBlocked)
                mtraci.release()
            except:
                mtraci.release()
                break
               
            laneLength /= 2.0
    
            mtraci.acquire()
            traci.vehicle.add(vehicleId, routeId, -2, 0, 0, 0, constants.DEFAULT_VEHICLE_TYPE)
            traci.vehicle.setStop(vehicleId, edgeBlocked, laneLength, laneIndex, 2147483646)
            mtraci.release()
            
            cpt += 1
            laneIndex += 1
            laneBlocked = laneBlocked[:-1] + str(laneIndex)
            
    sendAck(constants.PRINT_PREFIX_GRAPH, returnCode, outputSocket)
    return cpt

                
def unblockEdges(mtraci, edgesBlocked, outputSocket):
    """
    Unblocks edges in the SUMO simulated network by removing blocked vehicle previously added
    """
    returnCode = constants.ACK_OK
    
    for edgeBlocked in edgesBlocked:
        try:
            mtraci.acquire()
            blockedVehicles = traci.edge.getLastStepVehicleIDs(edgeBlocked)
            mtraci.release()
        except:
            mtraci.release()
            sendAck(constants.PRINT_PREFIX_GRAPH, constants.GRAPH_UNKNOWN_EDGE, outputSocket)
            return
            
        for blockedVehicle in blockedVehicles:
            if blockedVehicle.startswith(constants.BLOCKED_VEHICLE_ID_PREFIX):
                mtraci.acquire()
                traci.vehicle.remove(blockedVehicle)
                mtraci.release()
                
    sendAck(constants.PRINT_PREFIX_GRAPH, returnCode, outputSocket)
    
    
def sendEdgeId(mtraci, lon, lat, outputSocket):
    """
    Sends an edge ID calculated from geographic coordinates to the remote client
    """
    edgeId = getEdgeFromCoords(lon, lat, mtraci)
    
    routeCoordsMsg = []
    routeCoordsMsg.append(constants.EDGE_ID_RESPONSE_HEADER)
    routeCoordsMsg.append(constants.SEPARATOR)
    routeCoordsMsg.append(edgeId)
    routeCoordsMsg.append(constants.END_OF_MESSAGE)
        
    strmsg = ''.join(routeCoordsMsg)
    try:
        outputSocket.send(strmsg.encode())
    except:
        raise constants.ClosedSocketException("The listening socket has been closed")
    Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_GRAPH, strmsg))
        

def run(mtraci, inputSocket, outputSocket, eShutdown, eGraphReady, eManagerReady, graphDict, edgesDict):
    """
    See file description
    """
    bufferSize = 32768
    blockedIdCpt = 0
                        
    mtraci.acquire()
    edges = traci.edge.getIDList()
    mtraci.release()
    
    eGraphReady.set()
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
                        
                    Logger.infoFile("{} Message received: {}".format(constants.PRINT_PREFIX_GRAPH, cmd))
                        
                    #===== EDGES COORDINATES =====
                    # Send all edges coordinates to Client
                    if commandSize == 1 and command[0] == constants.ALL_EDGES_COORDS_REQUEST_HEADER:
                        sendEdgesDetails(edges, outputSocket, mtraci, constants.EDGES_COORDS, edgesDict, False)
                    
                    # Send the specified edges coordinates to Client    
                    elif commandSize > 1 and command[0] == constants.EDGES_COORDS_REQUEST_HEADER:
                        command.pop(0)
                        sendEdgesDetails(command, outputSocket, mtraci, constants.EDGES_COORDS, edgesDict, True)
                    
                    
                    #===== EDGES LENGTH =====
                    # Send all edges length to Client
                    elif commandSize == 1 and command[0] == constants.ALL_EDGES_LENGTH_REQUEST_HEADER:
                        sendEdgesDetails(edges, outputSocket, mtraci, constants.EDGES_LENGTH, None, False)
                    
                    # Send the specified edges length to Client    
                    elif commandSize > 1 and command[0] == constants.EDGES_LENGTH_REQUEST_HEADER:
                        command.pop(0)
                        sendEdgesDetails(command, outputSocket, mtraci, constants.EDGES_LENGTH, None, True)
                    
                    
                    #===== EDGES CONGESTION =====
                    # Send all edges congestion to Client
                    elif commandSize == 1 and command[0] == constants.ALL_EDGES_CONGESTION_REQUEST_HEADER:
                        sendEdgesDetails(edges, outputSocket, mtraci, constants.EDGES_CONGESTION, None, False)
                    
                    # Send the specified edges congestion to Client    
                    elif commandSize > 1 and command[0] == constants.EDGES_CONGESTION_REQUEST_HEADER:
                        command.pop(0)
                        sendEdgesDetails(command, outputSocket, mtraci, constants.EDGES_CONGESTION, None, True)
                    
                    
                    #===== EDGES SUCCESSORS (GRAPH) =====
                    # Send the graph dictionary to Client
                    elif commandSize == 1 and command[0] == constants.ALL_SUCCESSORS_REQUEST_HEADER:
                        sendEdgesDetails(edges, outputSocket, mtraci, constants.EDGES_SUCCESSORS, graphDict, False)
                    
                    # Send the specified edges successors with the corresponding distance to Client    
                    elif commandSize > 1 and command[0] == constants.SUCCESSORS_REQUEST_HEADER:
                        command.pop(0)
                        sendEdgesDetails(command, outputSocket, mtraci, constants.EDGES_SUCCESSORS, graphDict, True)
                        
                        
                    #===== BLOCK/UNBLOCK EDGES =====
                    # Block edges in the SUMO simulation
                    elif commandSize > 2 and command[0] == constants.BLOCK_EDGE_REQUEST_HEADER:
                        command.pop(0)
                        blockedIdCpt += blockEdges(mtraci, command, blockedIdCpt, outputSocket)
                        
                    # Unblock edges in the SUMO simulation
                    elif commandSize > 1 and command[0] == constants.UNBLOCK_EDGE_REQUEST_HEADER:
                        command.pop(0)
                        unblockEdges(mtraci, command, outputSocket)
                        
                        
                    #===== EDGE ID =====
                    # Sending an edge ID from geographic coordinates
                    elif commandSize == 3 and command[0] == constants.EDGE_ID_REQUEST_HEADER:
                        sendEdgeId(mtraci, command[1], command[2], outputSocket)
                        
                        
                    #===== UNKNOWN REQUEST =====
                    else:
                        Logger.warning("{}Invalid command received: {}".format(constants.PRINT_PREFIX_GRAPH, command))
                        sendAck(constants.PRINT_PREFIX_GRAPH, constants.INVALID_MESSAGE, outputSocket)

        except Exception as e:
            if e.__class__.__name__ == constants.CLOSED_SOCKET_EXCEPTION or e.__class__.__name__ == constants.TRACI_EXCEPTION:
                Logger.info("{}Shutting down current thread".format(constants.PRINT_PREFIX_GRAPH))
                sys.exit()
            else:
                Logger.error("{}A {} exception occurred:".format(constants.PRINT_PREFIX_GRAPH, e.__class__.__name__))
                Logger.exception(e)
