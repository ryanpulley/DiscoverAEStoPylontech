#!

'''
Service: DiscoverBMS.py

Purpose:
    1) Listens to the Discover Serial CAN protocol 
    2) Transforms data into object model
    3) Outputs to MQTT protocol on topics

Feature Details:
'''

import can
#import argparse
import paho.mqtt.client as mqtt
import struct
from enum import Enum
import logging
from logging.handlers import TimedRotatingFileHandler
import threading
from time import sleep
import json
import sys
import yaml
import os
from datetime import datetime
import math
import signal


#region ********** Metrics Class ************
'''
--------------------------------------
Metrics Class
--------------------------------------
'''

'''
Service metrics classes
'''
class BMStoInverterMetrics ():
   initialized = False
   lastBMSRead = datetime.now()
   lastInverterWrite = datetime.now()
   lastHeartbeat = datetime.now()
   BMSBytesRead = 0
   BMSBytesWritten = 0
   InverterBytesWritten = 0
   InverterBytesRead = 0


   def friendlySize(self,bytes):
      if bytes == 0:
         return "0B"
      sizeName = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
      i = int(math.floor(math.log(bytes, 1024)))
      p = math.pow(1024, i)
      s = round(bytes / p, 2)
      return "%s%s" % (s, sizeName[i])

   def millisecondsAgo(self,lastDate):
      if lastDate != None:
         a = datetime.now() - lastDate
         #return str(a.seconds)
         return str(int(a.total_seconds() * 1000))
      else:
         return -1
      
#endregion

#region ********** BMS Classes **********
'''
--------------------------------------
BMS Classes
--------------------------------------
'''

'''
BMS Battery Limits (0x351)
Transmission Rate: 1000ms

Example: 
  can0  351   [8]  2F 02 04 0B 04 0B B0 01
  
  Bytes Value   Dec Value   Converted Value     Description   
  0-1   022F    559         55.9v               Requested Charge Voltage
  2-3   0B04    2820        28.2a               Requested Charge Current
  4-5   0B04    2820        28.2a               Requested Maximum Discharge Current
  6-7   01B0    432         43.2v               Low Battery Cut Out Voltage
'''
class BMSDiscoverSCBatteryLimits ():
   initialized = False;
   requestedChargeVoltage = 0.0;
   requestedChargeCurrent = 0.0;
   requestedMaximumDischargeCurrent = 0.0;
   lowBatteryCutOutVoltage = 0.0;

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      unpackedBuffer = struct.unpack("<HHHH", buffer) 

      self.requestedChargeVoltage = unpackedBuffer[0]/10
      self.requestedChargeCurrent = unpackedBuffer[1]/10
      self.requestedMaximumDischargeCurrent = unpackedBuffer[2]/10
      self.lowBatteryCutOutVoltage = unpackedBuffer[3]/10
      self.initialized = True;

'''
BMS Battery Capacity Information (0x354)
Transmission Rate: 1000ms

Example: 
  can0  354   [8]  2C 01 E7 00 00 00 00 00
  
  Bytes Value   Dec Value   Converted Value     Description   
  0-1   012C    300         300ah               Battery Nominal Capacity
  2-3   00E7    231         231ah               Battery Remaining Capacity
  4-7   0000    0           0                   Reserved
'''
class BMSDiscoverSCBatteryCapacity ():
   initialized = False
   batteryNominalCapacity = 0
   batteryRemainingCapacity = 0

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      unpackedBuffer = struct.unpack("<HHHH", buffer) 

      self.batteryNominalCapacity = unpackedBuffer[0]
      self.batteryRemainingCapacity = unpackedBuffer[1]
      self.initialized = True
      
'''
BMS Battery Status (0x355)
Transmission Rate: 1000ms

Example: 
  can0  355   [8]  4D 00 64 00 00 00 00 00
  
  Bytes Value   Dec Value   Converted Value     Description   
  0-1   004D    77          77%                 Battery State of Charge
  2-3   0064    100         100%                Battery State of Health
  4-7   0000    0           0                   Reserved
'''
class BMSDiscoverSCBatteryStatus ():
   initialized = False
   batteryStateOfCharge = 0
   batteryStateOfHealth = 0

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      unpackedBuffer = struct.unpack("<HHHH", buffer) 

      self.batteryStateOfCharge = unpackedBuffer[0]
      self.batteryStateOfHealth = unpackedBuffer[1]
      self.initialized = True

'''
BMS Battery Measurements (0x356)
Transmission Rate: 1000ms

Example: 
  can0  356   [8]  11 02 A4 FF F0 00 00 00
  
  Bytes Value   Dec Value   Converted Value     Description   
  0-1   0211    529         52.9 V              Battery Voltage
  2-3   FFBB    65444       -9.2 A              Battery Current
  4-5   00F0    240         24 ºC               Battery Temperature
  6-7   0000    0           0                   Reserved
'''
class BMSDiscoverSCBatteryMeasurements ():
   initialized = False
   batteryVoltage = 0.0
   batteryCurrent = 0.0
   batteryTemperature = 0.0
   batteryTemperatureF = 0.0
   lowVoltageWarning = 48.0
   __lowVoltageCounter = 0

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      unpackedBuffer = struct.unpack("<HhhH", buffer) 

      self.batteryVoltage = unpackedBuffer[0]/10
 
      #--occasionaly we see an erroneous low voltage reported by the lynk II (46.x) volts
      #--which causes the Midnite AIO inverter to go to standby causing a 20-30 second outage
      #--to mitigate, we will not report to the inverter unless it occurs 3 times consecutively
      if (self.batteryVoltage <= self.lowVoltageWarning):
         self.__lowVoltageCounter += 1
         logger.warning("Low voltage reported by BMS: " + str(self.batteryVoltage) + ", occurence count:" + self.__lowVoltageCounter)
         logger.warning("0x356 message: " + buffer)
         if (self.__lowVoltageCounter < 3):
            self.batteryVoltage = self.lowVoltageWarning + 0.1
            logger.error("Low voltage reported by BMS over 3 times:" + str(self.batteryVoltage) + ", occurence count:" + self.__lowVoltageCounter)
      else:
         self.__lowVoltageCounter = 0

      self.batteryCurrent = unpackedBuffer[1]/10
      self.batteryTemperature = unpackedBuffer[2]/10
      self.batteryTemperatureF = (self.batteryTemperature * 9/5) +32
      self.initialized = True



class Alarm(Enum):

   CELL_VOLTAGE_HIGH, \
   CELL_VOLTAGE_LOW, \
   CELL_VOLTAGE_DIFFERENCE_HIGH, \
   CELL_TEMPERATURE_HIGH, \
   CELL_TEMPERATURE_LOW, \
   PACK_VOLTAGE_HIGH, \
   PACK_VOLTAGE_LOW, \
   PACK_CURRENT_HIGH, \
   PACK_CURRENT_LOW, \
   PACK_TEMPERATURE_HIGH, \
   PACK_TEMPERATURE_LOW, \
   CHARGE_CURRENT_HIGH, \
   CHARGE_VOLTAGE_HIGH, \
   CHARGE_VOLTAGE_LOW, \
   CHARGE_TEMPERATURE_HIGH, \
   CHARGE_TEMPERATURE_LOW, \
   CHARGE_MODULE_TEMPERATURE_HIGH, \
   DISCHARGE_CURRENT_HIGH, \
   DISCHARGE_VOLTAGE_HIGH, \
   DISCHARGE_VOLTAGE_LOW, \
   DISCHARGE_TEMPERATURE_HIGH, \
   DISCHARGE_TEMPERATURE_LOW, \
   DISCHARGE_MODULE_TEMPERATURE_HIGH, \
   SOC_HIGH, \
   SOC_LOW, \
   ENCASING_TEMPERATURE_HIGH, \
   ENCASING_TEMPERATURE_LOW, \
   TEMPERATURE_SENSOR_DIFFERENCE_HIGH, \
   FAILURE_SENSOR_CELL_TEMPERATURE, \
   FAILURE_SENSOR_PACK_TEMPERATURE, \
   FAILURE_SENSOR_CHARGE_MODULE_TEMPERATURE, \
   FAILURE_SENSOR_DISCHARGE_MODULE_TEMPERATURE, \
   FAILURE_SENSOR_PACK_VOLTAGE, \
   FAILURE_SENSOR_PACK_CURRENT, \
   FAILURE_COMMUNICATION_INTERNAL, \
   FAILURE_COMMUNICATION_EXTERNAL, \
   FAILURE_CLOCK_MODULE, \
   FAILURE_CHARGE_BREAKER, \
   FAILURE_DISCHARGE_BREAKER, \
   FAILURE_SHORT_CIRCUIT_PROTECTION, \
   FAILURE_EEPROM_MODULE, \
   FAILURE_PRECHARGE_MODULE, \
   FAILURE_NOT_CHARGING_DUE_TO_LOW_VOLTAGE, \
   FAILURE_OTHER = range (1,45)

class AlarmLevel(Enum):

   NONE, \
   WARNING, \
   ALARM = range (1,4)

'''
BMS Battery Alarms (0x35A)
Transmission Rate: 1000ms

Example: 
  can0  35A   [7]  AB AA FE AF AA FA FF
  
  Byte  Value   Dec Value   Converted Value     Description   
'''
class BMSDiscoverSCBatteryAlarms ():
   initialized = False

   alarms = {}
   protections = {}

   def __BytesTo2bits(self, data):
      bits_array = []
      doubleBitsArray = []
      for byte in data:
         bits = bin(byte)[2:].zfill(8)
         bits_array.extend(map(int, bits))

      for bittuple in zip(bits_array[::2], bits_array[1::2]):
        #print (int(str(bit1) + str(bit2),2))
        doubleBitsArray.append(int(str(bittuple[0]) + str(bittuple[1]),2))

      return doubleBitsArray
   
   def __setAlarm(self, alarm, BMSAlarmState):
      # Discover protocol sends 0=Ignored - Not Used, 1=Alarm/Warning, 2=Normal Operation, 3=Ignored - Not Used 
      if BMSAlarmState != 1:
         level=AlarmLevel.NONE
      else:
         level=AlarmLevel.ALARM
      # Alarm 
      if level != AlarmLevel.NONE:
         self.alarms[alarm] = AlarmLevel.ALARM
      else:
         #Clear Alarm
         if alarm in self.alarms:
            del self.alarms[alarm]

   def __setProtections(self, protection, BMSAlarmState):
      # Discover protocol sends 0=Ignored - Not Used, 1=Alarm/Warning, 2=Normal Operation, 3=Ignored - Not Used 
      if BMSAlarmState != 1:
         level=AlarmLevel.NONE
      else:
         level=AlarmLevel.WARNING
      # Alarm 
      if level != AlarmLevel.NONE:
         self.protections[protection] = AlarmLevel.WARNING
      else:
         #Clear Alarm
         if protection in self.protections:
            del self.protections[protection]

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      #unpackedBuffer = struct.unpack("<HHHc", buffer) 

      #print (self.__access_bit(buffer,1))
      errorWarningArray = self.__BytesTo2bits(buffer)
      #logger.debug('Read 0x35A - Raw Alerts/Protections Array: %s', errorWarningArray)
      self.__setAlarm(Alarm.FAILURE_OTHER, errorWarningArray[0])  #General BMS Alarm
      self.__setAlarm(Alarm.PACK_VOLTAGE_HIGH, errorWarningArray[1])  #High Voltage Alarm
      self.__setAlarm(Alarm.PACK_VOLTAGE_LOW, errorWarningArray[2])  #Low Voltage Alarm
      self.__setAlarm(Alarm.DISCHARGE_TEMPERATURE_HIGH, errorWarningArray[3])  #High Temperature Discharge Alarm
      self.__setAlarm(Alarm.DISCHARGE_TEMPERATURE_LOW, errorWarningArray[4])  #Low Temperature Discharge Alarm
      self.__setAlarm(Alarm.CHARGE_TEMPERATURE_HIGH, errorWarningArray[5])  #High Temperature Charge Alarm
      self.__setAlarm(Alarm.CHARGE_TEMPERATURE_LOW, errorWarningArray[6])  #Low Temperature Charge Alarm
      self.__setAlarm(Alarm.DISCHARGE_CURRENT_HIGH, errorWarningArray[7])  #Battery High Discharge Alarm
      self.__setAlarm(Alarm.CHARGE_CURRENT_HIGH, errorWarningArray[8])  #Battery High Charge Current Alarm
      #skip (byte 2, bits 2-3)
      self.__setAlarm(Alarm.FAILURE_OTHER, errorWarningArray[10]) #Internal BMS Alarm
      self.__setAlarm(Alarm.CELL_VOLTAGE_DIFFERENCE_HIGH, errorWarningArray[11]) #Imbalanced Cell Alarm
      #skip (byte 3, bits 0-1)
      #skip (byte 4, bits 2-3)
      self.__setProtections(Alarm.PACK_VOLTAGE_HIGH, errorWarningArray[14]) #High Voltage Warning
      self.__setProtections(Alarm.PACK_VOLTAGE_LOW, errorWarningArray[15]) #Low Voltage Warning
      self.__setProtections(Alarm.DISCHARGE_TEMPERATURE_HIGH, errorWarningArray[16]) #High Temperature Discharge Warning
      self.__setProtections(Alarm.DISCHARGE_TEMPERATURE_LOW, errorWarningArray[17]) #Low Temperature Discharge Warning
      self.__setProtections(Alarm.CHARGE_TEMPERATURE_HIGH, errorWarningArray[18]) #High Temperature Charge Warning
      self.__setProtections(Alarm.CHARGE_TEMPERATURE_LOW, errorWarningArray[19]) #Low Tmperature Charge Warning
      self.__setProtections(Alarm.DISCHARGE_CURRENT_HIGH, errorWarningArray[20]) #Battery High Discharge Current Warning
      self.__setProtections(Alarm.CHARGE_CURRENT_HIGH, errorWarningArray[21]) #Battery High Charge Current Warning
      #skip (byte 5, bits 4-5)
      self.__setProtections(Alarm.FAILURE_OTHER, errorWarningArray[23]) #Internal BMS Warning
      self.__setProtections(Alarm.CELL_VOLTAGE_DIFFERENCE_HIGH, errorWarningArray[24]) #Imbalanced Cell Warning
      #skip (bytes 6, bits 2-7)

      self.initialized = True;

'''
BMS Battery Manufacturer Name (0x35E)
Transmission Rate: 10000ms

Example: 
  can0  35E   [8]  44 49 53 43 4F 56 45 52
  
  Bytes 0-7 ASCII = DISCOVER
'''
class BMSDiscoverSCBatteryManufacturer ():
   initialized = False
   manufacturer = ''

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      self.manufacturer = buffer.decode('utf-8').rstrip('\u0000')
      self.initialized = True

'''
BMS Battery Model Name Upper (0x370)
Transmission Rate: 10000ms

Example: 
  can0  370   [8]  00 00 00 00 00 00 00 00
  
  Bytes 0-7 ASCII = NULL
'''
class BMSDiscoverSCModelNameUpper ():
   initialized = False
   modelName = ''

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      self.modelName = buffer.decode('utf-8').rstrip('\u0000')
      self.initialized = True

'''
BMS Battery Model Name Lower (0x371)
Transmission Rate: 10000ms

Example: 
  can0  371   [8]  00 00 00 00 00 00 00 00
  
  Bytes 0-7 ASCII = NULL
'''
class BMSDiscoverSCModelNameLower ():
   initialized = False
   modelName = ''

   def decode(self, buffer):
      # Unpack 8 bytes (little endian)      
      self.modelName = buffer.decode('utf-8').rstrip('\u0000')
      self.initialized = True

'''
BMS Battery Lynx Firmware (0x372)
Transmission Rate: 10000ms

Example: 
  can0  372   [4]  00 00 01 02
  
  Bytes 0-7 unsigned integer (xx.yy.zz.tt) little endian = 2.1.0.0
'''
class BMSDiscoverSCLynxFirmware ():
   initialized = False
   versionString = ''
   versionInt = 0

   def decode(self, buffer):
      versionFmtString = ""
      versionString = ""
      for abyte in buffer:
         versionFmtString = str(abyte) + "." + versionFmtString
         versionString =  str(abyte) + versionString
      self.versionString = versionFmtString[:-1]
      self.versionInt = str(versionString)

'''
BMS Battery Protocol Version (0x373)
Transmission Rate: 10000ms

Example: 
  can0  373   [4]  01 00 00 00
  
  Byte 0 unsigned integer (xx) = 1
'''
class BMSDiscoverSCProtocolVersion():
   initialized = False
   versionString = ''
   versionInt = 0

   def decode(self, buffer):
      self.versionString = str(buffer[0])
      self.versionInt = buffer[0]

#endregion

#region ********** Inverter Classes **********
'''
--------------------------------------
Inverter Classes (PYLONTECH Protocol)
--------------------------------------
'''

'''
Pylontech Battery Limits (0x351)

Example: 
  can0  351   [8]  2F 02 04 0B 04 0B B0 01
  
  Bytes Value   Dec Value   Converted Value     Description   
  0-1   022F    559         55.9v               Requested Charge Voltage
  2-3   0B04    2820        28.2a               Requested Charge Current
  4-5   0B04    2820        28.2a               Requested Maximum Discharge Current
  6-7   01B0    432         43.2v               Low Battery Cut Out Voltage
'''
class PylonBatteryLimits ():
   frame = 0x0351
   message = ""

   def encode(self):
      # Pack 8 bytes (little endian)   
      if BMSBatteryLimits.initialized:   
         self.message = struct.pack ('<HHHH', int(BMSBatteryLimits.requestedChargeVoltage*10), 
                     int(BMSBatteryLimits.requestedChargeCurrent*10), 
                     int(BMSBatteryLimits.requestedMaximumDischargeCurrent*10),
                     int(BMSBatteryLimits.lowBatteryCutOutVoltage*10))
         return True
      else:
         return False
       
'''
Pylontech Battery Status (0x355)

Example: 
  can0  355   [8]  62 00 64 00 00 00 00 00
  
  Bytes Value   Dec Value   Converted Value     Description   
  0-1   004D    77          77%                 Battery State of Charge
  2-3   0064    100         100%                Battery State of Health
  4-7   0000    0           0                   Reserved
'''
class PylonBatteryStatus ():
   frame = 0x0355
   message = ""
   InverterFakeoutSOC = 0
   CellBalancingRemainingTime = 0
   IsCellBalancingActive = False

   def __init__(self):
      self.cellBalancing = CellBalancing()
      self.cellBalancing.holdSOC =  CellBalancingHoldSOCParam
      self.cellBalancing.cellBalancingInterval = CellBalancingIntervalParam
      self.cellBalancing.cellBalancingMinutes = CellBalancingMinutesParam

   def encode(self):
      # Pack 8 bytes (little endian)   
      if BMSBatteryStatus.initialized:   
         self.InverterFakeoutSOC = self.cellBalancing.evaluateSOC(BMSBatteryStatus.batteryStateOfCharge)
         #self.InverterFakeoutSOC = BMSBatteryStatus.batteryStateOfCharge
         self.CellBalancingRemainingTime = self.cellBalancing.remainingTime
         self.IsCellBalancingActive = self.cellBalancing.isCellBalancingActive
         logger.debug ("PylonBatteryStatus x355, InverterFakeoutSOC:" + str(self.InverterFakeoutSOC) +
                       " CellBalancing Remaining Time:" + str(self.CellBalancingRemainingTime) +
                       " CellBalancing Active: " + str(self.IsCellBalancingActive))
         self.message = struct.pack ('<HHHH', int(self.InverterFakeoutSOC), 
                     int(BMSBatteryStatus.batteryStateOfHealth), 
                     0,
                     0)
         return True
      else:
         return False

'''
Pylontech Battery Measurements (0x356)

Example: 
  can0  356   [8]  11 02 A4 FF F0 00 00 00
  
  Bytes Value   Dec Value   Converted Value     Description   
  0-1   0211    529         52.9 V              Battery Voltage
  2-3   FFBB    65444       -9.2 A              Battery Current
  4-5   00F0    240         24 ºC               Battery Temperature
  6-7   0000    0           0                   Reserved
'''
class PylonBatteryMeasurements ():
   frame = 0x0356
   message = ""

   def encode(self):
      # Pack 8 bytes (little endian)   
      if BMSBatteryMeasurements.initialized:   
         self.message = struct.pack ('<HhhH', int(BMSBatteryMeasurements.batteryVoltage*100), 
                     int(BMSBatteryMeasurements.batteryCurrent*10), 
                     int(BMSBatteryMeasurements.batteryTemperature*10),
                     0)
         return True
      else:
         return False

'''
Pylontech Charge Flags (0x35C)

Example: 
  can0  356   [2]  00 00
  
  Bytes Value   Description   
  0:3   1       Request Full Charge
  0:4   1       Request Force Charge II (SOC 5-10%)
  0:5   1       Request Force Charge I (SOC 15-19%)
  0:6   1       Discharge Enable
  0:7   1       Charge Enable
'''
class PylonBatteryChargeFlags ():
   frame = 0x035C
   message = ""

   def encode(self):
      # Pack 2 bytes (little endian)   
      charge_enable =128     #bit 7
      discharge_enable = 64  #bit 6
      full_charge_enable = 8 #bit 3
      request_force_charge_1 = 32 #bit 5
      request_force_charge_2 = 16 #bit 4
      self.message = struct.pack ('<BB', charge_enable+
                                  discharge_enable+
                                  full_charge_enable+
                                  request_force_charge_1+
                                  request_force_charge_2, 0)
      return True

'''
Pylontech Battery Alarms/Protections (0x359)

Example: 
  can0  359   [7]  00 00 00 00 01 50 4E
'''
class PylonBatteryAlarms ():
   frame = 0x0359
   message = ""

   def __set_bit(self, byteArrayp, byte_index, bit_index):
       byteT = byteArrayp[byte_index]
       byteT |= 1<<bit_index
       byteArrayp[byte_index] = byteT
       

   def encode(self):
      if BMSBatteryAlarms.initialized:
         alarmsByteArray = bytearray(7)
 
         
         '''
         Byte 0                        Bit
         CellOvervoltageError        1
         CellUndervoltageError       2
         CellOvertemperatureError    3
         CellUndertemperatureError   4
         DischargeOvercurrentError   7

         Byte 1                        Bit
         ChargeOvercurrentError      0
         SystemError                 3
         '''
         #Alarms
         if Alarm.PACK_VOLTAGE_HIGH in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,0,1)
         if Alarm.PACK_VOLTAGE_LOW in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,0,2)
         if Alarm.DISCHARGE_TEMPERATURE_HIGH in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,0,3)
         if Alarm.CHARGE_TEMPERATURE_HIGH in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,0,3)
         if Alarm.DISCHARGE_TEMPERATURE_LOW in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,0,4)
         if Alarm.CHARGE_TEMPERATURE_LOW in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,0,4)
         if Alarm.DISCHARGE_CURRENT_HIGH in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,0,7)
         if Alarm.CHARGE_CURRENT_HIGH in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,1,0)
         if Alarm.FAILURE_OTHER in BMSBatteryAlarms.alarms: self.__set_bit(alarmsByteArray,1,3)

         '''
         Byte 2                        Bit
         CellOvervoltageWarning        1
         CellUndervoltageWarning       2
         CellOvertemperatureWarning    3
         CellUndertemperatureWarning   4
         DischargeOvercurrentWarning   7

         Byte 3                        Bit
         ChargeOvercurrentWarning      0
         SystemWarning                 3
         '''
         #Alarms
         if Alarm.PACK_VOLTAGE_HIGH in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,2,1)
         if Alarm.PACK_VOLTAGE_LOW in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,2,2)
         if Alarm.DISCHARGE_TEMPERATURE_HIGH in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,2,3)
         if Alarm.CHARGE_TEMPERATURE_HIGH in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,2,3)
         if Alarm.DISCHARGE_TEMPERATURE_LOW in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,2,4)
         if Alarm.CHARGE_TEMPERATURE_LOW in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,2,4)
         if Alarm.DISCHARGE_CURRENT_HIGH in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,2,7)
         if Alarm.CHARGE_CURRENT_HIGH in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,3,0)
         if Alarm.FAILURE_OTHER in BMSBatteryAlarms.protections: self.__set_bit(alarmsByteArray,3,3)

         alarmsByteArray[4] = 1   # module number
         alarmsByteArray[5] = 0x50
         alarmsByteArray[6] = 0x4E

         self.message=alarmsByteArray

         return True
      else:
         return False

'''
Pylon Battery Manufacturer Name (0x35E)

Example: 
  can0  35E   [8]  44 49 53 43 4F 56 45 52
  
  Bytes 0-7 ASCII = DISCOVER
'''
class PylonBatteryManufacturer ():
   frame = 0x035E
   message = ""

   def encode(self):
      # pack 8 bytes 
      if BMSManufacturer.initialized:     
         self.message = bytearray(BMSManufacturer.manufacturer.encode())
         #struct.pack('cccccccc',BMSManufacturer.manufacturer)
         return True
      else:
         return False

#endregion

#region ********** Cell Balancing **********
'''
Functions to control a CellBalancing capability

Description:
The Midnite AIO stops charging when reaching a defined SOC.
If we would like to perform a cell balancing, we need to "trick"
the inverter into thinking the Discover Batteries have not yet
reached that defined SOC.   So, we can "hold" the SOC at a lower 
number for a defined period of time to get an "Absorb" charge.
'''
class CellBalancing ():
   __lastSOC = 0
   __timerStartTime = datetime.now()
   holdSOC = 0                #SOC to hold at when actual SOC is greater than this value
   cellBalancingInterval = 1  #day interval to perform cell balancing
   cellBalancingMinutes = 30  #number of minutes to balance
   isCellBalancingActive = False
   remainingTime = 0
   lastBalanceDate = datetime.now()

   def __init__(self):
      #read date marker file
      try: 
         with open("cellbalance.marker", 'r') as file:
            #lastBalanceDateStr = file.readline ()
            self.lastBalanceDate = datetime.strptime(file.readline(),"%Y-%m-%d")
            logger.debug("Read cellbalance.marker with:" +self.lastBalanceDate.strftime("%Y-%m-%d"))      
      except FileNotFoundError:
         with open("cellbalance.marker", "w") as file:
            #for new file, start with the cell balancing today by writing last balance back #days in config
            self.lastBalanceDate = datetime.now() - datetime.timedelta(days=self.cellBalancingInterval)
            file.write(self.lastBalanceDate.strftime("%Y-%m-%d"))
            logger.debug("Wrote cellbalance.marker with:" +self.lastBalanceDate.strftime("%Y-%m-%d"))

   def __evaluateDay (self):
      if datetime.now() > self.lastBalanceDate + datetime.timedelta(days=self.cellBalancingInterval):
         logger.debug ('evaluated day for allowed run as True')
         return True
      else:
         logger.debug ('evaluated day for allowed run as False')
         return False
   
   def __startTimer (self):
      self.__timerStartTime = datetime.now()
      self.isCellBalancingActive = True
      logger.debug ('starting cell balance timer:' +self.__timerStartTime.strftime("%Y-%m-%d %H:%M:%S"))

   def __stopTimer (self):
      #write marker file with successful completion of cell balancing
      with open("cellbalance.marker", "w") as file:
         self.lastBalanceDate = datetime.now()
         file.write(self.lastBalanceDate.strftime("%Y-%m-%d"))
      self.isCellBalancingActive = False
      logger.debug ('stopping cell balance timer, wrote marker:' +self.lastBalanceDate.strftime("%Y-%m-%d"))

   def __remainingTime (self):
      elapsedTime = datetime.now() - self.__timerStartTime
      logger.debug ('setting remaining time:' + str((self.cellBalancingMinutes*60)-elapsedTime.seconds))
      return (self.cellBalancingMinutes * 60) - elapsedTime.seconds

   
   def evaluateSOC(self, SOC):
      if (self.__lastSOC == 0): self.__lastSOC = SOC

      if (self.isCellBalancingActive):
         self.remainingTime = self.__remainingTime()
         if (self.remainingTime > 0):
            logger.debug ("evaluateSOC in cell balance, holding at:" + str(self.holdSOC))
            return self.holdSOC
         else:
            logger.debug ("evaluateSOC hit cell balance time, stopping timer")
            self.__stopTimer()
      else:
         #evaluate if we have reached the start of hold
         if (SOC > self.__lastSOC):
            self.__lastSOC = SOC
            logger.debug ("evaluateSOC increment SOC, last SOC now:" + str(self.__lastSOC))
            if (SOC > self.holdSOC):
               #start timer if we are on an active day
               logger.debug ("evaluateSOC reached hold SOC")
               if self.__evaluateDay():
                  logger.debug ("evaluateSOC evaluated day as true, starting timer and holding at:" + str(self.holdSOC))
                  self.__startTimer()
                  return self.holdSOC
      
      return SOC
         
#endregion

#region ********** CAN **********
'''
--------------------------------------
CAN Methods
--------------------------------------
'''

def openCANPort (CANChannel, CANBitrate):
   try:
      #CANPort = can.interface.Bus(interface='socketcan', channel=CANChannel, bitrate=CANBitrate)
      CANPort = can.ThreadSafeBus(interface='socketcan', channel=CANChannel, bitrate=CANBitrate)
      return CANPort
   except:
      logger.error('Error: Failed to open CAN Port, exiting')
      exit ()

#endregion

#region ********** BMS Reader ************
'''
--------------------------------------
BMS Reader Methods
--------------------------------------
'''

def readBMS(runEvent,CANPort):
   global BMSBatteryLimits
   global BMSBatteryCapacity
   global BMSBatteryStatus
   global BMSBatteryMeasurements
   global BMSBatteryAlarms
   global BMSManufacturer
   global BMSModelNameUpper
   global BMSModelNameLower
   global BMSLynxFirmware
   global BMSProtocolVersion

   BMSBatteryLimits = BMSDiscoverSCBatteryLimits ()
   BMSBatteryCapacity = BMSDiscoverSCBatteryCapacity ()
   BMSBatteryStatus = BMSDiscoverSCBatteryStatus ()
   BMSBatteryMeasurements = BMSDiscoverSCBatteryMeasurements ()
   BMSBatteryAlarms = BMSDiscoverSCBatteryAlarms ()
   BMSManufacturer = BMSDiscoverSCBatteryManufacturer ()
   BMSModelNameUpper = BMSDiscoverSCModelNameUpper ()
   BMSModelNameLower = BMSDiscoverSCModelNameLower ()
   BMSLynxFirmware = BMSDiscoverSCLynxFirmware ()
   BMSProtocolVersion = BMSDiscoverSCProtocolVersion ()

   BMSBatteryMeasurements.lowVoltageWarning = LowVoltageWarningParam

      
   while runEvent.is_set():
      # Check if active (ACTIVE=1, ERROR=3, PASSIVE=2)
      if CANPort.state != can.BusState.ACTIVE:
         logger.error('BMS CAN Port reports state of:' +str(CANPort.state))

      message = CANPort.recv(timeout=5)
      if message is not None:
         #update metrics
         metrics.lastBMSRead = datetime.now()
         metrics.BMSBytesRead += len(message.data)

         if message.arbitration_id == 0x35E:
            BMSManufacturer.decode(message.data)
            #logger.debug('Read 0x35E - Manufacturer: %s', BMSManufacturer.manufacturer)
         elif message.arbitration_id == 0x351:
            #sys.stdout.write('\r\033[31mBMS \033[0mInverter')
            #sys.stdout.flush()
            BMSBatteryLimits.decode(message.data)
            #logger.debug('Read 0x351 - Requested Charge Voltage: %s', BMSBatteryLimits.requestedChargeVoltage)
            #logger.debug('Read 0x351 - Requested Charge Current: %s',BMSBatteryLimits.requestedChargeCurrent)
            #logger.debug('Read 0x351 - Requested Max Discharge Current: %s',BMSBatteryLimits.requestedMaximumDischargeCurrent)
            #logger.debug('Read 0x351 - Low Battery Cutout Voltage: %s',BMSBatteryLimits.lowBatteryCutOutVoltage)
         elif message.arbitration_id == 0x354:
            BMSBatteryCapacity.decode(message.data)
            #logger.debug('Read 0x354 - Battery Nominal Capacity: %s', BMSBatteryCapacity.batteryNominalCapacity)
            #logger.debug('Read 0x354 - Battery Remaining Capacity: %s', BMSBatteryCapacity.batteryRemainingCapacity)
         elif message.arbitration_id == 0x355:
            BMSBatteryStatus.decode(message.data)
            #logger.debug('Read 0x355 - Battery State of Charge: %s', BMSBatteryStatus.batteryStateOfCharge)
            #logger.debug('Read 0x355 - Battery State of Health: %s', BMSBatteryStatus.batteryStateOfHealth)
         elif message.arbitration_id == 0x356:
            BMSBatteryMeasurements.decode(message.data)
            #logger.debug('Read 0x356 - Battery Voltage: %s', BMSBatteryMeasurements.batteryVoltage)
            #logger.debug('Read 0x356 - Battery Current: %s', BMSBatteryMeasurements.batteryCurrent)
            #logger.debug('Read 0x356 - Battery Temperature: %s', BMSBatteryMeasurements.batteryTemperature)
            #logger.debug('Read 0x356 - Battery Temperature ºF: %s', BMSBatteryMeasurements.batteryTemperatureF)
         elif message.arbitration_id == 0x35A:
            BMSBatteryAlarms.decode(message.data)
            #logger.debug('Read 0x35A - Battery Alarms: %s', BMSBatteryAlarms.alarms)
            #logger.debug('Read 0x35A - Battery Protections (Warnings): %s', BMSBatteryAlarms.protections)
         elif message.arbitration_id == 0x370:
            BMSModelNameUpper.decode(message.data)
            #logger.debug('Read 0x370 - Battery Model Name: %s', BMSModelNameUpper.modelName)
         elif message.arbitration_id == 0x371:
            BMSModelNameLower.decode(message.data)
            #logger.debug('Read 0x371 - Battery Model Name (Lower): %s', BMSModelNameLower.modelName)
         elif message.arbitration_id == 0x372:
            BMSLynxFirmware.decode(message.data)
            #logger.debug('Read 0x372 - Lynx Firmware Version: %s', BMSLynxFirmware.versionString)
         elif message.arbitration_id == 0x373:
            BMSProtocolVersion.decode(message.data)
            #logger.debug('Read 0x373 - Battery Protocol Version: %s', BMSProtocolVersion.versionString)
         else:
            logger.error ("reading unhandled message: " + str(message.arbitration_id) + ", message: " + message.data)
      else:
         logger.warning ("time > 5 seconds to read CAN message from BMS")
#endregion

#region ************ Inverter Writer *************
'''
--------------------------------------
inverterWriter Methods
--------------------------------------
'''

def writeInverter (runEvent,CANPort, frequency):
   global InvBatteryStatus

   InvBatteryLimits = PylonBatteryLimits ()
   InvBatteryStatus = PylonBatteryStatus ()
   InvBatteryMeasurements = PylonBatteryMeasurements ()
   InvBatteryChargeFlags = PylonBatteryChargeFlags ()
   InvBatteryManufacturer = PylonBatteryManufacturer () 
   InvBatteryAlarms = PylonBatteryAlarms ()

   while runEvent.is_set():
      #0x351
      if (InvBatteryLimits.encode()):
         msg = can.Message(arbitration_id=InvBatteryLimits.frame, data=InvBatteryLimits.message,is_extended_id=False)
         CANPort.send(msg)
         #update metrics
         metrics.lastInverterWrite = datetime.now()
         metrics.InverterBytesWritten += len(msg.data)
      #0x355
      if (InvBatteryStatus.encode()):
         msg = can.Message(arbitration_id=InvBatteryStatus.frame, data=InvBatteryStatus.message, is_extended_id=False)
         CANPort.send(msg)
         #update metrics
         metrics.lastInverterWrite = datetime.now()
         metrics.InverterBytesWritten += len(msg.data)
      # 0x356
      if (InvBatteryMeasurements.encode()):
         msg = can.Message(arbitration_id=InvBatteryMeasurements.frame, data=InvBatteryMeasurements.message, is_extended_id=False)
         CANPort.send(msg)
         #update metrics
         metrics.lastInverterWrite = datetime.now()
         metrics.InverterBytesWritten += len(msg.data)
      # 0x35C --- #to-do need to find some may to control full charge and maybe force charge flags
      if (InvBatteryChargeFlags.encode()):
         msg = can.Message(arbitration_id=InvBatteryChargeFlags.frame, data=InvBatteryChargeFlags.message, is_extended_id=False)
         CANPort.send(msg)
         #update metrics
         metrics.lastInverterWrite = datetime.now()
         metrics.InverterBytesWritten += len(msg.data)
      # 0x35E
      if (InvBatteryManufacturer.encode()):
         msg = can.Message(arbitration_id=InvBatteryManufacturer.frame, data=InvBatteryManufacturer.message, is_extended_id=False) 
         CANPort.send(msg)
         #update metrics
         metrics.lastInverterWrite = datetime.now()
         metrics.InverterBytesWritten += len(msg.data)
      # 0x359
      if (InvBatteryAlarms.encode()):
         msg = can.Message(arbitration_id=InvBatteryAlarms.frame, data=InvBatteryAlarms.message, is_extended_id=False) 
         CANPort.send(msg)
         #update metrics
         metrics.lastInverterWrite = datetime.now()
         metrics.InverterBytesWritten += len(msg.data)
      sleep(frequency)      
#endregion

#region ************ Inverter->BMS Heartbeat ************
'''
--------------------------------------
inverter Heartbeat Methods
--------------------------------------
'''

def inverterHeartbeat (runEvent,InverterCANPort, BMSCANPort):
   #forward heartbeat events to BMS
   while runEvent.is_set():
      message = InverterCANPort.recv()
      if message is not None:
         BMSCANPort.send(message)
         #update metrics
         metrics.lastHeartbeat = datetime.now()
         metrics.InverterBytesRead += len(message.data)
         metrics.BMSBytesWritten += len(message.data)

#endregion

#region ************* Periodic Info Messages **************
'''
--------------------------------------
Periodic info messages
--------------------------------------
'''

def infoMessage(runEvent,frequency):

   while runEvent.is_set():
      logger.info ('')
      logger.info ('SOC\tVoltage\tAmps\tTemperature')
      logger.info ('---\t-------\t----\t-----------')
      logger.info (str(BMSBatteryStatus.batteryStateOfCharge) + "\t" +
                   str(BMSBatteryMeasurements.batteryVoltage) + "\t" +
                   str(BMSBatteryMeasurements.batteryCurrent) + "\t" +
                   str(BMSBatteryMeasurements.batteryTemperature))
      if 'InvBatteryStatus' in globals():
         if InvBatteryStatus.IsCellBalancingActive:
            InverterFakeoutSOC = InvBatteryStatus.InverterFakeoutSOC
            CellBalancingRemainingTime = InvBatteryStatus.CellBalancingRemainingTime
            logger.info ('Cell Balancing Active: Seconds Remaining: ' + 
                         str(CellBalancingRemainingTime) + "\t" +
                         'SOC to Inverter: ' +
                         str(InverterFakeoutSOC))  
         else:
            logger.info ('Cell balancing inactive')  

      logger.info ('')
      logger.info ('-  Last R/W (ms)   - -              Bytes              -')
      logger.info ('BMS-R  BMS-W  Heart  BMS-R    BMS-W    Inv-R    Inv-W   ')
      logger.info ('------ ------ ------ -------- -------- -------- --------')

      logger.info (metrics.millisecondsAgo(metrics.lastBMSRead).ljust(6) + ' ' +
                   metrics.millisecondsAgo(metrics.lastInverterWrite).ljust(6) + ' ' +
                   metrics.millisecondsAgo(metrics.lastHeartbeat).ljust(6) + ' ' +
                   metrics.friendlySize(metrics.BMSBytesRead).ljust(8) + ' ' +
                   metrics.friendlySize(metrics.BMSBytesWritten).ljust(8) + ' ' +
                   metrics.friendlySize(metrics.InverterBytesRead).ljust(8) + ' ' +
                   metrics.friendlySize(metrics.InverterBytesWritten))
      
      
      sleep(frequency)
#endregion

#region ************** MQTT ************** 
'''
--------------------------------------
MQTT Methods
--------------------------------------
'''

# mqtt on connect event
def MQTTOnConnect(client, userdata, flags, rc):
   logger.info ('MQTT Connection Acknowledgment received')

def MQTTConnect (hostname, port):
   client = mqtt.Client()
   client.on_connect = MQTTOnConnect
   client.connect(hostname, port)
   client.loop_start()
   return client

def MQTTWriter (runEvent, frequency):
   while runEvent.is_set():

      if 'InvBatteryStatus' in globals():
         InverterFakeoutSOC = InvBatteryStatus.InverterFakeoutSOC
         CellBalancingRemainingTime = InvBatteryStatus.CellBalancingRemainingTime
         IsCellBalancingActive = InvBatteryStatus.IsCellBalancingActive
      else:
         InverterFakeoutSOC = -1
         CellBalancingRemainingTime = -1
         IsCellBalancingActive = False
         
      data= {
         "lowBatteryCutOutVoltage": BMSBatteryLimits.lowBatteryCutOutVoltage,
         "requestedChargeCurrent": BMSBatteryLimits.requestedChargeCurrent,
         "requestedChargeVoltage": BMSBatteryLimits.requestedChargeVoltage,
         "requestedMaximumDischargeCurrent": BMSBatteryLimits.requestedMaximumDischargeCurrent,
         "stateOfCharge": BMSBatteryStatus.batteryStateOfCharge,
         "inverterFakeoutSOC": InverterFakeoutSOC,
         "cellBalancingRemainingTime": CellBalancingRemainingTime,
         "isCellBalancingActive": IsCellBalancingActive,
         "stateOfHealth": BMSBatteryStatus.batteryStateOfHealth,
         "batteryNominalCapacity":BMSBatteryCapacity.batteryNominalCapacity,
         "batteryRemainingCapacity":BMSBatteryCapacity.batteryRemainingCapacity,
         "batteryCurrent":BMSBatteryMeasurements.batteryCurrent,
         "batteryTemperature":BMSBatteryMeasurements.batteryTemperature,
         "batteryTemperatureF":BMSBatteryMeasurements.batteryTemperatureF,
         "batteryVoltage":BMSBatteryMeasurements.batteryVoltage,
         "manufacturer":BMSManufacturer.manufacturer,
         "lynxFirmwareVersion":BMSLynxFirmware.versionString,
         "BMSModelNameUpper":BMSModelNameUpper.modelName,
         "BMSModelNameLower":BMSModelNameLower.modelName,
         "protocolVersion":BMSProtocolVersion.versionString,
         "BMSLastReadTime":metrics.lastBMSRead.isoformat(),
         "InverterLastWriteTime":metrics.lastInverterWrite.isoformat(),
         "LastHeartbeatTime":metrics.lastHeartbeat.isoformat(),
         "BMSLastReadMSAgo": metrics.millisecondsAgo(metrics.lastBMSRead),
         "InverterLastWriteMSAgo": metrics.millisecondsAgo(metrics.lastInverterWrite),
         "LastHeartbeatMSAgo": metrics.millisecondsAgo(metrics.lastHeartbeat),
         "BMSBytesRead":metrics.BMSBytesRead,
         "BMSBytesWritten":metrics.BMSBytesWritten,
         "InverterReadBytes":metrics.InverterBytesRead,
         "InverterWriteBytes":metrics.InverterBytesWritten

         }
      (rc, mid) = MQTTClient.publish("DiscoverStorage", json.dumps(data, indent=2), qos=2)

      sleep(frequency)
# endregion

#region ************** main **************

def startThreads ():
   global runEvent
   global readBMSThread
   global MQTTWriterThread
   global writeInverterThread
   global inverterHeartbeatThread
   global infoMessageThread

   runEvent = threading.Event()
   runEvent.set()

   #start continuous BMS Reader
   readBMSThread = threading.Thread(target = readBMS, args=[runEvent,BMSCANPort])
   readBMSThread.start()

   #start continuous timed MQTT Writer
   MQTTWriterThread = threading.Thread(target = MQTTWriter, args=[runEvent,5])
   MQTTWriterThread.start()

   #write to Inverter
   writeInverterThread = threading.Thread(target = writeInverter, args=[runEvent,InverterCANPort,1])
   writeInverterThread.start ()

   #inverter heartbeat
   inverterHeartbeatThread = threading.Thread(target=inverterHeartbeat, args=[runEvent,InverterCANPort, BMSCANPort])
   inverterHeartbeatThread.start ()

   #Periodic info messages
   sleep (1)
   infoMessageThread = threading.Thread(target=infoMessage, args=[runEvent,10])
   infoMessageThread.start ()

def main():
   global BMSCANPortParam
   global BMSCANPortRateParam
   global InverterCANPortParam
   global InverterCANPortRateParam
   global LogLevelParam
   global CellBalancingIntervalParam
   global CellBalancingHoldSOCParam
   global CellBalancingMinutesParam
   global LowVoltageWarningParam
   global MQTTPortParam
   global MQTTHostParam
   global metrics

   global MQTTClient

   global BMSCANPort
   global InverterCANPort

   metrics = BMStoInverterMetrics ()

   #start logger
   logFormat = '%(asctime)s %(message)s'
   logging.basicConfig(format=logFormat)
   logger = logging.getLogger()
   logger.setLevel(logging.DEBUG)

   BMSCANPort = openCANPort (BMSCANPortParam,BMSCANPortRateParam) 
   InverterCANPort = openCANPort (InverterCANPortParam, InverterCANPortRateParam)

   MQTTClient = MQTTConnect(MQTTHostParam, MQTTPortParam)

   startThreads()


   try:
      while True:
        sleep(.1)
   except KeyboardInterrupt:
      logger.info('Keyboard Interrupt Received')
   finally:
      logger.info('Closing Threads')
      runEvent.clear()
      readBMSThread.join()
      MQTTWriterThread.join()
      writeInverterThread.join()
      infoMessageThread.join()
      inverterHeartbeatThread.join()
      
      BMSCANPort.shutdown()
      InverterCANPort.shutdown()
      


#application entry point:
if __name__ == "__main__":
   with open ("config/BMS2Inverter.yaml") as f:
      config = yaml.load(f, Loader=yaml.FullLoader)

    
   #parser = argparse.ArgumentParser()
   #parser.add_argument("-b", "--bmsport", default = "can0", help="BMS commuications port descriptor, e.g. can0")
   #parser.add_argument("-r", "--bmsportrate", default = 250000, type=int, help="BMS commuications port rate, e.g. 250000")
   #parser.add_argument("-i", "--inverterport", default = "can1", help="Inverter commuications port descriptor, e.g. can1")
   #parser.add_argument("-s", "--inverterportrate", default = 500000, type=int, help="Inverter commuications port rate, e.g. 500000")
   #parser.add_argument("-l", "--loglevel", default = "info", choices=["info", "warning", "debug"], help="log level: info, warning, debug")
   #args = parser.parse_args()

   BMSCANPortParam = config["BMS"]["port"]
   BMSCANPortRateParam = config["BMS"]["portrate"]
   InverterCANPortParam = config["inverter"]["port"]
   InverterCANPortRateParam = config["inverter"]["portrate"]
   LogLevelParam = config["logging"]["loglevel"]
   LogFileParam = config["logging"]["logfile"]
   CellBalancingIntervalParam = config['cellbalancing']['interval-days']
   CellBalancingHoldSOCParam = config['cellbalancing']['hold-soc']
   CellBalancingMinutesParam = config['cellbalancing']['minutes']
   LowVoltageWarningParam = config['BMS']['lowVoltageWarning']
   MQTTHostParam = config['mqtt']['host']
   MQTTPortParam = config['mqtt']['port']
    
   #start logger
   logFormat = '%(asctime)s %(message)s'
   formatter = logging.Formatter(logFormat)
   logging.basicConfig(format=logFormat)
   logger = logging.getLogger(__name__)
   if LogLevelParam == 'info':
      logger.setLevel(logging.INFO)
   elif LogLevelParam == 'warning':
      logger.setLevel(logging.WARNING)
   elif LogLevelParam == 'debug':
      logger.setLevel(logging.DEBUG)

   #start logger for CAN module
   logger2 = logging.getLogger('can')
   logger2.setLevel(logging.INFO)
 
   fh = logging.FileHandler(LogFileParam)
   fh = TimedRotatingFileHandler(LogFileParam, when='D', interval=1, backupCount=5)
   fh.setFormatter(formatter)
   logger.addHandler(fh)
   logger2.addHandler(fh)

   logger.info("Discover Battery BMS to Midnite AIO Inverter")
   logger.info("BMS Port: " + BMSCANPortParam)
   logger.info("Inverter Port: " + InverterCANPortParam)
   logger.info("Log Level: " + LogLevelParam)
   logger.info("Current working directory:" + os.getcwd())

   main()                  # call the main function:
#endregion