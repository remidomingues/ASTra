#!/usr/bin/env python

"""
@file    dijkstraroute.py
@author  Remi Domingues
@date    23/07/2013

This script is used for resolving routing request using a dijkstra algorithm.

Routing procedure (processRouteRequest):
    Transforming the SUMO edges ID into junctions ID
    Using a dijkstra algorithm for processing the routing request (See dijkstra.py)
    Transforming the junctions ID list returned in an edges ID list
"""

import constants
import traci
from sharedFunctions import getJunctionId
from sharedFunctions import isJunction
from sharedFunctions import correctRoute
from sharedFunctions import getOppositeEdge
from logger import Logger
import dijkstra
    

def processRouteRequest(src, destinations, junctionsDict, graphDict):
    """
    - Transforms the source and destination coordinates to SUMO junctions ID
    - Resolves the routing demand by using a dijkstra algorithm
    - Sends the route (list of geographic coordinates) back to the client
    """
    route = []
    first = True
    
    if isJunction(src):
        #src become an edge predecessor of the src junction
        src = iter(junctionsDict[getJunctionId(src)][0]).next()
        srcJunction = True
    else:
        srcJunction = False
    
    for dest in destinations:

        if isJunction(dest):
            #dest become an edge successor of the dest junction
            dest = iter(junctionsDict[getJunctionId(dest)][1]).next()
            destJunction = True
        else:
            destJunction = False
        
        try:
            #Getting shortest path
            tmpRoute = dijkstra.shortestPath(graphDict, src, dest)
        except Exception as e:
            Logger.exception(e)
            return constants.ROUTE_ERROR_CONNECTION, None
        
        #Removing the first edge if it's the first routing and we find recurrence
        if first and srcJunction and tmpRoute:
            tmpRoute.pop(0)
        elif first and len(tmpRoute) > 1 and tmpRoute[1] == getOppositeEdge(tmpRoute[0]):
            tmpRoute.pop(0)
            
        #Removing the last edge if it was a junctions from start
        if destJunction and tmpRoute:
            tmpRoute.pop()

        #Removing the first edge of routings with via points in order to avoid two identical edges when extending road
        if not first:
            tmpRoute.pop(0)
            
        #Adding the calculated routing to the main routing
        route.extend(tmpRoute)
        first = False
        
        #Updating source edge for the next routing
        if tmpRoute:
            src = tmpRoute[-1]
        else:
            src = dest
        
    
    if len(route) > 1 and route[-2] == getOppositeEdge(route[-1]):
        route.pop()
            
    return 0, route
