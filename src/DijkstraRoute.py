#!/usr/bin/env python

"""
@file	Dijkstraroute.py
@author  Remi Domingues
@date	23/07/2013

This script is used for resolving routing request using a Dijkstra algorithm.

Routing procedure (processRouteRequest):
	Transforming the SUMO edges ID into junctions ID
	Using a Dijkstra algorithm for processing the routing request (See Dijkstra.py)
	Transforming the junctions ID list returned in an edges ID list
"""

import os, sys
import optparse
import subprocess
import socket
import time
import traceback
import ctypes
import constants
import traci
from sharedFunctions import getEdgeFromLane
from sharedFunctions import getJunctionId
from sharedFunctions import isJunction
from sharedFunctions import correctRoute
from logger import Logger
import dijkstra
	

"""
- Transforms the source and destination coordinates to SUMO junctions ID
- Resolves the routing demand by using a Dijkstra algorithm
- Sends the route (list of geographic coordinates) back to the client
"""
def processRouteRequest(src, destinations, junctionsDict, graphDict, edgesDict):
	route = []
	first = True
	
	if isJunction(src):
		src = iter(junctionsDict[getJunctionId(src)][0]).next()
	
	for dest in destinations:
		if isJunction(dest):
			dest = iter(junctionsDict[getJunctionId(dest)][1]).next()
		
		try:
			tmpRoute = dijkstra.shortestPath(graphDict, src, dest)
		except Exception as e:
			Logger.exception(e)
			return constants.ROUTE_ERROR_CONNECTION, None
		
		if isJunction(src):
			try:
				tmproute.pop(0)
			except:
				pass
			
		if isJunction(dest):
			try:
				tmproute.pop()
			except:
				pass
			
		tmpRoute = correctRoute(src, dest, tmpRoute)
		route.extend(tmpRoute)
		
		if len(tmpRoute) != 0:
			src = tmpRoute[-1]
		else:
			src = dest
		
	
	#route = getRouteFromJunctions(junctionsRoute, junctionsDict)
	return 0, route
