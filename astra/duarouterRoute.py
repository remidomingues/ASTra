#!/usr/bin/env python

"""
@file    Duarouterroute.py
@author  Remi Domingues
@date    07/06/2013

This script is used for resolving routing request using a Duarouter subprocess.

Routing procedure (processRouteRequest):
    Building a trip list from these edges using a junctions dictionary(*) in order to improve the routing accuracy
    Writing this list in an XML file
    Running Duarouter routing solver with this file as an input
    Parsing the resulting output XML file and getting the best route in
    Correcting the route
"""

import os, sys
import subprocess
import time
import constants
import traci
from xml.dom.minidom import parseString
from xml.dom.minidom import Document
from sharedFunctions import getJunctionId
from sharedFunctions import isJunction
from sharedFunctions import correctRoute


def removeRoutingFiles():
    """
    Removes the temporary files used for routing purposes
    """
    if os.path.isfile(constants.TRIPS_PATH):
        os.remove(constants.TRIPS_PATH)
        
    if os.path.isfile(constants.ROUTES_OUTPUT_PATH):
        os.remove(constants.ROUTES_OUTPUT_PATH)
        
    if os.path.isfile(constants.ROUTES_ALT_OUTPUT_PATH):
        os.remove(constants.ROUTES_ALT_OUTPUT_PATH)


def getTrips(edgeSrc, edgeDest, junctionsDict):
    """ 
    Returns a list of edges ID containing edges pairs.
    Each pair represent routing demand by a source and destination edge ID.
    This list is built from a source edge ID, a destination edge ID and a junction dictionary(*)
    """
    if isJunction(edgeSrc):
        src = list(junctionsDict[getJunctionId(edgeSrc)][0])[0]
    else:
        src = edgeSrc
        
    if isJunction(edgeDest):
        dest = list(junctionsDict[getJunctionId(edgeDest)][1])[0]
    else:
        dest = edgeDest
    
    return [src, dest]


def writeTrips(trips):    
    """
    Writes a list of edges ID (associated by pair (source edge ID / destination edge ID) in an XML file
    """
    i = 0
    doc = Document()
    root = doc.createElement(constants.XML_TRIPS_ELEMENT)
    doc.appendChild(root)
    
    while i < len(trips):
        trip = doc.createElement(constants.XML_TRIP_ELEMENT)
        trip.setAttribute(constants.XML_TRIP_ID_ATTRIBUTE, str(i))
        trip.setAttribute(constants.XML_TRIP_DEPART_ATTRIBUTE, str(0))
        trip.setAttribute(constants.XML_TRIP_FROM_ATTRIBUTE, trips[i])
        trip.setAttribute(constants.XML_TRIP_TO_ATTRIBUTE, trips[i + 1])
        root.appendChild(trip)
        i += 2
    
    xmlFile = open(constants.TRIPS_PATH, 'w')
    doc.writexml(xmlFile, '\t', '\t' '\n')
    doc.unlink()
    xmlFile.close()
    

def runDuarouterRouteSolver():
    """
    Starts a DUAROUTER subprocess in charge of resolving shortest path demands and wait for it
    """
    runTime = 0
    
    try:
        duarouterProcess = subprocess.Popen(constants.DUAROUTER_START_COMMAND, shell=True, stdout=sys.stdout)
    except:
        return constants.DUAROUTER_ERROR_LAUNCH
    
    # Wait until process terminates
    while duarouterProcess.poll() is None and runTime < constants.DUAROUTER_MAX_SLEEP_TIME:
        time.sleep(constants.DUAROUTER_SLEEP_TIME)
        runTime += constants.DUAROUTER_SLEEP_TIME
    
    if runTime >= constants.DUAROUTER_MAX_SLEEP_TIME:
        return constants.ROUTE_TIMEOUT_ERROR
    duarouterProcess.wait()
    return 0
    

def getBestRouteFromXml():
    """
    Parses an XML file and return the cheapest route (list of edges ID)
    """
    xmlFile = open(constants.ROUTES_ALT_OUTPUT_PATH, 'r')
    xmlData = xmlFile.read().encode("UTF-8")
    dom = parseString(xmlData)
    xmlFile.close()
    xmlRoutes = dom.getElementsByTagName(constants.XML_ROUTE_ELEMENT)
    minCost = -1
    
    if xmlRoutes:    
        for node in xmlRoutes:
            tmpCost = float(node.getAttribute(constants.XML_COST_ATTRIBUTE))
            if minCost == -1 or tmpCost < minCost:
                edges = node.getAttribute(constants.XML_EDGES_ATTRIBUTE)
                minCost = tmpCost
        edges = str(edges)
        route = edges.split(constants.SEPARATOR)
        return 0, route
    
    return constants.ROUTE_ERROR_CONNECTION, None


def processRouteRequest(src, destinations, junctionsDict):
    """
    - Transforms the source and destination coordinates to SUMO edges ID
    - Resolves the routing demand by using DUAROUTER
    - Sends the route (list of geographic coordinates) back to the client
    """
    route = []
    first = True

    for dest in destinations:
        removeRoutingFiles()
        trips = getTrips(src, dest, junctionsDict)
        writeTrips(trips)
        returnCode = runDuarouterRouteSolver()
        if returnCode != 0:
            return returnCode, None
        
        returnCode, tmpRoute = getBestRouteFromXml()
        if returnCode != 0:
            return returnCode, None
        tmpRoute = correctRoute(src, dest, tmpRoute)

        if first:
            first = False
        else:
            tmpRoute.pop(0)
        
        route.extend(tmpRoute)
        if len(tmpRoute) != 0:
            src = tmpRoute[-1]
    
    
    return 0, route
