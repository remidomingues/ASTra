#!/usr/bin/env python

"""
@file	DuarouterRoute.py
@author  Remi Domingues
@date	07/06/2013

This script is used for resolving routing request using a Duarouter subprocess.

Routing procedure (processRouteRequest):
	Building a trip list from these edges using a junctions dictionary(*) in order to improve the routing accuracy
	Writing this list in an XML file
	Running Duarouter routing solver with this file as an input
	Parsing the resulting output XML file and getting the best route in
	Correcting the route
"""

import os, sys
import optparse
import subprocess
import socket
import time
import traceback
import ctypes
import Constants
import traci
from xml.dom.minidom import parseString
from xml.dom.minidom import Document
from SharedFunctions import getEdgeFromLane
from SharedFunctions import getJunctionId
from SharedFunctions import getOppositeEdge
from SharedFunctions import isJunction
from SharedFunctions import correctRoute


def removeRoutingFiles():
	if os.path.isfile(Constants.TRIPS_PATH):
		os.remove(Constants.TRIPS_PATH)
		
	if os.path.isfile(Constants.ROUTES_OUTPUT_PATH):
		os.remove(Constants.ROUTES_OUTPUT_PATH)
		
	if os.path.isfile(Constants.ROUTES_ALT_OUTPUT_PATH):
		os.remove(Constants.ROUTES_ALT_OUTPUT_PATH)


""" 
Returns a list of edges ID containing edges pairs.
Each pair represent routing demand by a source and destination edge ID.
This list is built from a source edge ID, a destination edge ID and a junction dictionary(*)
"""
def getTrips(edgeSrc, edgeDest, junctionsDict):
	if isJunction(edgeSrc):
		src = list(junctionsDict[getJunctionId(edgeSrc)][0])[0]
	else:
		src = edgeSrc
		
	if isJunction(edgeDest):
		dest = list(junctionsDict[getJunctionId(edgeDest)][1])[0]
	else:
		dest = edgeDest
	
	return [src, dest]


""" Writes a list of edges ID (associated by pair (source edge ID / destination edge ID) in an XML file """
def writeTrips(trips):	
	i = 0
	doc = Document()
	root = doc.createElement(Constants.XML_TRIPS_ELEMENT)
	doc.appendChild(root)
	
	while i < len(trips):
		trip = doc.createElement(Constants.XML_TRIP_ELEMENT)
		trip.setAttribute(Constants.XML_TRIP_ID_ATTRIBUTE, str(i))
		trip.setAttribute(Constants.XML_TRIP_DEPART_ATTRIBUTE, str(0))
		trip.setAttribute(Constants.XML_TRIP_FROM_ATTRIBUTE, trips[i])
		trip.setAttribute(Constants.XML_TRIP_TO_ATTRIBUTE, trips[i + 1])
		root.appendChild(trip)
		i += 2
	
	xmlFile = open(Constants.TRIPS_PATH, 'w')
	doc.writexml(xmlFile, '\t', '\t' '\n')
	doc.unlink()
	xmlFile.close()
	

""" Starts a DUAROUTER subprocess in charge of resolving shortest path demands and wait for it """
def runDuarouterRouteSolver():
	runTime = 0
	
	try:
		duarouterProcess = subprocess.Popen(Constants.DUAROUTER_START_COMMAND, shell=True, stdout=sys.stdout)
	except:
		return Constants.DUAROUTER_ERROR_LAUNCH
	
	# Wait until process terminates
	while duarouterProcess.poll() is None and runTime < Constants.DUAROUTER_MAX_SLEEP_TIME:
		time.sleep(Constants.DUAROUTER_SLEEP_TIME)
		runTime += Constants.DUAROUTER_SLEEP_TIME
	
	if runTime >= Constants.DUAROUTER_MAX_SLEEP_TIME:
		return Constants.ROUTE_TIMEOUT_ERROR
	duarouterProcess.wait()
	return 0
	

""" Parses an XML file and return the cheapest route (list of edges ID) """
def getBestRouteFromXml():
	xmlFile = open(Constants.ROUTES_ALT_OUTPUT_PATH, 'r')
	xmlData = xmlFile.read().encode("UTF-8")
	dom = parseString(xmlData)
	xmlFile.close()
	xmlRoutes = dom.getElementsByTagName(Constants.XML_ROUTE_ELEMENT)
	
	if xmlRoutes:	
		edges = ''
		for node in xmlRoutes:
			tmpCost = float(node.getAttribute(Constants.XML_COST_ATTRIBUTE))
			if not(edges) or tmpCost < minCost:
				edges = node.getAttribute(Constants.XML_EDGES_ATTRIBUTE)
				minCost = tmpCost
		edges = str(edges)
		route = edges.split(Constants.SEPARATOR)
		return 0, route
	
	return Constants.ROUTE_ERROR_CONNECTION, None


"""
- Transforms the source and destination coordinates to SUMO edges ID
- Resolves the routing demand by using DUAROUTER
- Sends the route (list of geographic coordinates) back to the client
"""
def processRouteRequest(src, destinations, junctionsDict):
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
		if returnCode !=0:
			return returnCode, None
		tmpRoute = correctRoute(src, dest, tmpRoute)

		if first:
			first = False
		else:
			tmpRoute.pop(0)
		
		route.extend(tmpRoute)
		if len(route) != 0:
			src = tmpRoute[-1]
	
	
	return 0, route
