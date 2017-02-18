#! /usr/bin/python
#
# Nabaztag RFID with Raspberry
#
# (c) DerFlash - https://github.com/DerFlash/Trinity
#
#

import time
import atexit
import sys

import threading
from threading import Timer

import logging
logger = logging.getLogger()
#logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

import Adafruit_ADS1x15
adc = Adafruit_ADS1x15.ADS1015()

from Adafruit_MotorHAT import Adafruit_MotorHAT, Adafruit_DCMotor
mh = Adafruit_MotorHAT(addr=0x60)


class BunnyEar:

	earID_LEFT = 0
	earID_RIGHT = 1

	direction_FORWARD = 0
	direction_BACKWARD = 1
	direction_AUTO = 2

	encoderMode_RESET = 0
	encoderMode_INIT = 1
	encoderMode_SETUP = 2
	encoderMode_ACTIVE = 3

	encoderState_LOW = 1
	encoderState_HIGH = 2
	
	# unfortunately both encoders running at the same time produce massive lag resulting in wrong tooth detection :-(
	threadSync = threading.Semaphore()

	def __init__(self, earID, motorID, encoderID):
		atexit.register(self.cleanup)

		self.earSpeed = 255

		self.earID = earID
		self.motorID = motorID
		self.encoderID = encoderID
		
		self.encoderMode = self.encoderMode_RESET
		self.encoderState = self.encoderState_LOW
		
		self.earEncoderActive = threading.Event()
		self.earEncoderActive.clear() # needed?
		
		self.deactivateBunnyEarTimer = None
				
		self.encoderGaps = 0
		self.encoderLastGap = 0

		self.lastTimeStamp = 0
		
		self.earDirection = self.direction_FORWARD
		self.earPosition = 0
		self.earTargetPosition = 0
		
		self.lastRead = 0
		
		mh.getMotor(self.motorID).setSpeed(self.earSpeed)


		# init
		logger.info("[%s] Initializing...",self.earName())
#		print "[" + self.earName() + "] Initializing..."

		earEncoderThread = threading.Thread(target=self.earEncoder)
		earEncoderThread.daemon = True
		earEncoderThread.start()

		self.initDone = threading.Event()
		self.initDone.set() # temporarily mark initialized, so init below can happen

		self.moveEarToPosition(0, self.direction_FORWARD, self.setInitDone)
		
		self.initDone.clear() # mark not intialized yet
		

	def setInitDone(self):
		self.encoderMode = self.encoderMode_ACTIVE
		
		logger.info("[%s] Initializing done...",self.earName())
		self.initDone.set()

	def earName(self):
		return "Left ear" if self.earID == self.earID_LEFT else "Right ear"
		
	def cleanup(self):
		mh.getMotor(self.motorID).run(Adafruit_MotorHAT.RELEASE)
		
	def encoderStateSwitched(self):
	
		# on active we only care about changes to HIGH (those are our gaps)
		if self.encoderState == self.encoderState_HIGH:
		
			self.earPosition += (1 if self.earDirection == self.direction_FORWARD else -1)
			
			# if we know the cap count, correct psition
			if self.encoderGaps > 0:
				self.earPosition = self.earPosition % self.encoderGaps

			#print "[EAR ", motorNUM, "] Current ear position: ", earPosition, (" (setup active)" if encoderMode is not encoderMode_ACTIVE else "")

			if self.encoderMode == self.encoderMode_ACTIVE or self.encoderMode == self.encoderMode_SETUP:

				if self.earDirection == self.direction_FORWARD:
					if self.earTargetPosition < self.earPosition:
						self.positionDistance = self.earTargetPosition + self.encoderGaps - self.earPosition
					else:
						self.positionDistance = self.earTargetPosition - self.earPosition
				else:
					if self.earPosition < self.earTargetPosition:
						self.positionDistance = self.earPosition + self.encoderGaps - self.earTargetPosition
					else:
						self.positionDistance = self.earPosition - self.earTargetPosition
		
				logger.info("[%s] Position: %s | Target position: %s | Direction: %s | Distance: %s", self.earName(), self.earPosition, self.earTargetPosition, ("FORWARD" if self.earDirection == self.direction_FORWARD else "BACKWARD"), self.positionDistance)

		
				if self.earPosition == self.earTargetPosition:
					logger.info("[%s] Found target ear position. Halt!",self.earName())
					self.stopEar()
				
				elif 1 <= self.positionDistance <= 2:
					logger.info("[%s] Almost there, slowing down...",self.earName())
					mh.getMotor(self.motorID).setSpeed(self.earSpeed / 3)
			
				elif self.positionDistance > 1:
					mh.getMotor(self.motorID).setSpeed(self.earSpeed)
		
		# on setup we only care about changes to LOW (those are our teeth)
		if self.encoderMode != self.encoderMode_ACTIVE and self.encoderState == self.encoderState_LOW:
	
			timeStamp = int(round(time.time() * 1000))

			if self.encoderMode is self.encoderMode_RESET:
			
				logger.info("[%s] Resetting ear position encoder...",self.earName())
				self.encoderGaps = 0
				self.encoderLastGap = 0
				self.lastTimeStamp = timeStamp
				self.encoderMode = self.encoderMode_INIT

			elif self.encoderMode is self.encoderMode_INIT:
			
				# calc gap time since last tooth
				gapTime = timeStamp - self.lastTimeStamp
				self.lastTimeStamp = timeStamp
				
				logger.info("[%s] Current tooth gap took %s seconds",self.earName(), gapTime)
		
				# if we already know a previous gap duration and this one is big enough to be our encoder mark
				if self.encoderLastGap != 0 and gapTime > self.encoderLastGap * 3:
			
					# init counting
					if self.encoderGaps == 0:
						logger.info("[%s] Found big gap. Starting tooth counting",self.earName())
						self.encoderGaps = 1 # found first gap to count
			
					# final find
					else:
						logger.info("[%s] Found big gap again. Tooth count is: %s. Resetting ear position to zero. Encoder is now active!", self.earName(), self.encoderGaps)

						#since we know we ran too far and since we finish doing a reverse, we assume we should be on the next positon already
						self.earPosition = (0 if self.earID == self.earID_LEFT else 1)
					
						self.encoderMode = self.encoderMode_SETUP
						self.stopEar()
						
				# count gaps + save last gap time
				else:
					# only count gaps when first one was already found
					if self.encoderGaps > 0:
						self.encoderGaps += 1 # count gaps while INIT
					
					self.encoderLastGap = gapTime
		
	def resetMotorEncoders(self):
		self.encoderMode = self.encoderMode_RESET
	
	def moveEarToPosition(self, targetPosition, direction=None, stopCallback=None):
		if (not self.initDone.isSet()):
			self.initDone.wait()
	
		self.earTargetPosition = targetPosition
		self.stopCallback = stopCallback
		
		# auto direction
		if direction == None or direction == self.direction_AUTO:
			distanceBACKWARD = (self.earPosition + self.encoderGaps - targetPosition) if targetPosition > self.earPosition else (self.earPosition - targetPosition)
			distanceFORDWARD = (targetPosition + self.encoderGaps - self.earPosition) if targetPosition < self.earPosition else (targetPosition - self.earPosition)
			direction = self.direction_BACKWARD if distanceBACKWARD < distanceFORDWARD else self.direction_FORWARD

		self.earDirection = direction

		logger.info("[%s] Should move to position: %s | Direction: %s", self.earName(), targetPosition, ("FORWARD" if direction == self.direction_FORWARD else "BACKWARD"))
	
		self.activateBunnyEar()
		
		logger.info("[%s] (Re-)Starting motor",self.earName())

		if self.earID == self.earID_LEFT:
			mh.getMotor(self.motorID).run(Adafruit_MotorHAT.BACKWARD if direction == self.direction_FORWARD else Adafruit_MotorHAT.FORWARD)
		else:
			mh.getMotor(self.motorID).run(Adafruit_MotorHAT.FORWARD if direction == self.direction_FORWARD else Adafruit_MotorHAT.BACKWARD)

	def stopEar(self):
		logger.info("[%s] Stopping motor",self.earName())
		
		mh.getMotor(self.motorID).run(Adafruit_MotorHAT.RELEASE)
		self.deactivateBunnyEarTimer = Timer(1, self.deactivateBunnyEar)
		self.deactivateBunnyEarTimer.start()
	
	def activateBunnyEar(self):
		logger.info("[%s] (Re-)Activating ear encoder",self.earName())
		
		if self.deactivateBunnyEarTimer is not None:
			self.deactivateBunnyEarTimer.cancel()
		else:
			self.threadSync.acquire()
			self.earEncoderActive.set()

	def deactivateBunnyEar(self):
		logger.info("[%s] Deactivating ear encoder",self.earName())
		self.deactivateBunnyEarTimer = None

		self.earEncoderActive.clear()
		self.threadSync.release()
		
		if self.stopCallback is not None:
			self.stopCallback()
	
	def earEncoder(self):
		while True:
			if (not self.earEncoderActive.isSet()):
				logger.info("[%s] Ear encoder inactive. Waiting...",self.earName())
				logger.info("")
				self.earEncoderActive.wait()
				logger.info("")
				logger.info("[%s] Ear encoder started",self.earName())

			readMe = adc.read_adc(self.encoderID, gain=1)
	
			if (self.encoderState == self.encoderState_HIGH) and (readMe < 500):
#				print "[", self.earName(), "] Ear encoder is now LOW [", readMe, "]"
				self.encoderState = self.encoderState_LOW
				self.encoderStateSwitched()
	
			if (self.encoderState == self.encoderState_LOW) and (readMe > 500):
#				print "[", self.earName(), "] Ear encoder is now HIGH [", readMe, "]"
				self.encoderState = self.encoderState_HIGH
				self.encoderStateSwitched()
	
			self.lastRead = readMe

class BunnyEars:

	def initLeftEar(self, earMotorID = 1, earSensorID = 0):
		self.left = BunnyEar(BunnyEar.earID_LEFT, earMotorID, earSensorID)

	def initRightEar(self, earMotorID = 2, earSensorID = 1):
		self.right = BunnyEar(BunnyEar.earID_RIGHT, earMotorID, earSensorID)

	def __init__(self, leftEarMotorID = 1, leftBunnyEarID = 0, rightEarMotorID = 2, rightBunnyEarID = 1):
		initLeftEarThread = threading.Thread(target=self.initLeftEar, args=(leftEarMotorID, leftBunnyEarID))
		initLeftEarThread.daemon = True
		initLeftEarThread.start()

		initRightEarThread = threading.Thread(target=self.initRightEar, args=(rightEarMotorID, rightBunnyEarID))
		initRightEarThread.daemon = True
		initRightEarThread.start()
		
# example
def main():
	ears = BunnyEars()
	
	# finally let's just stay alive for our daemon threads
	while True:
	    time.sleep(1)
						

if __name__ == "__main__":
	main()
	


