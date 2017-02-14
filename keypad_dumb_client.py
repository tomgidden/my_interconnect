#!/usr/bin/python
# -*- coding: utf-8 -*-

mqtt_host = 'mqtt.home'

import paho.mqtt.client as paho

import platform
import sys
import os
import urllib2
import time
from subprocess import call
import struct
import socket
import threading
import fcntl

try:
    mqtt = paho.Client()
    mqtt.connect(mqtt_host, 1883, 60)
    mqtt.loop_start()
except Exception as e:
    print "MQTT error: "+str(e)
    pass

#device = '/dev/'

hidraw_path = '/sys/class/hidraw'
keypad_actuator_topic = '/actuator/bedroom/keypad'

import time
import struct

class MyKeypad (object):

    def __init__(self, fn, host, dev, type):
        self.type = type
        self.host = host
        self.dev = dev
        self.device = fn
        self.state = []
        self.topic = keypad_actuator_topic + '/' + type + '/' + host + '/' + dev

    def poll (self):
        try:
            with open(self.device, 'r') as f:
                buf = f.read(8)
                while buf:
                    bytes = struct.unpack('B'*len(buf), buf)
                    self.process(list(bytes))
                    buf = f.read(8)

        except IOError:
            pass

    def process (self, bytes) :

#        if 83 in bytes:
#            return

        oldState = list(self.state)
        self.state = []

        for button in bytes:
            if button == 0: continue

            if button not in oldState:
                mqtt.publish(self.topic+'/press', button)

            self.state.append(button)

        for button in oldState:
            if button not in self.state:
                mqtt.publish(self.topic+'/release', button)

def thread_device (dev, type):
    fn = "/dev/"+dev
    keypad = MyKeypad(fn, platform.node(), dev, type)

    while True:
        try:
            keypad.poll()
            if os.path.exists(fn):
                time.sleep(5)
            else:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            sys.exit(1)
        print "Failure"

if __name__ == '__main__':

    try:
        daemons = {}

        devs = [f for f in os.listdir(hidraw_path) if "05A4:9840" in os.path.realpath(hidraw_path + '/' + f)]
        for dev in devs:
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wired'))
            daemons[dev].daemon = True
            daemons[dev].start()

        devs = [f for f in os.listdir(hidraw_path) if "062A:4182" in os.path.realpath(hidraw_path + '/' + f)]
        for dev in devs:
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wireless'))
            daemons[dev].daemon = True
            daemons[dev].start()

        while True:
            time.sleep(0.2)

    except (KeyboardInterrupt, SystemExit):
        sys.exit(1)
