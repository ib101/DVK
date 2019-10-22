# DaVinci Kitchen GmbH Python 3.6.8 Script by Ibrahim Elfaramawy
import platform
import serial
import os
import sys
import ssl
import json
import hashlib
import base64
import time
from time import gmtime, strftime, sleep
from http.client import HTTPSConnection
from twisted.internet import reactor, task
from twisted.internet.task import LoopingCall
from pymodbus.transaction import ModbusRtuFramer, ModbusAsciiFramer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSequentialDataBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server.asynchronous import StartTcpServer
splash = (r"""
   ___     __   ___         _
  |   \ __ \ \ / (_)_ _  __(_)
  | |) / _` \ V /| | ' \/ _| |
  |___/\__,_|\_/ |_|_||_\__|_|
---------------------------------""")
routines = [("Routine 1", "home", "pos1", "pos2", "pos3", "pos4", "pos5", "pos6", "pos7"),

            ("Test", "home", "test1", "test2", "test3",
            "test1", "test2", "test3"), ]

index = 1
set_values = [0, 0]
newtask = False
lasttask = False
testmode = False
t0 = 0
routinenmbr = 0

if(platform.system() == "Windows"):
    port_var = 'COM6'
else:
    port_var = '/dev/ttyACM0'

ser = serial.Serial(
    port=port_var, baudrate=9600, parity=serial.PARITY_ODD, stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS, timeout=0, write_timeout=0)

if ser.isOpen():
    ser.close()

ser.open()
ser.isOpen()

def encode_password(user, password):
    bs = ','.join([str(b) for b in hashlib.sha256((password + '#' + user + '@franka').encode('utf-8')).digest()])
    return base64.encodebytes(bs.encode('utf-8')).decode('utf-8')

class FrankaAPI:
    def __init__(self, hostname, user, password):
        self._hostname = hostname
        self._user = user
        self._password = password

    def __enter__(self):
        self._client = HTTPSConnection(self._hostname, context=ssl._create_unverified_context())
        self._client.connect()
        self._client.request('POST', '/admin/api/login',
                             body=json.dumps(
                                 {'login': self._user, 'password': encode_password(self._user, self._password)}),
                             headers={'content-type': 'application/json'})
        self._token = self._client.getresponse().read().decode('utf8')
        return self

    def __exit__(self, type, value, traceback):
        self._client.close()

    def start_task(self, task):
        self._client.request('POST', '/desk/api/execution',
                             body='id=%s' % task,
                             headers={'content-type': 'application/x-www-form-urlencoded',
                                      'Cookie': 'authorization=%s' % self._token})
        return self._client.getresponse().read()

    def open_brakes(self):
        self._client.request('POST', '/desk/api/robot/open-brakes',
                             headers={'content-type': 'application/x-www-form-urlencoded',
                                      'Cookie': 'authorization=%s' % self._token})
        return self._client.getresponse().read()

def log(message):
    return print(strftime("%H:%M:%S")+"  "+message)

def first(s):
    api.start_task(routines[routinenmbr][1])
    log("Task "+routines[routinenmbr][1])
    global t0
    t0 = time.time()

with FrankaAPI('10.10.10.3', 'user', 'password') as api:
    print(splash)
    print("Enter number to start routine:")
    for routine in enumerate(routines):
        print("["+str(routine[0]+1)+"] "+routines[routine[0]][0])
    print(r"""[t] Test Mode
            ---------------------------------""")
    log("Unlocking Brakes")
    try:
        api.open_brakes()
    except:
        log("ERROR Opening Brakes")
    sleep(11)
    log("Brakes Unlocked")
    string = str(input())
if string == "t":
    testmode = True
    log("Entering Test Mode")
if string.strip().isdigit():
    routinenmbr = int(string)-1
    log("Starting "+routines[routinenmbr][0])
    first = task.deferLater(reactor, 28, first, "DVK")


def updating_writer(a):
    global routine, index, testmode, set_values, newtask, lasttask, t0, routinenmbr
    context = a[0]
    output_coils = context[0].getValues(5, 4, count=80)
    output_coils = list(map(int, output_coils))
    context[0].setValues(5, 4, set_values)
    for i in range(16, 46):
        if output_coils[i]:
            ser.write(bytes(str(i)+"\n", encoding="ascii"))
    for i in range(47, 79):
        if output_coils[i]:
            ser.write(bytes(str(i+1)+"\n", encoding="ascii"))
    if (output_coils[2] and newtask == False and testmode == False):
        if index < len(routine[routinenmbr])-1:  # -2
            newtask = True
            index += 1
            reactor.callLater(1, wait, index)
        elif(output_coils[2] and lasttask == False):
            lasttask = True
            run_time = time.time()-t0
            log("The End, time: "+str(round(run_time/60, 2))+" min")
            os._exit(1)
    if (output_coils[2] == 0):
        newtask = False


def run_updating_server():
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, [0]*100),
        ir=ModbusSequentialDataBlock(0, [0]*100))
    context = ModbusServerContext(slaves=store, single=True)
    loop = LoopingCall(f=updating_writer, a=(context,))
    loop.start(0.00001, now=True)
    try:
        StartTcpServer(context, address=("10.10.10.2", 502))
    except ValueError:
        log("ERROR Staring TCP Server")


def wait(index):
    global routines
    api.start_task(routines[routinenmbr][index])
    log(str(index)+"/"+str(len(routines[routinenmbr])-1)+" "+str(routines[routinenmbr][index]))


l = task.LoopingCall(run_updating_server)
l.start(0.0001)
reactor.run()
