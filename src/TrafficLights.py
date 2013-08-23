#!/usr/bin/env python

"""
@file    trafficLights.py
@author  Remi Domingues
@date    24/06/2013

(0) Traffic lights COORDINATES request: COO tllId1 ... tllIdN
        If no traffic light ID is specified, the geographic coordinates of every traffic light will be sent

(1) Traffic lights COORDINATES response: COO tllId1 lon1 lat1 ... tllIdN lonN latN (N in [0-X] if all traffic lights were requested (See constants for X value))
        If ALL TRAFFIC LIGHTS were requested, these messages are followed by an end message (response): TLL END

(2) Traffic lights DETAILS request: GET tmsLogin tllId zoom answerDetailsLevel
        The zoom is an integer between 100 (min) and 100 000 (max). 100 means a 100% zoom, the entire map can fit in the screen.
        answerDetailsLevel = 0 => (3)
        answerDetailsLevel = 1 => (4)
        
(3) SHORT traffic lights DETAILS answer: DET tmsLogin screenshotPath currentPhaseIndex nextSwitchTime
        The screenshotPath is an absolute path of a PNG file centered on a junction which has a traffic light
        The current phase index is an integer between 0 and N
        nextSwitchTime is a value in milliseconds. This one refers to the next traffic light state change
        Note: if the operating system the server is running on is based on POSIX, the screenshotPath will be equal to null
        
(4) FULL traffic lights DETAILS answer: DET tmsLogin screenshotPath currentPhaseIndex nextSwitchTime state0 duration0 ... stateN durationN
        See (3)
        A phase is defined by a state and a duration. The phases order defines the traffic light behaviour
            - State: string which is equals to the number of lanes the traffic light manage
            - Duration: time in milliseconds for which a state will be displayed. The next state is then displayed
        
(5) SHORT SET traffic lights details request: SET tllId currentPhaseIndex
        tllId: SUMO traffic light id
        currentPhaseIndex: SUMO index corresponding to the current traffic light phase in the complete phases definition

(6) FULL SET traffic lights details request: SET tllId currentPhaseIndex state0 duration0 ... stateN durationN
        For detailed parameters pieces of information, see (5) and (4)
        
(7) ACKNOWLEDGE or ERROR response after a SET((5) or (6)) request: ACK returnCode
        OK = 0
        Invalid phase index = 1
        Invalid phase state = 2
        Invalid phase duration = 3
        
(8) ERROR response when an invalid request is received : ERR 40

(9) Traffic lights dictionary:
        - Key = SUMO edge ID
        - Value = SUMO traffic light ID which is located at the end of the edge
    Note: this dictionary does not contain every SUMO edges ID, but only the ones which end with a traffic light
"""

import os, sys
import socket
import constants
import traci
import time
import traceback
from sharedFunctions import isJunction
from sharedFunctions import getEdgeFromLane
from sharedFunctions import getFirstLaneFromEdge
from sharedFunctions import isDictionaryOutOfDate
from sharedFunctions import sendAck
from logger import Logger


"""
============================================================================================================================================
===                                                   TRAFFIC LIGHTS DICTIONARY MANAGEMENT (9)                                           ===
============================================================================================================================================
"""
""" Returns a dictionary as {Key=edgeId, Value=traffic light ID which is located at the end of the edge} """
def buildTrafficLightsDictionary(mtraci):
    Logger.info("{}Building traffic lights dictionary...".format(constants.PRINT_PREFIX_TLL))

    previousEdge = ''
    tllDict = dict()
    
    mtraci.acquire()
    tlls = traci.trafficlights.getIDList()
    mtraci.release()
    
    for tll in tlls:
        mtraci.acquire()
        controlledLanes = traci.trafficlights.getControlledLanes(tll)
        mtraci.release()
        
        for lane in controlledLanes:
            currentEdge = getEdgeFromLane(lane)
            if currentEdge != previousEdge:
                tllDict[currentEdge] = tll
                previousEdge = currentEdge
            
    Logger.info("{}Done".format(constants.PRINT_PREFIX_TLL))
    return tllDict


""" Writes the traffic lights dictionary in an output file """
def exportTrafficLightsDictionary(tllDict):
    Logger.info("{}Exporting traffic lights dictionary...".format(constants.PRINT_PREFIX_TLL))
    file = open(constants.SUMO_TLL_DICTIONARY_FILE, 'w')
    
    for pair in tllDict.items():
        file.write(pair[0])
        file.write(constants.SEPARATOR)
        file.write(pair[1])
        file.write(constants.END_OF_LINE)
        
    file.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_TLL))
    
    
""" Reads the traffic lights dictionary from an input file """
def importTrafficLightsDictionary():
    Logger.info("{}Importing traffic lights dictionary...".format(constants.PRINT_PREFIX_TLL))
    file = open(constants.SUMO_TLL_DICTIONARY_FILE, 'r')
    tllDict = dict()
    
    line = file.readline()[0:-1]
    while line:
        array = line.split(constants.SEPARATOR)
        tllDict[array[0]] = array[1]
        line = file.readline()[0:-1]
    
    file.close()
    Logger.info("{}Done".format(constants.PRINT_PREFIX_TLL))
    return tllDict


""" Returns the traffic lights dictionary(*). This one is obtained from a text file, updated if new map data are detected """
def getTrafficLightsDictionary(mtraci):
    if isDictionaryOutOfDate(constants.SUMO_TLL_DICTIONARY_FILE, constants.SUMO_NETWORK_FILE):
        tllDict = buildTrafficLightsDictionary(mtraci)
        exportTrafficLightsDictionary(tllDict)
    else:
        tllDict = importTrafficLightsDictionary()
    return tllDict



"""
============================================================================================================================================
===                                               TRAFFIC LIGHTS MANAGEMENT FOR PRIORITY VEHICLES                                        ===
============================================================================================================================================
"""
""" Returns a traffic light state where green current states are passed to yellow and yellow to red. Priority lane state does not change """
def getOrangeState(currentState, prioLaneIndex):
    orangeState = []
    for i in range(0, len(currentState)):
        if i == prioLaneIndex:
            orangeState.append(currentState[i])
        elif currentState[i] == constants.YELLOW:
            orangeState.append(constants.RED)
        elif currentState[i] == constants.GREEN or currentState[i] == constants.GREEN_PRIO:
            orangeState.append(constants.YELLOW)
        else:
            orangeState.append(currentState[i])
    return ''.join(orangeState)


""" Returns a list containing each unique item of the list given in parameter. The order does not change """
def removeDoubles(doubleList):
    uniqueList = []
    tmpItem = None
    for item in doubleList:
        if item != tmpItem:
            uniqueList.append(item)
            tmpItem = item
    
    return uniqueList


"""
Returns the unique ordered (according to the hidden lane index calculated from this order) lanes 
controlled by the traffic light given in parameter
"""
def getUniqueInputLanes(mtraci, tllId):
    mtraci.acquire()
    inputLanes = traci.trafficlights.getControlledLanes(tllId)
    mtraci.release()
    
    return removeDoubles(inputLanes)


"""
Returns the index of the hidden lane defined by an inLane (going in the junction) and an outLane
(leaving from the junction). The unique controlled (in) lanes list is used for this purpose
"""
def getHiddenLaneIndex(mtraci, inputLanes, inLane, outLane):
    i = 0
    hiddenLaneIndex = 0
    found = False
    
    while i < len(inputLanes) and not found:
        lane = inputLanes[i]
        
        mtraci.acquire()
        tmpLinks = traci.lane.getLinks(lane)
        mtraci.release()
        
        if lane == inLane:
            j = 0
            tmpLinksLength = len(tmpLinks)
            while j < tmpLinksLength and not found:
                 if tmpLinks[j][0] == outLane:
                     hiddenLaneIndex += j
                     found = True
                 j += 1
        else:
            hiddenLaneIndex += len(tmpLinks)
        i += 1
        
    return hiddenLaneIndex


"""
Restores the previous phase definition for a traffic light given in parameter.
This phase definition must be stored in the yellowTllDict from which it will be removed.
The new current phase must also be specified """
def restorePreviousPhaseDefinition(mtraci, yellowTllDict, tllId, greenPhaseIndex):
    previousPhaseDetails = yellowTllDict[tllId]
            
    setCompletePhasesDefinition(tllId, previousPhaseDetails, greenPhaseIndex, mtraci)
    
    del yellowTllDict[tllId]
                

""" Returns the phase index matching with a green ('g' or 'G') state for the specified hidden lane """
def getGreenPhaseIndex(phasesDetails, hiddenLaneIndex):
    k = 0
    found = False
    while k < len(phasesDetails) and not found:
        state = phasesDetails[k]
        if state[hiddenLaneIndex] == 'g' or state[hiddenLaneIndex] == 'G':
            phaseIndex = k/2
            found = True
        else:
            k+=2
    return phaseIndex


"""
Returns the (out) lane linked with the (in) lane which match with the (out) edge received
If no lane match, the algorithm will use as inLane the next lane on the inEdge.
If no lane match and if there is no other lane available on the inEdge, -1 will be returned
"""
def getOutLane(mtraci, inLane, outEdge):
    found = False
    laneIndex = 0
    laneOutIndex = 0
    
    while not found:
        try:
            mtraci.acquire()
            lanesOut = traci.lane.getLinks(inLane)
            mtraci.release()
        except:
            mtraci.release()
            return -1
        
        while laneOutIndex < len(lanesOut) and not found:
            outLane = lanesOut[laneOutIndex][0]
            if getEdgeFromLane(outLane) == outEdge:
                found = True
            else:
                laneOutIndex += 1
        
        if not found:
            laneIndex += 1
            laneOutIndex = 0
            inLane = inLane[:len(inLane) - 1] + str(laneIndex)
            
    return outLane


"""
Changes a traffic light current phase index in order to set it green for the priority lane
or sets a global before-green state (See getOrangeState())
The priority lane is the hidden lane linking the inLane and the outLane
"""
def changeState(mtraci, tllId, inLane, outLane, setState, yellowTllDict):
    if tllId in yellowTllDict:
        isOrange = True
    else:
        isOrange = False
        
    if setState == constants.SET_YELLOW and isOrange:
        return
    
    lanes = getUniqueInputLanes(mtraci, tllId)
    hiddenLaneIndex = getHiddenLaneIndex(mtraci, lanes, inLane, outLane)
    
    mtraci.acquire()
    completeDefinition = traci.trafficlights.getCompleteRedYellowGreenDefinition(tllId)
    currentPhaseIndex = traci.trafficlights.getPhase(tllId)
    currentTime = traci.simulation.getCurrentTime()
    nextSwitchTime = traci.trafficlights.getNextSwitch(tllId)
    mtraci.release()

    nextSwitchTime = nextSwitchTime - currentTime
    nextSwitchStep = nextSwitchTime / 1000.0 / constants.SUMO_SIMULATION_STEP_TIME
    phasesDetails = getPhasesDetails(completeDefinition)
    currentState = phasesDetails[currentPhaseIndex * 2]
    
    #If the traffic light the given edge which ends with does not contain a signal for the lane the vehicle will go to 
    if len(currentState) == hiddenLaneIndex:
        return
    
    #The traffic light is gren for the priority lane, and the time but the time for the priority vehicle to reach the junction is unsufficient
    if (setState == constants.SET_YELLOW or setState == constants.SET_GREEN) and not isOrange and ((currentState[hiddenLaneIndex] == 'g' or currentState[hiddenLaneIndex] == 'G')):
        if nextSwitchStep - constants.YELLOW_STEPS_ANTICIPATION < 0:
            #Logger.info(tllId + " is GREEN => reinitializing timer")
            #Reset the current phase timer
            mtraci.acquire()
            traci.trafficlights.setPhase(tllId, currentPhaseIndex)
            mtraci.release()
        #else:
        #    Logger.info(tllId + " is GREEN => nothing to do")
        
    elif setState == constants.SET_YELLOW:
        #Logger.info(tllId + " has been set to YELLOW temporary phase")
        #Saving the current phase state and duration
        yellowTllDict[tllId] = phasesDetails
        newState = getOrangeState(currentState, hiddenLaneIndex)
        
        orangePhasesDetails = list(phasesDetails)
        orangePhasesDetails[currentPhaseIndex * 2] = newState
        orangePhasesDetails[currentPhaseIndex * 2 + 1] = constants.YELLOW_STEPS_ANTICIPATION * 1000
        
        #Setting a temporary current phase in order to prepare the junction for passing green the priority lane
        setCompletePhasesDefinition(tllId, orangePhasesDetails, currentPhaseIndex, mtraci)
        
    #We set the priority lane green only if (the associated traffic light is not green and the current state will change before the priority car crosses the junction) 
    elif setState == constants.SET_GREEN and not((currentState[hiddenLaneIndex] == 'g' or currentState[hiddenLaneIndex] == 'G') and nextSwitchStep - constants.GREEN_STEPS_ANTICIPATION > 0):
        #Logger.info(tllId + " has been set to GREEN")
        greenPhaseIndex = getGreenPhaseIndex(phasesDetails, hiddenLaneIndex)

        if isOrange:
            restorePreviousPhaseDefinition(mtraci, yellowTllDict, tllId, greenPhaseIndex)
        else:
            mtraci.acquire()
            traci.trafficlights.setPhase(tllId, greenPhaseIndex)
            mtraci.release()
    #else:
    #    Logger.info(tllId + " is GREEN => nothing to do")


"""
Determines for each priority vehicle which are the next traffic lights and the distance to these ones.
Regarding to the vehicle current speed and the time elapsed during a SUMO simulation step,
the traffic light hidden lane the vehicle will cross is set to green or the junction to a temporary orange state
if the vehicle is close enough and if the concurrent access between priority vehicles allows it.
Note: the following algorithm could be highly improved by exploring every edges the vehicle will use
    at the beginning, but then only explore the edges which are now in the vehicle scope because of
    the last step progression. Two list, one for the orange look up and one for the green, would be used
    for this purpose.
Note 2: The main complexity of this algorithm resides in the lack of TraCI functionalities in order to get
    retrieve the state of a hidden lane linking two lanes. This could also be highly improved by using a
    dictionary built when starting the software.
"""
def updateTllForPriorityVehicles(mtraci, priorityVehicles, mPriorityVehicles, tllDict, yellowTllDict, managedTllDict):
    mPriorityVehicles.acquire()
    managedTlls = [];
    length = len(priorityVehicles)
    
    #Checking if the next traffic light has to be changed for each priority vehicleId in the simulation
    for prioVehIndex in range(0, length):
        vehicleId = priorityVehicles[prioVehIndex]
        
        #Getting route and position information for the current priority vehicleId
        mtraci.acquire()
        route = traci.vehicle.getRoute(vehicleId)
        currentLane = traci.vehicle.getLaneID(vehicleId)
        mtraci.release()
        
        if currentLane != '' and not isJunction(currentLane):
            #Getting speed information for space and time predictions
            mtraci.acquire()
            lanePosition = traci.vehicle.getLanePosition(vehicleId)
            laneLength = traci.lane.getLength(currentLane)
            speed = traci.vehicle.getSpeed(vehicleId)
            mtraci.release()
            
            currentEdge = getEdgeFromLane(currentLane)
            currentEdgeIndex = route.index(currentEdge)
            remainingLength = laneLength - lanePosition
            edge = currentEdge
            lane = currentLane
            edgeIndex = currentEdgeIndex

            #Browsing the next edges the vehicleId will go to            
            while remainingLength <= constants.YELLOW_LENGTH_ANTICIPATION and edgeIndex < len(route) - 1:
                #If the current edge (the vehicleId is not) ends with a traffic light
                if edge in tllDict:
                    #If the car is close enough for the traffic light to become green
                    if remainingLength <= constants.GREEN_LENGTH_ANTICIPATION:
                        setState = constants.SET_GREEN
                    #If the car is close enough for the traffic light to prepare (temporary state) becoming green
                    elif not tllDict[edge] in yellowTllDict:
                        setState = constants.SET_YELLOW
                    else:
                        managedTlls.append(tllDict[edge])
                        setState = constants.IGNORE
                    
                    #Calculating the next lane the vehicleId will go to
                    outEdge = route[edgeIndex + 1]
                    
                    outLane = getOutLane(mtraci, lane, outEdge)
                    
                    #Calling for a traffic light change
                    if outLane != -1 and setState != constants.IGNORE:
                        tllId = tllDict[edge]
                        managedTlls.append(tllId)
                        if (tllId in managedTllDict and managedTllDict[tllId][1] > remainingLength) or not tllId in managedTllDict:
                                managedTllDict[tllId] = (vehicleId, remainingLength)
                                changeState(mtraci, tllId, lane, outLane, setState, yellowTllDict)

                    tllFound = True

                edgeIndex += 1
                if edgeIndex < len(route):
                    edge = route[edgeIndex]
                    lane = getFirstLaneFromEdge(edge)
                    
                    mtraci.acquire()
                    laneLength = traci.lane.getLength(lane)
                    mtraci.release()
                    
                    remainingLength += laneLength
            
            #Removing the tlls which have been crossed from the managedTllDict    
            for key in managedTllDict.keys():
                if managedTllDict[key][0] == vehicleId and not key in managedTlls:
                    del managedTllDict[key]
                    
            managedTlls[:] = []
    
    mPriorityVehicles.release()



"""
============================================================================================================================================
===                                                   TRAFFIC LIGHTS DYNAMIC CONFIGURATION                                               ===
============================================================================================================================================
"""
""" Returns the absolute path of a traffic light screenshot from a tms login """
def getScreenshotAbsolutePath(login):
    return constants.SCREEN_DIRECTORY + "/" + constants.SCREENSHOT_FILE_NAME.format(login)


""" Returns the geographic coordinates of a traffic light from its SUMO ID """
def getTrafficLightCoordinates(trafficId, mtraci):
    mtraci.acquire()
    coords = traci.junction.getPosition(trafficId)
    coordsGeo = traci.simulation.convertGeo(coords[0], coords[1], False)
    mtraci.release()
    
    return coordsGeo


""" Returns a list according to the following pattern: state0 duration0 state1 duration1 ... stateN durationN from a complete phases definition"""
def getPhasesDetails(completePhasesDefinition):
    i = 6
    fieldSeparator = '\n'
    keyValueSeparator = ':'
    strPhasesDefinition = repr(completePhasesDefinition[0])
    arrayDefinition = strPhasesDefinition.split(fieldSeparator)
    phasesDetails = []
    while i < len(arrayDefinition):
        duration = arrayDefinition[i].split(keyValueSeparator)[1][1:]
        i += 3
        state = arrayDefinition[i].split(keyValueSeparator)[1][1:]
        i+= 2
        phasesDetails.append(state)
        phasesDetails.append(duration)
        
    return phasesDetails


"""
Returns a string matching with the SUMO complete phases definition.
A list according to the following pattern is required:
state0 duration0 state1 duration1 ... stateN durationN
"""
def setCompletePhasesDefinition(tllId, phasesDetails, currentPhaseIndex, mtraci):
    i = 0
    phasesDefinition = []
    
    while i < len(phasesDetails):
        state = phasesDetails[i]
        i += 1
        duration = int(phasesDetails[i])
        
        if duration < constants.TLL_MIN_PHASE_DURATION:
            return constants.TLL_PHASE_DURATION_ERROR
        
        i += 1
        mtraci.acquire()
        phase = traci.trafficlights.Phase(duration, duration, duration, state)
        mtraci.release()
        phasesDefinition.append(phase)
    
    phaseDuration = int(phasesDetails[currentPhaseIndex * 2 + 1]) / 1000
    
    mtraci.acquire()
    logicPhasesDefinition = traci.trafficlights.Logic("", 0, 0, currentPhaseIndex, phasesDefinition)
    traci.trafficlights.setCompleteRedYellowGreenDefinition(tllId, logicPhasesDefinition)
    traci.trafficlights.setPhaseDuration(tllId, phaseDuration)
    mtraci.release()
    
    return constants.ACK_OK
    

""" Sends traffic lights position messages(*) to the remote client using an output socket """
def sendTrafficLightsPosition(trafficLightsId, mtraci, outputSocket, uniqueMsg):
    trafficLightsNumber = 0
    trafficLightsPos = []
    trafficLightsPos.append(constants.TLL_COORDS_REQUEST_HEADER)
    
    #Requires 32768 bytes buffer: sending traffic lights per packet of 500
    for trafficId in trafficLightsId:
        tllCoords = getTrafficLightCoordinates(trafficId, mtraci)
        
        trafficLightsPos.append(constants.SEPARATOR)
        trafficLightsPos.append(trafficId)
        trafficLightsPos.append(constants.SEPARATOR)
        trafficLightsPos.append(str(tllCoords[0]))
        trafficLightsPos.append(constants.SEPARATOR)
        trafficLightsPos.append(str(tllCoords[1]))
        
        trafficLightsNumber += 1
        
        if not uniqueMsg and trafficLightsNumber == constants.TLL_NUMBER_PER_MESSAGE:
            trafficLightsPos.append(constants.SEPARATOR)
            trafficLightsPos.append(constants.END_OF_MESSAGE)
            strmsg = ''.join(trafficLightsPos)
            try:
                outputSocket.send(strmsg.encode())
            except:
                raise constants.ClosedSocketException("The listening socket has been closed")
            Logger.infoFile("{} Message sent: <{} traffic lights positions>".format(constants.PRINT_PREFIX_TLL, constants.TLL_NUMBER_PER_MESSAGE))
            trafficLightsNumber = 0
            trafficLightsPos[:] = []
            trafficLightsPos.append(constants.TLL_COORDS_REQUEST_HEADER)
    
    
    trafficLightsPos.append(constants.END_OF_MESSAGE)
    
    strmsg = ''.join(trafficLightsPos)
    try:
        outputSocket.send(strmsg.encode())
    except:
        raise constants.ClosedSocketException("The listening socket has been closed")
    Logger.infoFile("{} Message sent: <{} traffic lights positions>".format(constants.PRINT_PREFIX_TLL, trafficLightsNumber))
    

    if not uniqueMsg:
        #Sending end of traffic lights position messages
        trafficLightsPos[:] = []
        trafficLightsPos.append(constants.TLL_COORDS_REQUEST_HEADER)
        trafficLightsPos.append(constants.SEPARATOR)
        trafficLightsPos.append(constants.TLL_POS_END)
        trafficLightsPos.append(constants.END_OF_MESSAGE)
        
        strmsg = ''.join(trafficLightsPos)
        try:
            outputSocket.send(strmsg.encode())
        except:
            raise constants.ClosedSocketException("The listening socket has been closed")
        Logger.infoFile("{} Message sent: {}".format(constants.PRINT_PREFIX_TLL, strmsg))
    
    
""" Saves a screenshot centered on the specified junction from SUMO GUI """
def saveTrafficLightScreenshot(login, tllId, zoom, mtraci):
    tllCoords = getTrafficLightCoordinates(tllId, mtraci)
    
    filePath = getScreenshotAbsolutePath(login)
    
    mtraci.acquire()
    try:
        tll2DCoords = traci.simulation.convertGeo(tllCoords[0], tllCoords[1], True)
        viewList = traci.gui.getIDList()
    except:
        mtraci.release()
        raise
    mtraci.release()
    
    viewId = viewList[len(viewList) - 1]
    
    mtraci.acquire()
    try:
        traci.gui.setOffset(viewId, tll2DCoords[0], tll2DCoords[1])
        traci.gui.setZoom(viewId, zoom)
        traci.gui.screenshot(viewId, filePath)
    except:
        mtraci.release()
        raise
    mtraci.release()
    
    return filePath


""" Sends a traffic lights details answer(***) to the remote client using an output socket """
def sendTrafficLightsDetails(tllId, tmsLogin, screenshotPath, outputSocket, mtraci, detailsLevel):
    #DTL tmsLogin screenshotPath currentPhaseIndex nextSwitchTime state0 duration0 ... stateN durationN
    mtraci.acquire()
    try:
        currentPhaseIndex = traci.trafficlights.getPhase(tllId)
        currentTime = traci.simulation.getCurrentTime()
        nextSwitchTime = traci.trafficlights.getNextSwitch(tllId)
        completePhasesDefinition = traci.trafficlights.getCompleteRedYellowGreenDefinition(tllId)
    except:
        mtraci.release()
        raise
    mtraci.release()
    
    nextSwitchTime = nextSwitchTime - currentTime
    phasesDetails = getPhasesDetails(completePhasesDefinition)
    
    details = []
    details.append(constants.TLL_GET_DETAILS_RESPONSE_HEADER)
    details.append(constants.SEPARATOR)
    details.append(tmsLogin)
    details.append(constants.SEPARATOR)
    details.append(screenshotPath)
    details.append(constants.SEPARATOR)
    details.append(str(currentPhaseIndex))
    details.append(constants.SEPARATOR)
    details.append(str(nextSwitchTime))
    
    if detailsLevel == 1:
        i = 0
        while i < len(phasesDetails):
            details.append(constants.SEPARATOR)
            details.append(phasesDetails[i])
            i += 1
            details.append(constants.SEPARATOR)
            details.append(phasesDetails[i])
            i += 1

    details.append(constants.END_OF_MESSAGE)
    
    strmsg = ''.join(details)
    try:
        outputSocket.send(strmsg.encode())
    except:
        raise constants.ClosedSocketException("The listening socket has been closed")


""" Gets a traffic lights details information from SUMO, then sends them(***) to the remote client by an output socket """
def processGetDetailsRequest(tmsLogin, tllId, zoom, outputSocket, mtraci, detailsLevel):
    if not constants.POSIX_OS:
        screenshotPath = saveTrafficLightScreenshot(tmsLogin, tllId, zoom, mtraci)
    else:
        screenshotPath = 'null'
    sendTrafficLightsDetails(tllId, tmsLogin, screenshotPath, outputSocket, mtraci, detailsLevel)
    

""" Gets a traffic lights details from """
def processSetDetailsRequest(command, commandSize, outputSocket, mtraci):
    #SET tllId currentPhaseIndex state0 duration0 ... stateN durationN
    returnCode = constants.ACK_OK
    command.pop(0)
    tllId = command.pop(0)
    currentPhaseIndex = int(command.pop(0))

    #Setting current phase index
    mtraci.acquire()
    oldPhaseIndex = traci.trafficlights.getPhase(tllId)
    try:
        traci.trafficlights.setPhase(tllId, currentPhaseIndex)
    except:
        traci.trafficlights.setPhase(tllId, oldPhaseIndex)
        mtraci.release()
        returnCode = constants.TLL_PHASE_INDEX_ERROR
        sendAck(constants.PRINT_PREFIX_TLL, returnCode, outputSocket)
        raise
    mtraci.release()
    
    #Setting complete phases definition
    if commandSize > 3:
        mtraci.acquire()
        oldPhasesDefinition = traci.trafficlights.getCompleteRedYellowGreenDefinition(tllId)
        try:
            returnCode = setCompletePhasesDefinition(tllId, command, currentPhaseIndex, mtraci)
            mtraci.release()
        except:
            oldPhasesDetails = getPhasesDetails(oldPhasesDefinition)
            setCompletePhasesDefinition(tllId, oldPhasesDetails, oldPhaseIndex, mtraci)
            mtraci.release()
            returnCode = constants.TLL_PHASE_STATE_ERROR
            
    #Sending ack
    sendAck(constants.PRINT_PREFIX_TLL, returnCode, outputSocket)
    
    
""" See file description """
def run(mtraci, inputSocket, outputSocket, eShutdown, eTrafficLightsReady, eManagerReady):
    bufferSize = 1024
    
    mtraci.acquire()
    trafficLightsId = traci.trafficlights.getIDList()
    mtraci.release()
    
    eTrafficLightsReady.set()
    while not eManagerReady.is_set():
        time.sleep(constants.SLEEP_SYNCHRONISATION)
    
    while not eShutdown.is_set():
        try:
            # Read the message from the input socket (blocked until a message is read)
            try:
                buff = inputSocket.recv(bufferSize)
            except:
            	traceback.print_exc()
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
                    
                    Logger.infoFile("{} Message received: {}".format(constants.PRINT_PREFIX_TLL, cmd))
                    
                    # Send all traffic lights geographic coordinates to the client
                    if commandSize == 1 and command[0] == constants.ALL_TLL_COORDS_REQUEST_HEADER:
                        sendTrafficLightsPosition(trafficLightsId, mtraci, outputSocket, False)
                    
                    
                    # Send the requested traffic lights geographic coordinates to the client    
                    elif commandSize > 1 and command[0] == constants.TLL_COORDS_REQUEST_HEADER:
                        command.pop(0)
                        sendTrafficLightsPosition(command, mtraci, outputSocket, True)
                        
                        
                    # Process a GET details request (**)
                    elif commandSize == 5 and command[0] == constants.TLL_GET_DETAILS_REQUEST_HEADER:
                        processGetDetailsRequest(command[1], command[2], int(command[3]), outputSocket, mtraci, int(command[4]))
                        
                        
                    # Process a SET details request (**)
                    elif commandSize > 2 and command[0] == constants.TLL_SET_DETAILS_REQUEST_HEADER:
                        processSetDetailsRequest(command, commandSize, outputSocket, mtraci)
                    
                    
                    # Error
                    else:
                        Logger.warning("{}Invalid command received: {}".format(constants.PRINT_PREFIX_TLL, command))
                        print command[0]
                        print constants.ALL_TLL_COORDS_REQUEST_HEADER
                        print commandSize
                        sendAck(constants.PRINT_PREFIX_TLL, constants.INVALID_MESSAGE, outputSocket)

        except Exception as e:
            if e.__class__.__name__ == constants.CLOSED_SOCKET_EXCEPTION or e.__class__.__name__ == constants.TRACI_EXCEPTION:
                Logger.info("{}Shutting down current thread".format(constants.PRINT_PREFIX_TLL))
                Logger.exception(e)
                sys.exit()
            else:
                Logger.error("{}A {} exception occurred:".format(constants.PRINT_PREFIX_TLL, e.__class__.__name__))
                Logger.exception(e)
