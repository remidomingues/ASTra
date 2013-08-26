
                           ASTra - API for Simulated Traffic


Presentation
============
ASTra is an open source Python library designed to remotely access a SUMO simulation
at runtime using TCP/IP sockets and high level calls.
It is a multithreaded process, based on TraCI and Duarouter tools, providing a set of
functionalities which can be enabled or disabled and come with a high reliability -
with automatic restarts for the whole API and simulation if a serious issue occurs.
This API has been developped by Rémi Domingues and Anthony Labaere in the PEL 
laboratory, at UCD, in a research project led by Lero.



Download link
=============
ASTra can be downloaded on https://github.com/remidomingues/ASTra

This API is still under development, so new version may be uploaded, fixing previous
bugs and extending functionalities.



Using ASTra
===========
This library is compatible with Python 2.7.2 and has been tested on Ubuntu 13.04 
(3.8.0-27 linux kernel), Linux Mint 14 (3.5.0-36 linux kernel), Linux Mint 15
(3.8.0-26 linux kernel), Windows 7 and Windows 8. SUMO 0.16.0 is required.

The default network loaded by ASTra is the Dublin one.
Before starting ASTra, please modify the following constants in the constants.py file:

	POSIX_OS = {True,False}
	ASTRA_DIRECTORY = <ASTRA_ABSOLUTE_DIRECTORY>
	SUMO_DIRECTORY = <SUMO_INSTALLATION_DIRECTORY>



For starting the application, please install Python 2.7.2 and SUMO 0.16.0 then execute
the following command in a shell:

	python <ASTRA_MANAGER_FILE_PATH>

This application can also be launched from Java using Jython 2.7-b1 and the following
code lines:
	
	FileInputStream pythonScript = new FileInputStream(new File(<ASTRA_MANAGER_FILE_PATH>));
	interpreter.execfile(pythonScript);

	
For adding a network to simulate to ASTra, you must add your network file, (.net.xml)
and you configuration file (.sumocfg) in the config folder. You can also use any SUMO
compatible file and specify them in your .sumocfg file, they will be loaded when
starting SUMO. Please make sure the TRACI_PORT constant is the same than the one
specified in the .sumocfg file. Then, add the following lines in the constants.py file:

	MY_NETWORK_ID = "myNetwork"
	MY_NETWORK_CONFIG_FILE = CONFIG_DIRECTORY + "/myNetwork.sumocfg"
	MY_NETWORK_NET_FILE = CONFIG_DIRECTORY + "/myNetwork.net.xml"
	addNetworkToConfigDict(MY_NETWORK_NETWORK_ID, MY_NETWORK_ID, MY_NETWORK_NET_FILE)


This will add your network to ASTra's networks directory. If you want to use this
network, modify the following constant value:

	SUMO_CHOSEN_NETWORK = MY_NETWORK_ID

	
ASTra will then wait for connections on ports 18001 to 18009. Less connections can be
made if disabling functionalities. The connections are done in the port ascending order.
Check files descriptions for socket messages.
	


Bugs.
=====
Please send bugs and requests to remidomingues@live.fr



License.
========
ASTra is licensed under GPL, see the COPYING file for details.
