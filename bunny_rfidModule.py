#! /usr/bin/python
#
# Nabaztag RFID with Raspberry
#
# (c) DerFlash - https://github.com/DerFlash/Trinity
#
# thanks to:
# 06.05.2016 carlo64 - https://github.com/ccarlo64/nabaztag_raspberry
# 

import smbus
import time

import threading

import logging
logger = logging.getLogger()
#logger.setLevel(logging.DEBUG) # output level
logger.addHandler(logging.StreamHandler())

bus=smbus.SMBus(1)

R_PARAM = 0x00 #Parameter Register
R_FRAME = 0x01 #Input/Output Frame Register
R_AUTH  = 0x02 #Authenticate Register
R_SLOT  = 0x03 #slot Marker Register
RFID    = 0x50 #address
cmdInitiate  = [0x02,0x06,0x00]
cmdSelectTag = [0x02,0x0E,0x00]
cmdGetTagUid = [0x01,0x0B]
cmdOn  = 0x10
cmdOff = 0x00
zero = []
laterRfid = 0.05

class RFIDReader:

	def __init__(self, detectionCallback):
	
		self.detectionCallback = detectionCallback
	
		bus.write_quick(RFID)
		bus.write_byte_data(RFID,R_PARAM,cmdOff) #off rfid! 
		bus.write_byte_data(RFID,R_PARAM,cmdOn) #on rfid! 
		time.sleep(laterRfid)
		
		detectionLoopThread = threading.Thread(target=self.detectionLoop)
		detectionLoopThread.daemon = True
		detectionLoopThread.start()

		
	def detectionLoop(self):
	
		while 1:
			bus.write_i2c_block_data(RFID,R_FRAME,cmdInitiate)
			time.sleep(laterRfid)
	
			r = bus.read_i2c_block_data(RFID,R_FRAME)
			time.sleep(laterRfid)
	
			logger.debug("wait for rfid ..." + ', '.join(str(x) for x in [0]))

			if r[0]<>0x00:

			  bus.write_i2c_block_data(RFID,R_SLOT,zero) #Turn on detected sequence of tags
			  time.sleep(laterRfid)
	  
			  bus.write_i2c_block_data(RFID,R_FRAME,zero) 
	  
			  tableChip=bus.read_i2c_block_data(RFID,R_FRAME) 
	  
			  find = (tableChip[2] << 8) + tableChip[1];

			  if find>0:

				logger.debug("found, now test chip: " + ', '.join(str(x) for x in tableChip))

				countTag=0        
				wordBitIdx = (tableChip[2]<<8) + tableChip[1]
				
				logger.debug("wordBitIdx: " + str(wordBitIdx))
				
				for idxTmp in range( 0,16):
				
				  if (wordBitIdx & 0x0001):
				  
					logger.debug("CHIP " + str(tableChip[idxTmp+3]))
			
					cmdSelectTag[2]=tableChip[idxTmp+3]
					bus.write_i2c_block_data(RFID,R_FRAME,cmdSelectTag)  #select chip 
					time.sleep(laterRfid) 
			
					bus.write_i2c_block_data(RFID,R_FRAME,zero) 
					time.sleep(laterRfid)
						
					rr=bus.read_i2c_block_data(RFID,R_FRAME)  # 
					# test response != null && response.Length == 2 && response[1] == tag.ChipId;
			
					bus.write_i2c_block_data(RFID,R_FRAME,cmdGetTagUid) #get id  
					time.sleep(laterRfid) 
			
					bus.write_i2c_block_data(RFID,R_FRAME,zero) 
					time.sleep(laterRfid)
						
					uid=bus.read_i2c_block_data(RFID,R_FRAME)  # read id

					foundTag = ''.join(hex(a )[2:].zfill(2) for a in reversed(uid[1:9]))
					
					logger.debug("getuid :" + str(countTag) + " len + udi (8 byte) " + ', '.join(str(x) for x in uid))
					logger.debug("your TAG is: " + foundTag)
					
					self.detectionCallback(foundTag)

					#d00218c1......   d0 02 18 c1 .. .. .. ..
			
					countTag+=1
				  wordBitIdx>>=1
		  
			time.sleep(0.5)
			
# example
def main():
	def foundTag(tagID):
		print "found TAG: ", tagID

	reader = RFIDReader(foundTag)
	
	# finally let's just stay alive for our daemon threads
	while True:
	    time.sleep(1)
						

if __name__ == "__main__":
	main()
	