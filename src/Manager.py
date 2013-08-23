#!/usr/bin/env python

"""
@file	manager.py
@author  Remi Domingues
@date	07/06/2013

Script algorithm:
while True
	- Starting the SUMO program
	- Initializing a TraCI connection
	- Initializing and waiting for socket connections from the remote client
	- Starting threads
	- Waiting for an error in the previous threads
	- Closing sockets
	- Waiting for the previous threads
	- Cleaning
"""

import os, sys
import subprocess
import signal
import socket
import time
import threading
from threading import Lock

try:
	currentDirectory = os.path.dirname(sys.argv[0])
	astraDirectory = os.path.dirname(currentDirectory)
	sys.path.append(os.path.dirname(sys.argv[0]))
except:
	sys.path.append(os.path.abspath('../apps/cardemo/astra/src'))
	sys.path.append(os.path.abspath('src/main/app/astra/src'))

import constants
import duarouterRoute
import simulation
import vehicle
import trafficLights
import dijkstraRoute
import route
import graph
from sumolib import checkBinary
import traci
from logger import Logger

""" Returns a socket connected to the distant host / port given in parameter """
def acceptConnection(host, port):
	Logger.info("{}Waiting for connection on {}:{}...".format(constants.PRINT_PREFIX_MANAGER, host, port))
	vSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	vSocket.bind((host, port))
	vSocket.listen(1)
	conn, addr = vSocket.accept()
	Logger.info("{}Connected".format(constants.PRINT_PREFIX_MANAGER))
	return conn


""" Starts a SUMO subprocess with the specified network """
def startSUMO(sumoStartCommand):
	Logger.info("{}Starting a SUMO instance using {} network...".format(constants.PRINT_PREFIX_MANAGER, constants.SUMO_CHOSEN_NETWORK))
	sumoGuiProcess = subprocess.Popen(sumoStartCommand, shell=True, stdout=sys.stdout)
	Logger.info("{}Done".format(constants.PRINT_PREFIX_MANAGER))


""" Initializes TraCI on the specified port """
def initTraciConnection(traciPort, maxRetry):
	sleep = 1
	step = 0
	traciInit = False
	Logger.info("{}Initializing TraCI on port {}...".format(constants.PRINT_PREFIX_MANAGER, traciPort))
	while not(traciInit) and step < maxRetry:
		try:
			traci.init(traciPort)
			traciInit = True
		except:
			Logger.info("{}Traci initialisation on port {} failed. Retrying connection in {} seconds...".format(constants.PRINT_PREFIX_MANAGER, traciPort, sleep))
			time.sleep(sleep)
			if sleep >= 4:
				sleep = 5
			else:
				sleep *= 2
			step += 1
			
	if not(traciInit):
		Logger.error("{}Traci initialisation on port {} failed. Shutting down SUMO Manager".format(constants.PRINT_PREFIX_MANAGER, traciPort))
		sys.stdout.flush()
		sys.exit(0)
		
	Logger.info("{}Initialized".format(constants.PRINT_PREFIX_MANAGER))


""" Starts a SUMO subprocess, connects to TraCI then starts ASTra's threads """
def deployThreads(mtraci, mRelaunch, mPriorityVehicle, eRouteReady, eGraphReady, eVehicleReady, eTrafficLightsReady, eSimulationReady, eShutdown, eManagerReady, priorityVehicles, graphDict, junctionsDict, edgesDict, vehicles, mVehicles):
	#Building sockets and starting threads
	if constants.GRAPH_ENABLED:
		Logger.info("{}--------- Graph enabled --------".format(constants.PRINT_PREFIX_MANAGER))
		graphInputSocket = acceptConnection(constants.HOST, constants.GRAPH_INPUT_PORT)
		graphOutputSocket = acceptConnection(constants.HOST, constants.GRAPH_OUTPUT_PORT)
		graphThread = threading.Thread(None, graph.run, "Graph", (mtraci, graphInputSocket, graphOutputSocket, eShutdown, eGraphReady, eManagerReady, graphDict, junctionsDict, edgesDict), {})
		graphThread.start()
	else:
		Logger.info("{}======== Graph disabled ========".format(constants.PRINT_PREFIX_MANAGER))
		eGraphReady.set()
		
	if constants.ROUTING_ENABLED:
		Logger.info("{}------- Routing enabled --------".format(constants.PRINT_PREFIX_MANAGER))
		routerInputSocket = acceptConnection(constants.HOST, constants.ROUTER_INPUT_PORT)
		routerOutputSocket = acceptConnection(constants.HOST, constants.ROUTER_OUTPUT_PORT)
		routerThread = threading.Thread(None, route.run, "Route", (mtraci, routerInputSocket, routerOutputSocket, eShutdown, eRouteReady, eManagerReady, graphDict, junctionsDict, edgesDict), {})
		routerThread.start()
	else:
		Logger.info("{}======= Routing disabled =======".format(constants.PRINT_PREFIX_MANAGER))
		eRouteReady.set()
	
	if constants.VEHICLE_ENABLED:
		Logger.info("{}-------- Vehicles enabled --------".format(constants.PRINT_PREFIX_MANAGER))
		orderInputSocket = acceptConnection(constants.HOST, constants.VEHICLE_INPUT_PORT)
		orderOutputSocket = acceptConnection(constants.HOST, constants.VEHICLE_OUTPUT_PORT)
		orderThread = threading.Thread(None, vehicle.run, "Vehicle", (mtraci, orderInputSocket, orderOutputSocket, eShutdown, priorityVehicles, mPriorityVehicle, eVehicleReady, eManagerReady, vehicles, mVehicles), {})
		orderThread.start()
	else:
		Logger.info("{}======= Vehicles disabled ========".format(constants.PRINT_PREFIX_MANAGER))
		eVehicleReady.set()
	
	if constants.TLL_ENABLED:
		Logger.info("{}---- Traffic lights enabled ----".format(constants.PRINT_PREFIX_MANAGER))
		tllInputSocket = acceptConnection(constants.HOST, constants.TLL_INPUT_PORT)
		tllOutputSocket = acceptConnection(constants.HOST, constants.TLL_OUTPUT_PORT)
		trafficLightsThread = threading.Thread(None, trafficLights.run, "TrafficLights", (mtraci, tllInputSocket, tllOutputSocket, eShutdown, eTrafficLightsReady, eManagerReady), {})
		trafficLightsThread.start()
	else:
		Logger.info("{}=== Traffic lights disabled ====".format(constants.PRINT_PREFIX_MANAGER))
		eTrafficLightsReady.set()
	
	if constants.SIMULATION_ENABLED:
		Logger.info("{}------ Simulation enabled -------".format(constants.PRINT_PREFIX_MANAGER))
		simulatorOutputSocket = acceptConnection(constants.HOST, constants.SIMULATOR_OUTPUT_PORT)
		simulatorThread = threading.Thread(None, simulation.run, "Simulation", (mtraci, simulatorOutputSocket, mRelaunch, eShutdown, eSimulationReady, priorityVehicles, mPriorityVehicle, eManagerReady, vehicles, mVehicles), {})
		simulatorThread.start()
	else:
		Logger.info("{}====== Simulation disabled ======".format(constants.PRINT_PREFIX_MANAGER))
		Logger.info("{}=== Automatic redeployment on error disabled ===".format(constants.PRINT_PREFIX_MANAGER))
		eSimulationReady.set()
		
	return graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket


""" Closes sockets then wait for threads end """
def shutdownThreads(eShutdown, graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket):
	eShutdown.set()
	
	#Closing sockets and waiting for the threads end
	if constants.SIMULATION_ENABLED:
		simulatorOutputSocket.close()
		simulatorThread.join()
	if constants.TLL_ENABLED:
		tllOutputSocket.close()
		tllInputSocket.close()
		trafficLightsThread.join()
	if constants.VEHICLE_ENABLED:
		orderOutputSocket.close()
		orderInputSocket.close()
		orderThread.join()
	if constants.ROUTING_ENABLED:
		routerOutputSocket.close()
		routerInputSocket.close()
		routerThread.join()
	if constants.GRAPH_ENABLED:
		graphOutputSocket.close()
		graphInputSocket.close()
		graphThread.join()
		

""" See file description """
#Automatic restart is the remote sockets are closed or if TraCI or SUMO crash
while True:
	#Variables
	#Mutex
	mtraci = Lock()
	mRelaunch = Lock()
	mPriorityVehicle = Lock()
	mVehicles = Lock()
	#Events
	eRouteReady = threading.Event()
	eGraphReady = threading.Event()
	eVehicleReady = threading.Event()
	eTrafficLightsReady = threading.Event()
	eSimulationReady = threading.Event()
	eShutdown = threading.Event()
	eManagerReady = threading.Event()
	#Vehicles list
	priorityVehicles = []
	vehicles = []
	
	Logger.info("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
			  + "+ Initializing app 'ASTra'                                 +\n"
			  + "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

	if constants.POSIX_OS:
		Logger.warning("You are running on a POSIX based operating system (See constants).\nThe screenshot functionality has been disabled for the traffic lights management.")
	
	#Starting SUMO
	startSUMO(constants.SUMO_GUI_START_COMMAND)
	
	#Connecting to TraCI
	initTraciConnection(constants.TRACI_PORT, constants.TRACI_CONNECT_MAX_STEPS)
	
	#Building dictionaries
	if constants.ROUTING_ENABLED or constants.GRAPH_ENABLED:
		graphDict, junctionsDict, edgesDict = graph.getGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci)
		
	if constants.VEHICLE_ENABLED or constants.SIMULATION_ENABLED:
		mtraci.acquire()
		vehicles = traci.vehicle.getIDList()
		mtraci.release()
		vehicles = vehicle.getRegularVehicles(vehicles)
		
	graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket = deployThreads(mtraci, mRelaunch, mPriorityVehicle, eRouteReady, eGraphReady, eVehicleReady, eTrafficLightsReady, eSimulationReady, eShutdown, eManagerReady, priorityVehicles, graphDict, junctionsDict, edgesDict, vehicles, mVehicles)
	
	#Waiting for the threads to be ready
	while not eGraphReady.is_set() or not eRouteReady.is_set() or not eVehicleReady.is_set() or not eTrafficLightsReady.is_set() or not eSimulationReady.is_set():
		time.sleep(constants.SLEEP_SYNCHRONISATION)
	
	#Sending a ready message to the remote client
	eManagerReady.set()
	
	Logger.info("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
			   + "+ Started app 'ASTra'                                     +\n"
			   + "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
		
	#Waiting for a TraCI exception
	if constants.SIMULATION_ENABLED:
		mRelaunch.acquire()
	else:
		#No redeployment if an error occurs
		while(True):
			time.sleep(65536)
	
	#Asking for the threads to shutdown
	Logger.info("{}Shutting down all threads. Preparing for redeployment...".format(constants.PRINT_PREFIX_MANAGER))
	
	shutdownThreads(eShutdown, graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket)
		
	traci.close()
	sys.stdout.flush()
	time.sleep(1)
