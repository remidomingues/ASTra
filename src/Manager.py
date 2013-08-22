#!/usr/bin/env python

"""
@file	Manager.py
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
	astraDirectory = os.path.abspath('C:/Temp/workspace/cardemo/src/main/app/astra/src')
	sys.path.append(astraDirectory)

import Constants
import DuarouterRoute
import Simulation
import Vehicle
import TrafficLights
import DijkstraRoute
import Route
import Graph
from sumolib import checkBinary
import traci
from Logger import Logger

""" Returns a socket connected to the distant host / port given in parameter """
def acceptConnection(host, port):
	Logger.info("{}Waiting for connection on {}:{}...".format(Constants.PRINT_PREFIX_MANAGER, host, port))
	vSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	vSocket.bind((host, port))
	vSocket.listen(1)
	conn, addr = vSocket.accept()
	Logger.info("{}Connected".format(Constants.PRINT_PREFIX_MANAGER))
	return vSocket


""" Starts a SUMO subprocess with the specified network """
def startSUMO(sumoStartCommand):
	Logger.info("{}Starting a SUMO instance using {} network...".format(Constants.PRINT_PREFIX_MANAGER, Constants.SUMO_CHOSEN_NETWORK))
	sumoGuiProcess = subprocess.Popen(sumoStartCommand, shell=True, stdout=sys.stdout)
	Logger.info("{}Done".format(Constants.PRINT_PREFIX_MANAGER))


""" Initializes TraCI on the specified port """
def initTraciConnection(traciPort, maxRetry):
	sleep = 1
	step = 0
	traciInit = False
	Logger.info("{}Initializing TraCI on port {}...".format(Constants.PRINT_PREFIX_MANAGER, traciPort))
	while not(traciInit) and step < maxRetry:
		try:
			traci.init(traciPort)
			traciInit = True
		except:
			Logger.info("{}Traci initialisation on port {} failed. Retrying connection in {} seconds...".format(Constants.PRINT_PREFIX_MANAGER, traciPort, sleep))
			time.sleep(sleep)
			if sleep >= 4:
				sleep = 5
			else:
				sleep *= 2
			step += 1
			
	if not(traciInit):
		Logger.error("{}Traci initialisation on port {} failed. Shutting down SUMO Manager".format(Constants.PRINT_PREFIX_MANAGER, traciPort))
		sys.stdout.flush()
		sys.exit(0)
		
	Logger.info("{}Initialized".format(Constants.PRINT_PREFIX_MANAGER))


""" Starts a SUMO subprocess, connects to TraCI then starts ASTra's threads """
def deployThreads(mtraci, mRelaunch, mPriorityVehicle, eRouteReady, eGraphReady, eVehicleReady, eTrafficLightsReady, eSimulationReady, eShutdown, eManagerReady, priorityVehicle):
	#Building sockets and starting threads
	if Constants.GRAPH_ENABLED:
		Logger.info("{}--------- Graph enabled --------".format(Constants.PRINT_PREFIX_MANAGER))
		graphInputSocket = acceptConnection(Constants.HOST, Constants.GRAPH_INPUT_PORT)
		graphOutputSocket = acceptConnection(Constants.HOST, Constants.GRAPH_OUTPUT_PORT)
		graphThread = threading.Thread(None, Graph.run, "Graph", (mtraci, graphInputSocket, graphOutputSocket, eShutdown, eGraphReady, eManagerReady, graph, junctionsDict, edgesDict), {})
		graphThread.start()
	else:
		Logger.info("{}======== Graph disabled ========".format(Constants.PRINT_PREFIX_MANAGER))
		eGraphReady.set()
		
	if Constants.ROUTING_ENABLED:
		Logger.info("{}------- Routing enabled --------".format(Constants.PRINT_PREFIX_MANAGER))
		routerInputSocket = acceptConnection(Constants.HOST, Constants.ROUTER_INPUT_PORT)
		routerOutputSocket = acceptConnection(Constants.HOST, Constants.ROUTER_OUTPUT_PORT)
		routerThread = threading.Thread(None, Route.run, "Route", (mtraci, routerInputSocket, routerOutputSocket, eShutdown, eRouteReady, eManagerReady, graph, junctionsDict, edgesDict), {})
		routerThread.start()
	else:
		Logger.info("{}======= Routing disabled =======".format(Constants.PRINT_PREFIX_MANAGER))
		eRouteReady.set()
	
	if Constants.ORDERS_ENABLED:
		Logger.info("{}-------- Vehicles enabled --------".format(Constants.PRINT_PREFIX_MANAGER))
		orderInputSocket = acceptConnection(Constants.HOST, Constants.ORDER_INPUT_PORT)
		orderOutputSocket = acceptConnection(Constants.HOST, Constants.ORDER_OUTPUT_PORT)
		orderThread = threading.Thread(None, Vehicle.run, "Vehicle", (mtraci, orderInputSocket, orderOutputSocket, eShutdown, priorityVehicle, mPriorityVehicle, eVehicleReady, eManagerReady), {})
		orderThread.start()
	else:
		Logger.info("{}======= Vehicles disabled ========".format(Constants.PRINT_PREFIX_MANAGER))
		eVehicleReady.set()
	
	if Constants.TLL_ENABLED:
		Logger.info("{}---- Traffic lights enabled ----".format(Constants.PRINT_PREFIX_MANAGER))
		tllInputSocket = acceptConnection(Constants.HOST, Constants.TLL_INPUT_PORT)
		tllOutputSocket = acceptConnection(Constants.HOST, Constants.TLL_OUTPUT_PORT)
		trafficLightsThread = threading.Thread(None, TrafficLights.run, "TrafficLights", (mtraci, tllInputSocket, tllOutputSocket, eShutdown, eTrafficLightsReady, eManagerReady), {})
		trafficLightsThread.start()
	else:
		Logger.info("{}=== Traffic lights disabled ====".format(Constants.PRINT_PREFIX_MANAGER))
		eTrafficLightsReady.set()
	
	if Constants.SIMULATION_ENABLED:
		Logger.info("{}------ Simulation enabled -------".format(Constants.PRINT_PREFIX_MANAGER))
		simulatorOutputSocket = acceptConnection(Constants.HOST, Constants.SIMULATOR_OUTPUT_PORT)
		simulatorThread = threading.Thread(None, Simulation.run, "Simulation", (mtraci, simulatorOutputSocket, mRelaunch, eShutdown, eSimulationReady, priorityVehicle, mPriorityVehicle, eManagerReady), {})
		simulatorThread.start()
	else:
		Logger.info("{}====== Simulation disabled ======".format(Constants.PRINT_PREFIX_MANAGER))
		Logger.info("{}=== Automatic redeployment on error disabled ===".format(Constants.PRINT_PREFIX_MANAGER))
		eSimulationReady.set()
		
	return graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket


""" Closes sockets then wait for threads end """
def shutdownThreads(eShutdown, graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket):
	eShutdown.set()
	
	#Closing sockets and waiting for the threads end
	if Constants.SIMULATION_ENABLED:
		simulatorOutputSocket.close()
		simulatorThread.join()
	if Constants.TLL_ENABLED:
		tllOutputSocket.close()
		tllInputSocket.close()
		trafficLightsThread.join()
	if Constants.ORDERS_ENABLED:
		orderOutputSocket.close()
		orderInputSocket.close()
		orderThread.join()
	if Constants.ROUTING_ENABLED:
		routerOutputSocket.close()
		routerInputSocket.close()
		routerThread.join()
	if Constants.GRAPH_ENABLED:
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
	#Events
	eRouteReady = threading.Event()
	eGraphReady = threading.Event()
	eVehicleReady = threading.Event()
	eTrafficLightsReady = threading.Event()
	eSimulationReady = threading.Event()
	eShutdown = threading.Event()
	eManagerReady = threading.Event()
	#Priority vehicles list
	priorityVehicle = []
	
	Logger.info("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
			  + "+ Initializing app 'ASTra'                                 +\n"
			  + "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

	if Constants.POSIX_OS:
		Logger.warning("You are running on a POSIX based operating system (See Constants).\nThe screenshot functionality has been disabled for the traffic lights management.")
	
	#Starting SUMO
	startSUMO(Constants.SUMO_GUI_START_COMMAND)
	
	#Connecting to TraCI
	initTraciConnection(Constants.TRACI_PORT, Constants.TRACI_CONNECT_MAX_STEPS)
	
	#Building dictionaries
	if Constants.ROUTING_ENABLED or Constants.GRAPH_ENABLED:
		graph, junctionsDict, edgesDict = Graph.getGraphAndJunctionsDictionaryAndEdgesDictionary(mtraci)
		
	graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket = deployThreads(mtraci, mRelaunch, mPriorityVehicle, eRouteReady, eGraphReady, eVehicleReady, eTrafficLightsReady, eSimulationReady, eShutdown, eManagerReady, priorityVehicle)
	
	#Waiting for the threads to be ready
	while not eGraphReady.is_set() or not eRouteReady.is_set() or not eVehicleReady.is_set() or not eTrafficLightsReady.is_set() or not eSimulationReady.is_set():
		time.sleep(Constants.SLEEP_SYNCHRONISATION)
	
	#Sending a ready message to the remote client
	eManagerReady.set()
	
	Logger.info("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
			   + "+ Started app 'ASTra'                                     +\n"
			   + "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
		
	#Waiting for a TraCI exception
	if Constants.SIMULATION_ENABLED:
		mRelaunch.acquire()
	else:
		#No redeployment if an error occurs
		while(True):
			time.sleep(65536)
	
	#Asking for the threads to shutdown
	Logger.info("{}Shutting down all threads. Preparing for redeployment...".format(Constants.PRINT_PREFIX_MANAGER))
	
	shutdownThreads(eShutdown, graphThread, graphInputSocket, graphOutputSocket, routerThread, routerInputSocket, routerOutputSocket, orderThread, orderInputSocket, orderOutputSocket, trafficLightsThread, tllInputSocket, tllOutputSocket, simulatorThread, simulatorOutputSocket)
		
	traci.close()
	sys.stdout.flush()
	time.sleep(1)
