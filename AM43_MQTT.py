#!/usr/bin/env python3
from bluepy import btle
import configparser
import os
from flask import Flask
import datetime
from retrying import retry
import json
import random
import time

from paho.mqtt import client as mqtt_client


#Variables
config = configparser.ConfigParser() #Read ini file for meters
inifilepath = "./AM43.ini"
app = Flask(__name__)
broker = 'ip to broker'
port = 1883
head_topic = "homeblind/Blinds1/#"
command_topic = "homeblind/Blinds1/set"
position_topic =  "homeblind/Blinds1/position"
check_topic =  "homeblind/Blinds1/check"
check_answer_topic =  "homeblind/Blinds1/checkanswer"
set_position_topic = "homeblind/Blinds1/set_position"
client_id = 'am43client01'
username = 'usrername'
password = 'password'

# AM43 Notification Identifiers
# Msg format: 9a <id> <len> <data * len> <xor csum>
IdMove = 0x0d  #not used in code yet
IdStop = 0x0a
IdBattery = 0xa2
IdLight = 0xaa
IdPosition = 0xa7
IdPosition2 = 0xa8  #not used in code yet
IdPosition3 = 0xa9  #not used in code yet

BatteryPct = None
LightPct = None
PositionPct = None
global bSuccess



#Check and read inifile
if (os.path.exists(inifilepath)):
    config.read(inifilepath)
else:
    print()
    print("ERROR: Cannot find ini file: " + inifilepath + "! Correct the path in this script or put the ini file in the correct directory. Exiting", flush=True)
    print()
    exit(1)

class AM43Delegate(btle.DefaultDelegate):
    def __init__(self):
        btle.DefaultDelegate.__init__(self)
    def handleNotification(self, cHandle, data):
        if (data[1] == IdBattery):
            global BatteryPct
            #print("Battery: " + str(data[7]) + "%")
            BatteryPct = data[7]
        elif (data[1] == IdPosition):
            global PositionPct
            #print("Position: " + str(data[5]) + "%")
            PositionPct = data[5]
        elif (data[1] == IdLight):
            global LightPct
            #print("Light: " + str(data[4] * 12.5) + "%")
            LightPct = data[4] * 12.5
        else:
            print("Unknown identifier notification recieved: " + str(data[1:2]))



def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client(client_id)
    # client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client


def publish(client):
    msg_count = 0
    while True:
        time.sleep(1)
        msg = f"messages: {msg_count}"
        result = client.publish(command_topic, msg)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            print(f"Send `{msg}` to topic `{command_topic}`")
        else:
            print(f"Failed to send message to topic {command_topic}")
        msg_count += 1




# Constructs message and write to blind controller
def write_message(characteristic, dev, id, data, bWaitForNotifications):
    ret = False

    # Construct message
    msg = bytearray({0x9a})
    msg += bytearray({id})
    msg += bytearray({len(data)})
    msg += bytearray(data)

    # Calculate checksum (xor)
    csum = 0
    for x in msg:
        csum = csum ^ x
    msg += bytearray({csum})
    
    #print("".join("{:02x} ".format(x) for x in msg))
    
    if (characteristic):
        result = characteristic.write(msg)
        if (result["rsp"][0] == "wr"):
            ret = True
            if (bWaitForNotifications):
                if (dev.waitForNotifications(10)):
                    #print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " -->  BTLE Notification recieved", flush=True)
                    pass
    return ret


@retry(stop_max_attempt_number=2,wait_fixed=2000)
def ScanForBTLEDevices():
    scanner = btle.Scanner()
    print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Scanning for bluetooth devices....", flush=True)
    devices = scanner.scan()

    bAllDevicesFound = True
    for AM43BlindsDevice in config['AM43_BLE_Devices']:
        AM43BlindsDeviceMacAddress = config.get('AM43_BLE_Devices', AM43BlindsDevice)  # Read BLE MAC from ini file
        
        bFound = False
        for dev in devices:
            if (AM43BlindsDeviceMacAddress == dev.addr):
                print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Found " + AM43BlindsDeviceMacAddress, flush=True)
                bFound = True
                break
            #else: 
                #bFound = False
        if bFound == False:
            print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " " + AM43BlindsDeviceMacAddress + " not found on BTLE network!", flush=True)
            bAllDevicesFound = False
        
    if (bAllDevicesFound == True):
        print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Every AM43 Blinds Controller is found on BTLE network", flush=True)
        return
    else:
        print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Not all AM43 Blinds Controllers are found on BTLE network, restarting bluetooth stack and checking again....", flush=True)
        os.system("service bluetooth restart")
        raise ValueError(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Not all AM43 Blinds Controllers are found on BTLE network, restarting bluetooth stack and check again....")


@retry(stop_max_attempt_number=10,wait_fixed=2000)
def ConnectBTLEDevice(AM43BlindsDeviceMacAddress,AM43BlindsDevice):        
    try:
        print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Connecting to " + AM43BlindsDeviceMacAddress + ", " + AM43BlindsDevice.capitalize() + "...", flush=True)
        dev = btle.Peripheral(AM43BlindsDeviceMacAddress)
        return dev
    except:
        raise ValueError(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Cannot connect to " + AM43BlindsDeviceMacAddress + " trying again....")

        



def subscribe(client: mqtt_client):
  global bSuccess

  DeviceGroup = "AM43_BLE_Devices" 
  for AM43BlindsDevice in config[DeviceGroup]:
    AM43BlindsDeviceMacAddress = config.get('AM43_BLE_Devices', AM43BlindsDevice)  # Read BLE MAC from ini file
    bSuccess = False

    try:
      dev = ConnectBTLEDevice(AM43BlindsDeviceMacAddress,AM43BlindsDevice)
    except:
      print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " ERROR, Cannot connect to " + AM43BlindsDeviceMacAddress, flush=True)
      print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " Please check any open connections to the blinds motor and close them, the Blinds Engine App perhaps?", flush=True)
      continue
        
    print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " --> Connected to " + dev.addr + ", " + AM43BlindsDevice.capitalize(), flush=True)



    BlindsControlService = dev.getServiceByUUID("fe50")
    BlindsControlServiceCharacteristic = BlindsControlService.getCharacteristics("fe51")[0]
    def on_message(client, userdata, msg):
        global bSuccess
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` position_topic")
        if msg.topic == command_topic:
          if msg.payload.decode() == "OPEN":
            bSuccess = write_message(BlindsControlServiceCharacteristic, dev, IdMove, [0], False)
            result = client.publish(position_topic, "0")

          if msg.payload.decode() == "CLOSE":
            bSuccess = write_message(BlindsControlServiceCharacteristic, dev, IdMove, [100], False)
            result = client.publish(position_topic, "100")

          if msg.payload.decode() == "STOP":
            bSuccess = write_message(BlindsControlServiceCharacteristic, dev, IdStop, [0xcc], False)

        if msg.topic == set_position_topic:
          print (msg.payload.decode())
          bSuccess = write_message(BlindsControlServiceCharacteristic, dev, IdMove, [int(msg.payload.decode())], False)
          result = client.publish(position_topic, msg.payload.decode())


        if msg.topic == check_topic:
          if BlindsControlServiceCharacteristic.supportsRead():
            bSuccess = dev.setDelegate(AM43Delegate())
            bSuccess = write_message(BlindsControlServiceCharacteristic, dev, IdBattery, [0x01], True)
            bSuccess = write_message(BlindsControlServiceCharacteristic, dev, IdLight, [0x01], True)
            bSuccess = write_message(BlindsControlServiceCharacteristic, dev, IdPosition, [0x01], True)

            # retrieve global variables with current percentages
            global BatteryPct
            global LightPct
            global PositionPct
            print(
            datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " ----> Battery level: " + str(BatteryPct) + "%, " +
            "Blinds position: " + str(PositionPct) + "%, " +
            "Light sensor level: " + str(LightPct) + "%", flush=True)
            info = '{"battery": ' + str(BatteryPct) + ', "position":' + str(PositionPct) + ', "light": ' + str(LightPct) + ', "macaddr": ' + str(AM43BlindsDeviceMacAddress) + '}'
            print (info)
            result = client.publish(check_answer_topic, info)
            result = client.publish(position_topic, str(PositionPct))

            # Reset variables
            BatteryPct = None
            LightPct = None
            PositionPct = None


        if (bSuccess):
          print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " ----> Writing " + msg.payload.decode() + " to " + AM43BlindsDevice.capitalize()  + " was succesfull!", flush=True)
        else:
          print(datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " ----> Writing to " + AM43BlindsDevice.capitalize()  + " FAILED", flush=True)

        c1 = [ {"command": msg.payload.decode(), "bSuccess": bSuccess, "macaddr": AM43BlindsDeviceMacAddress}]
        print (c1)
 


    client.subscribe(head_topic)
    client.on_message = on_message




def run():
    client = connect_mqtt()
    subscribe(client)
    client.loop_forever()



if __name__ == '__main__':
    run()
