#!/usr/bin/env python

"""
@file	SUMOFunctions.py
@author  Remi Domingues
@date	27/07/2013

This script contains some functions used in order to overcome some lack in TraCI functions,
or to the contrary avoid these call because of concurrent access to the TraCI resource.
"""

import os
import Constants

""" Returns true if the edge belongs to a junction """
def isJunction(edgeId):
	return edgeId[0] == ':'


""" Returns a junction ID from a hidden lane ID """
def getJunctionId(junctionEdgeId):
	return junctionEdgeId[1:junctionEdgeId.index('_')]


""" Returns the edge of the received lane """
def getEdgeFromLane(lane):
    return lane.split('_')[0]


""" Returns the first lane ID from and edge ID given in parameter"""
def getFirstLaneFromEdge(edgeId):
    return edgeId + "_0"


""" Returns the opposite edge ID of the edge ID given in parameter """
def getOppositeEdge(edge):
	if edge[0] == '-':
		return edge[1:]
	return '-' + edge


""" Returns true if the dictionary file doesn't exist or is older than the network file the dictionary is based on """
def isDictionaryOutOfDate(dictionaryFile, networkFile):
	if os.path.isfile(os.path.abspath(dictionaryFile)):
		return os.path.getmtime(os.path.abspath(networkFile)) > os.path.getmtime(os.path.abspath(dictionaryFile))
	return True


""" Removes opposite edges in a route given in parameter, thanks to its source and destination edge ID """
def correctRoute(edgeSrc, edgeDest, route):
	if(len(route) > 1):
		# Delete the first route element if this one is the opposite of the second
		if (not(isJunction(edgeSrc)) and route[1] == getOppositeEdge(edgeSrc)) or isJunction(edgeSrc):
			route.pop(0)
		
		if isJunction(edgeDest) or route[-2] == getOppositeEdge(edgeDest):
			route.pop()
		
	return route


""" Send an acknowledge with a return code to the remote client """
def sendAck(printPrefix, code, outputSocket):
    ack = []
    ack.append(Constants.ACKNOWLEDGE_HEADER)
    ack.append(Constants.SEPARATOR)
    ack.append(str(code))
    ack.append(Constants.SEPARATOR)
    ack.append(Constants.END_OF_MESSAGE)
        
    strmsg = ''.join(ack)
    try:
        outputSocket.send(strmsg.encode())
    except:
        raise Constants.ClosedSocketException("The listening socket has been closed")
    Logger.infoFile("{} Message sent: {}".format(printPrefix, strmsg))
