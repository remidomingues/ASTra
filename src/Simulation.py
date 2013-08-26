#!/usr/bin/env python

"""
@file	Simulation.py
@author  Remi Domingues
@date	07/06/2013

Script algorithm:
While 1:
	Running a SUMO simulation step of X seconds
	Sending a vehicles position(1) message to the remote client by an output socket
	Sending the vehicles ID of each arrived vehicle (2) by an output socket
	Changing the traffic lights phases if required for cleaning the road for priority vehicles
	Sleeping Y seconds

(1) Vehicles position message: COO vehicleId1 lon1 lat1 vehicleId2 lon2 lat2 ... vehicleIdN lonN latN

(2) Vehicles deletion message: DEL vehicleId1 vehicleId2 ... vehicleIdN
"""

import os, sys
import re
import optparse
import subprocess
import socket
import time
import constants
import traci
import traceback
from sharedFunctions import getEdgeFromLane
from sharedFunctions import isJunction
from trafficLights import updateTllForPriorityVehicles
from trafficLights import getTrafficLightsDictionary
from vehicle import sendArrivedVehicles
from vehicle import sendVehiclesCoordinates
from vehicle import getRegularVehicles
from logger import Logger

def runSimulationStep(mtraci, outputSocket):
	"""
	Runs one SUMO simulation step
	"""
	mtraci.acquire()
	traci.simulationStep()
	mtraci.release()
		
	
def removeArrivedVehicles(arrivedVehicles, priorityVehicles, mPriorityVehicles, managedTllDict, vehicles):
	"""
	Removes every arrived vehicles from the priority vehicles shared list
	"""
	for vehicleId in arrivedVehicles:
		
		if not constants.IGNORED_VEHICLES_REGEXP.match(vehicle):
			vehicles.remove(vehicleId)
		
			mPriorityVehicles.acquire()
			if vehicleId in priorityVehicles:
				priorityVehicles.remove(vehicleId)
			mPriorityVehicles.release()
			
			for key in managedTllDict.keys():
				if managedTllDict[key][0] == vehicleId:
					del managedTllDict[key]
	

def notifyAndUpdateArrivedVehicles(mtraci, outputSocket, priorityVehicles, mPriorityVehicles, managedTllDict, vehicles):
	"""
	Sends an arrived vehicles message (2) to the remote client and Remove every arrived vehicles from the priority vehicles shared list
	"""
	mtraci.acquire()
	arrivedVehicles = traci.simulation.getArrivedIDList()
	mtraci.release()
	arrivedVehicles = getRegularVehicles(arrivedVehicles)
	
	if constants.SEND_ARRIVED_VEHICLES and (constants.SEND_MSG_EVEN_IF_EMPTY or (not constants.SEND_MSG_EVEN_IF_EMPTY and arrivedVehicles)):
		sendArrivedVehicles(arrivedVehicles, mtraci, outputSocket)
	removeArrivedVehicles(arrivedVehicles, priorityVehicles, mPriorityVehicles, managedTllDict, vehicles)
	

def run(mtraci, outputSocket, mRelaunch, eShutdown, eSimulationReady, priorityVehicles, mPriorityVehicles, eManagerReady, vehicles, mVehicles):
	"""
	See file description
	"""
	yellowTllDict = dict()
	managedTllDict = dict();
	tllDict = getTrafficLightsDictionary(mtraci)
	
	mRelaunch.acquire()
	eSimulationReady.set()
	while not eManagerReady.is_set():
		time.sleep(constants.SLEEP_SYNCHRONISATION)

	while not eShutdown.is_set():
		startTime = time.clock()
		
		try:
			mVehicles.acquire()
			runSimulationStep(mtraci, outputSocket)
			
			notifyAndUpdateArrivedVehicles(mtraci, outputSocket, priorityVehicles, mPriorityVehicles, managedTllDict, vehicles)
			mVehicles.release()
			
			if constants.SEND_VEHICLES_COORDS and (constants.SEND_MSG_EVEN_IF_EMPTY or (not constants.SEND_MSG_EVEN_IF_EMPTY and vehicles)):
				sendVehiclesCoordinates(vehicles, mtraci, outputSocket, mVehicles)
				
			
			updateTllForPriorityVehicles(mtraci, priorityVehicles, mPriorityVehicles, tllDict, yellowTllDict, managedTllDict)

		except Exception as e:
			if e.__class__.__name__ == constants.TRACI_EXCEPTION or e.__class__.__name__ == constants.CLOSED_SOCKET_EXCEPTION:
				Logger.exception(e)
				mRelaunch.release()
				Logger.info("{}Shutting down current thread".format(constants.PRINT_PREFIX_SIMULATOR))
				sys.exit()
			else:
				Logger.error("{}A {} exception occurred:".format(constants.PRINT_PREFIX_SIMULATOR, e.__class__.__name__))
				Logger.exception(e)
				
		
		endTime = time.clock()
		duration = endTime - startTime
		sleepTime = constants.SIMULATOR_SLEEP - duration
		
		#Logger.info("{}Sleep time: {}".format(constants.PRINT_PREFIX_SIMULATOR, sleepTime))
		if sleepTime > 0:
			time.sleep(sleepTime)
