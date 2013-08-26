#!/usr/bin/env python

"""
@file	Constants.py
@author  Remi Domingues
@date	18/06/2013

String constants used by ASTra Python scripts
"""

import os, sys
import re
from math import ceil
from datetime import datetime
import logging


""" Operating system """
POSIX_OS = False

""" Functionalities """
ROUTING_ENABLED = True
GRAPH_ENABLED = True
VEHICLE_ENABLED = True
SIMULATION_ENABLED = True
TLL_ENABLED = True


""" Cardemo """
SERVER = False


class ClosedSocketException(Exception):
	"""
	Exception threw when the socket the process is trying to listen or write is closed
	"""
	pass

""" Main directories """
ASTRA_DIRECTORY = os.path.abspath('C:/Temp/workspace/cardemo/src/main/app/astra')
SUMO_DIRECTORY = os.path.abspath(os.path.dirname(ASTRA_DIRECTORY) + '/sumo-0.16.0')
CONFIG_DIRECTORY = ASTRA_DIRECTORY + "/config"
DICT_DIRECTORY = ASTRA_DIRECTORY + "/dict"
LOG_DIRECTORY = ASTRA_DIRECTORY + "/log"
TMP_DIRECTORY = ASTRA_DIRECTORY + "/tmp"
SCREEN_DIRECTORY = ASTRA_DIRECTORY + "/screen"

""" Networks constants """
"""
SUMO_CONFIG dictionary structure:
	Key = networkId
	Value = Configuration Files dictionary:
				Key = configFileType
				Value = configFilePath
Note:
- configFileType in {CONFIG_FILE_KEY, NETWORK_FILE_KEY}
"""
SUMO_CONFIG_DICT = dict()
CONFIG_FILE_KEY = "Config"
NETWORK_FILE_KEY = "Network"

def addNetworkToConfigDict(networkId, configFile, networkFile):
	"""
	Add a network linked with its configuration files to the sumo config dictionary
	"""
	filesDict = dict()
	filesDict[CONFIG_FILE_KEY] = configFile
	filesDict[NETWORK_FILE_KEY] = networkFile
	SUMO_CONFIG_DICT[networkId] = filesDict
	

""" Networks configuration """
""" Dublin """
DUBLIN_NETWORK_ID = "Dublin"
DUBLIN_CONFIG_FILE = CONFIG_DIRECTORY + "/Dublin.sumocfg"
DUBLIN_NET_FILE = CONFIG_DIRECTORY + "/Dublin.net.xml"
addNetworkToConfigDict(DUBLIN_NETWORK_ID, DUBLIN_CONFIG_FILE, DUBLIN_NET_FILE)

""" Chosen network """
SUMO_CHOSEN_NETWORK = DUBLIN_NETWORK_ID

""" Config file """
SUMO_BINARY = os.path.abspath(SUMO_DIRECTORY + "/bin/sumo-gui")
DUAROUTER_BINARY = os.path.abspath(SUMO_DIRECTORY + "/bin/duarouter.exe")
SUMO_TOOLS_DIRECTORY = os.path.abspath(SUMO_DIRECTORY + "/tools")
sys.path.append(SUMO_TOOLS_DIRECTORY)

SUMO_NETWORK_FILE = SUMO_CONFIG_DICT[SUMO_CHOSEN_NETWORK][NETWORK_FILE_KEY]
SUMO_CONFIG_FILE = SUMO_CONFIG_DICT[SUMO_CHOSEN_NETWORK][CONFIG_FILE_KEY]
SUMO_GUI_SETTINGS_FILE = CONFIG_DIRECTORY + "/sumo-gui-settings.xml"

SUMO_JUNCTIONS_DICTIONARY_FILE = DICT_DIRECTORY + "/{}JunctionsDictionary".format(SUMO_CHOSEN_NETWORK)
SUMO_EDGES_DICTIONARY_FILE = DICT_DIRECTORY + "/{}EdgesDictionary".format(SUMO_CHOSEN_NETWORK)
SUMO_TLL_DICTIONARY_FILE = DICT_DIRECTORY + "/{}TrafficLightsDictionary".format(SUMO_CHOSEN_NETWORK)
SUMO_GRAPH_FILE = DICT_DIRECTORY + "/{}GraphDictionary".format(SUMO_CHOSEN_NETWORK)


""" Shared constants """
SLEEP_SYNCHRONISATION = 0.1
MESSAGES_SEPARATOR = "\r\n"
END_OF_LINE = '\n'
END_OF_MESSAGE = '\n'
EMPTY_STRING = ''
SEPARATOR = ' '
TRACI_EXCEPTION = "FatalTraCIError"
CLOSED_SOCKET_EXCEPTION = "ClosedSocketException"


""" Acknowledge messages """
ACKNOWLEDGE_HEADER = "ACK"
ACK_OK = 0
INVALID_MESSAGE = 40

GRAPH_UNKNOWN_EDGE = 30
GRAPH_INVALID_BLOCK_MSG = 31

ROUTE_ERROR_CONNECTION = 1
DUAROUTER_ERROR_LAUNCH = 2
ROUTE_TIMEOUT_ERROR = 6
ROUTE_INVALID_ALGORITHM = 7
ROUTE_INVALID_GEO = 8
ROUTE_ROUTING_REQUEST_FAILED = 10

VEHICLE_INVALID_ROUTE = 4
VEHICLE_EMPTY_ROUTE = 5
VEHICLE_MOCK_FAILED = 9
VEHICLE_DELETE_FAILED_UNKNOWN = 11

TLL_PHASE_INDEX_ERROR = 21
TLL_PHASE_STATE_ERROR = 22
TLL_PHASE_DURATION_ERROR = 23



""" Socket configuration """
HOST = "127.0.0.1"
MANAGER_OUTPUT_PORT = 18000
GRAPH_INPUT_PORT = 18001
GRAPH_OUTPUT_PORT = 18002
ROUTER_INPUT_PORT = 18003
ROUTER_OUTPUT_PORT = 18004
VEHICLE_INPUT_PORT = 18005
VEHICLE_OUTPUT_PORT = 18006
TLL_INPUT_PORT = 18007
TLL_OUTPUT_PORT = 18008
SIMULATOR_OUTPUT_PORT = 18009


""" Logger """
LOGGER_ID = "sumo"
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
NOW = datetime.now()
LOG_FILE_PATH = LOG_DIRECTORY + "/sumo.log.{}.log".format(datetime.strftime(NOW, "%d-%m-%Y_%Hh%Mm%Ss"))
	
	   
"""  Manager """
PRINT_PREFIX_MANAGER = "Manager >>> "
TRACI_PORT = 8813
TRACI_CONNECT_MAX_STEPS = 20
SUMO_SIMULATION_STEP_TIME = 1
SUMO_GUI_QUIT_ON_END = "true"
SUMO_GUI_GAME_MODE = "false"
SUMO_GUI_START_AUTO = "true"
SUMO_GUI_START_COMMAND = "{} -c {} --gui-settings-file {} --step-length {} --quit-on-end {} --game {} --start {}" .format(SUMO_BINARY, SUMO_CONFIG_FILE, SUMO_GUI_SETTINGS_FILE, SUMO_SIMULATION_STEP_TIME, SUMO_GUI_QUIT_ON_END, SUMO_GUI_GAME_MODE, SUMO_GUI_START_AUTO)
READY_HEADER = "SOK"


""" Graph """
PRINT_PREFIX_GRAPH =  "Graph >>> "

EDGES_COORDS = 1
EDGES_LENGTH = 2
EDGES_CONGESTION = 3
EDGES_SUCCESSORS = 4
GRAPH = 5

ALL_EDGES_COORDS_REQUEST_HEADER = "COO"
EDGES_COORDS_REQUEST_HEADER = "COO"
EDGES_COORDS_RESPONSE_HEADER = "COO"
EDGES_COORDS_END = "END"
EDGES_NUMBER_PER_COORDS_MESSAGE = 500	#If -1, the whole message will be sent

ALL_EDGES_LENGTH_REQUEST_HEADER = "LEN"
EDGES_LENGTH_REQUEST_HEADER = "LEN"
EDGES_LENGTH_RESPONSE_HEADER = "LEN"
EDGES_LENGTH_END = "END"
EDGES_NUMBER_PER_LENGTH_MESSAGE = 500	#If -1, the whole message will be sent

ALL_EDGES_CONGESTION_REQUEST_HEADER = "CON"
EDGES_CONGESTION_REQUEST_HEADER = "CON"
EDGES_CONGESTION_RESPONSE_HEADER = "CON"
EDGES_CONGESTION_END = "END"
EDGES_NUMBER_PER_CONGESTION_MESSAGE = 500	#If -1, the whole message will be sent

ALL_SUCCESSORS_REQUEST_HEADER = "SUC"
SUCCESSORS_REQUEST_HEADER = "SUC"
SUCCESSORS_RESPONSE_HEADER = "SUC"
SUCCESSORS_END = "END"
SUCCESSORS_LIST_SEPARATOR = ","
SUCCESSORS_NUMBER_PER_MESSAGE = 500		#If -1, the whole message will be sent

BLOCK_EDGE_REQUEST_HEADER = "BLO"
BLOCKED_ROUTE_ID_PREFIX = 'BLO'
BLOCKED_VEHICLE_ID_PREFIX = 'BLO'
UNBLOCK_EDGE_REQUEST_HEADER = "UNB"

EDGE_ID_REQUEST_HEADER = "EID"
EDGE_ID_RESPONSE_HEADER = "EID"


""" Route """
PRINT_PREFIX_ROUTER = "Route >>> "

ROUTING_REQUEST_HEADER = "GET"
ROUTING_RESPONSE_HEADER = "ROU"
DIJKSTRA_REQUEST = "DIJ"
DUAROUTER_REQUEST = "DUA"
EDGES_ID = 0
GEOGRAPHIC_COORDS = 1
ERROR_HEADER = "ERR"


""" DijkstraRoute """
PRINT_PREFIX_DIJKSTRA = "DijkstraRoute >>> "
XML_EDGE_ELEMENT = "edge"
XML_EDGE_ID = "id"
XML_EDGE_FROM_JUNCTION = "from"
XML_EDGE_TO_JUNCTION = "to"
XML_LANE_ELEMENT = "lane"
XML_LANE_ID = "id"
XML_LANE_LENGTH = "length"


""" DuarouterRoute """
PRINT_PREFIX_DUAROUTER = "DuarouterRoute >>> "
XML_TRIPS_ELEMENT = "trips"
XML_TRIP_ELEMENT = "trip"
XML_TRIP_ID_ATTRIBUTE = "id"
XML_TRIP_DEPART_ATTRIBUTE = "depart"
XML_TRIP_FROM_ATTRIBUTE = "from"
XML_TRIP_TO_ATTRIBUTE = "to"
XML_ROUTE_ELEMENT = "route"
XML_COST_ATTRIBUTE = "cost"
XML_EDGES_ATTRIBUTE = "edges"
TRIPS_PATH = TMP_DIRECTORY + "/trips.xml"
ROUTES_OUTPUT_PATH = TMP_DIRECTORY + "/result.rou.xml"
ROUTES_ALT_OUTPUT_PATH = TMP_DIRECTORY + "/result.rou.alt.xml"
DUAROUTER_START_COMMAND_TEMPLATE = "{} --ignore-errors --trip-files {} --net-file {} --output-file {}"
DUAROUTER_START_COMMAND = DUAROUTER_START_COMMAND_TEMPLATE.format(DUAROUTER_BINARY, TRIPS_PATH, SUMO_NETWORK_FILE, ROUTES_OUTPUT_PATH)
DUAROUTER_SLEEP_TIME = 0.1
DUAROUTER_MAX_SLEEP_TIME = 20


""" Vehicle """
PRINT_PREFIX_VEHICLE = "Vehicle >>> "
"""
The following constant must contain a regular expression which will be evaluated for
every vehicle when requested for all vehicles information (delete / coordinates / speed / arrived messages)
If you want access the information of a vehicle you ignore, you must specify the corresponding vehicle ID
in one of the previous messages
=> These vehicles are ignored ONLY with messages about ALL VEHICLES
=> These ones cannot be priority
"""
IGNORED_VEHICLES = "^(COL*)|(MOC*)$"
IGNORED_VEHICLES_REGEXP = re.compile(IGNORED_VEHICLES)

VEHICLE_ADD_REQUEST_HEADER = "ADD"
VEHICLE_ADD_RAND_REQUEST_HEADER = "MOC"
VEHICLE_DELETE_REQUEST_HEADER = "DEL"
VEHICLE_SPEED_REQUEST_HEADER = "SPE"
VEHICLE_SPEED_RESPONSE_HEADER = "SPE"

VEHICLE_COORDS_REQUEST_HEADER = "COO"
VEHICLE_COORDS_RESPONSE_HEADER = "COO"

VEHICLE_ARRIVED_REQUEST_HEADER = "ARR"
VEHICLE_ARRIVED_RESPONSE_HEADER = "ARR"

DEFAULT_VEHICLE_TYPE = "DEFAULT_VEHTYPE"
ROUTE_ID_PREFIX = 'R'
VEHICLE_ID_PREFIX = 'V'
PRIORITY_VEHICLE = '1'


""" TrafficLights """
PRINT_PREFIX_TLL = "TrafficLights >>> "

ALL_TLL_COORDS_REQUEST_HEADER = "COO"
TLL_COORDS_REQUEST_HEADER = "COO"
TLL_COORDS_RESPONSE_HEADER = "COO"
TLL_NUMBER_PER_MESSAGE = 500	#If -1, the whole message will be sent
TLL_POS_END = "END"
TLL_GET_DETAILS_REQUEST_HEADER = "GET"
TLL_GET_DETAILS_RESPONSE_HEADER = "DET"
TLL_SET_DETAILS_REQUEST_HEADER = "SET"

TLL_MIN_PHASE_DURATION = 1000
SCREENSHOT_FILE_NAME = "{}.png"
RED = 'r'
YELLOW = 'y'
GREEN = 'g'
GREEN_PRIO = 'G'
IGNORE = 0
SET_YELLOW = 1
SET_GREEN = 2
# How many meters the priority vehicle must be before a junction for changing the traffic light phase to green 
GREEN_LENGTH_ANTICIPATION = 50
# How many meters the priority vehicle must be before a junction for changing the traffic light phase to yellow
YELLOW_LENGTH_ANTICIPATION = 100
PRIORITY_VEHICLE_KM_PER_HOUR_SPEED = 50
PRIORITY_VEHICLE_KM_PER_SEC_SPEED = PRIORITY_VEHICLE_KM_PER_HOUR_SPEED * 1000 / 3600.0
GREEN_STEPS_ANTICIPATION = int(ceil(GREEN_LENGTH_ANTICIPATION / PRIORITY_VEHICLE_KM_PER_SEC_SPEED / SUMO_SIMULATION_STEP_TIME))
YELLOW_STEPS_ANTICIPATION = int(ceil(YELLOW_LENGTH_ANTICIPATION / PRIORITY_VEHICLE_KM_PER_SEC_SPEED / SUMO_SIMULATION_STEP_TIME))
		

""" Simulation """
PRINT_PREFIX_SIMULATOR = "Simulation >>> "
SIMULATOR_SLEEP = 1
SEND_MSG_EVEN_IF_EMPTY = False
SEND_VEHICLES_COORDS = True
SEND_ARRIVED_VEHICLES = True
