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
import Constants
import traci
import traceback
from SharedFunctions import getEdgeFromLane
from SharedFunctions import isJunction
from TrafficLights import updateTllForPriorityVehicles
from TrafficLights import getTrafficLightsDictionary
from Vehicle import sendArrivedVehicles
from Vehicle import sendVehiclesCoordinates
from Logger import Logger

""" Runs one SUMO simulation step """
def runSimulationStep(mtraci, outputSocket):
	mtraci.acquire()
	traci.simulationStep()
	mtraci.release()
		
	
""" Removes every arrived vehicles from the priority vehicles shared list """
def removePriorityArrivedVehicles(arrivedVehicles, priorityVehicles, mPriorityVehicles, managedTllDict):
	for vehicleId in arrivedVehicles:
		mPriorityVehicles.acquire()
		if vehicleId in priorityVehicles:
			priorityVehicles.remove(vehicleId)
		mPriorityVehicles.release()
		
		for key in managedTllDict.keys():
			if managedTllDict[key][0] == vehicleId:
				del managedTllDict[key]
	

""" Sends an arrived vehicles message (2) to the remote client and Remove every arrived vehicles from the priority vehicles shared list """
def notifyAndUpdateArrivedVehicles(mtraci, outputSocket, priorityVehicles, mPriorityVehicles, managedTllDict):
	mtraci.acquire()
	arrivedVehicles = traci.simulation.getArrivedIDList()
	mtraci.release()
	arrivedVehicles = getRegularVehicles(arrivedVehicles)
	
	if Constants.SEND_ARRIVED_VEHICLES:
		if Constants.SEND_MSG_EVEN_IF_EMPTY or (not Constants.SEND_MSG_EVEN_IF_EMPTY and arrivedVehicles):
			sendArrivedVehicles(arrivedVehicles, mtraci, outputSocket)
	removePriorityArrivedVehicles(arrivedVehicles, priorityVehicles, mPriorityVehicles, managedTllDict)
	

""" See file description """
def run(mtraci, outputSocket, mRelaunch, eShutdown, eSimulationReady, priorityVehicles, mPriorityVehicles, eManagerReady):
	yellowTllDict = dict()
	managedTllDict = dict();
	tllDict = getTrafficLightsDictionary(mtraci)
	
	mRelaunch.acquire()
	eSimulationReady.set()
	while not eManagerReady.is_set():
		time.sleep(Constants.SLEEP_SYNCHRONISATION)

	while not eShutdown.is_set():
		startTime = time.clock()
		
		try:
			runSimulationStep(mtraci, outputSocket)
			
			if Constants.SEND_VEHICLES_COORDS:
				mtraci.acquire()
				vehicles = traci.vehicle.getIDList()
				mtraci.release()
				vehicles = getRegularVehicles(vehicles)
				
				if Constants.SEND_MSG_EVEN_IF_EMPTY or (not Constants.SEND_MSG_EVEN_IF_EMPTY and vehicles):
					sendVehiclesCoordinates(vehicles, outputSocket, mtraci)
				
			notifyAndUpdateArrivedVehicles(mtraci, outputSocket, priorityVehicles, mPriorityVehicles, managedTllDict)
			
			updateTllForPriorityVehicles(mtraci, priorityVehicles, mPriorityVehicles, tllDict, yellowTllDict, managedTllDict)

		except Exception as e:
			if e.__class__.__name__ == Constants.TRACI_EXCEPTION or e.__class__.__name__ == Constants.CLOSED_SOCKET_EXCEPTION:
				Logger.exception(e)
				mRelaunch.release()
				Logger.info("{}Shutting down current thread".format(Constants.PRINT_PREFIX_SIMULATOR))
				sys.exit()
			else:
				Logger.error("{}A {} exception occurred:".format(Constants.PRINT_PREFIX_SIMULATOR, e.__class__.__name__))
				Logger.exception(e)
				
		
		endTime = time.clock()
		duration = endTime - startTime
		sleepTime = Constants.SIMULATOR_SLEEP - duration
		
		#Logger.info("{}Sleep time: {}".format(Constants.PRINT_PREFIX_SIMULATOR, sleepTime))
		if sleepTime > 0:
			time.sleep(sleepTime)
