#!/usr/bin/env python

"""
@file    SUMOFunctions.py
@author  Remi Domingues
@date    27/07/2013

This script contains some functions used in order to overcome some lack in TraCI functions,
or to the contrary avoid these call because of concurrent access to the TraCI resource.
"""

import os
import constants
from logger import Logger

def isJunction(edgeId):
    """
    Returns true if the edge belongs to a junction
    """
    return edgeId[0] == ':'


def getJunctionId(junctionEdgeId):
    """
    Returns a junction ID from a hidden lane ID
    """
    return junctionEdgeId[1:junctionEdgeId.index('_')]


def getEdgeFromLane(lane):
    """
    Returns the edge of the received lane
    """
    return lane.split('_')[0]


def getFirstLaneFromEdge(edgeId):
    """
    Returns the first lane ID from and edge ID given in parameter
    """
    return edgeId + "_0"


def getOppositeEdge(edge):
    """
    Returns the opposite edge ID of the edge ID given in parameter
    """
    if edge[0] == '-':
        return edge[1:]
    return '-' + edge


def isDictionaryOutOfDate(dictionaryFile, networkFile):
    """
    Returns true if the dictionary file doesn't exist or is older than the network file the dictionary is based on
    """
    if os.path.isfile(os.path.abspath(dictionaryFile)):
        return os.path.getmtime(os.path.abspath(networkFile)) > os.path.getmtime(os.path.abspath(dictionaryFile))
    return True


def correctRoute(edgeSrc, edgeDest, route):
    """
    Removes opposite edges in a route given in parameter, thanks to its source and destination edge ID
    """
    # Delete the first route element if this one is the opposite of the second
    if len(route) > 1 and (not(isJunction(edgeSrc)) and route[1] == getOppositeEdge(edgeSrc)) or isJunction(edgeSrc):
        route.pop(0)
        
        if len(route) > 1 and isJunction(edgeDest) or route[-2] == getOppositeEdge(edgeDest):
            route.pop()
        
    return route


def sendAck(printPrefix, code, outputSocket):
    """
    Send an acknowledge with a return code to the remote client
    """
    ack = []
    ack.append(constants.ACKNOWLEDGE_HEADER)
    ack.append(constants.SEPARATOR)
    ack.append(str(code))
    ack.append(constants.SEPARATOR)
    ack.append(constants.END_OF_MESSAGE)
        
    strmsg = ''.join(ack)
    try:
        outputSocket.send(strmsg.encode())
    except:
        raise constants.ClosedSocketException("The listening socket has been closed")
    Logger.infoFile("{} Message sent: {}".format(printPrefix, strmsg))
