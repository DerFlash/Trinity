#! /usr/bin/python
#
# Nabaztag RFID with Raspberry
#
# (c) DerFlash - https://github.com/DerFlash/Trinity
#
#

import time

from bunny_earModule import BunnyEars
from bunny_earModule import BunnyEar

from bunny_rfidModule import RFIDReader

class BunnyPi():

	def foundRFIDTag(self, tagID):
		print "found RFID TAG: ", tagID
	
	def __init__(self):

		self.ears = BunnyEars()
		self.rfidReader = RFIDReader(self.foundRFIDTag)

		print "Bunny init done"

		self.ears.left.moveEarToPosition(0)
		self.ears.right.moveEarToPosition(0)

		self.ears.left.moveEarToPosition(0, BunnyEar.direction_BACKWARD)
		self.ears.right.moveEarToPosition(0, BunnyEar.direction_BACKWARD)
	

def main():
	bunny = BunnyPi()

	# finally let's just stay alive for our daemon threads
	while True:
	    time.sleep(1)
						

if __name__ == "__main__":
	main()
	