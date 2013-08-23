#!/usr/bin/env python

"""
@file	Logger.py
@author  Remi Domingues
@date	30/07/2013

This file contains a logger class definition.
"""

import sys
import logging
import constants
import traceback

"""
Logger used in order to write error, warning and info messages
in the user console and a log file
"""
class Logger:
	logger = logging.getLogger(constants.LOGGER_ID)
	
	@staticmethod
	def initLogger():
		hdlr = logging.FileHandler(constants.LOG_FILE_PATH)
		formatter = logging.Formatter(constants.LOG_FORMAT)
		hdlr.setFormatter(formatter)
		Logger.logger.addHandler(hdlr)
		Logger.logger.setLevel(constants.LOG_LEVEL)
		
	@staticmethod
	def exception(e):
		Logger.logger.exception(e)
		traceback.print_exc()

	@staticmethod
	def error(message):
		Logger.logFile(logging.ERROR, message)
		Logger.logConsole(logging.ERROR, message)
	
	@staticmethod
	def info(message):
		Logger.logFile(logging.INFO, message)
		Logger.logConsole(logging.INFO, message)

	@staticmethod
	def warning(message):
		Logger.logFile(logging.WARNING, message)
		Logger.logConsole(logging.WARNING, message)
		
	@staticmethod
	def infoFile(message):
		Logger.logFile(logging.INFO, message)

	@staticmethod
	def logFile(level, message):
		Logger.logger.log(level, message)
			
	@staticmethod
	def logConsole(level, message):
		if level == logging.INFO:
			print message
		if level == logging.WARNING:
			print "WARNING : " + message
		elif level == logging.ERROR:
			sys.stderr.write(message + '\n')


Logger.initLogger()