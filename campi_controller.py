#!/usr/bin/python3
# -*- coding: utf-8 -*-

mqtt_host = 'mqtt.home'

import paho.mqtt.client as paho

import platform
import sys
import os
#import urllib2
import time
from subprocess import call
import struct
import socket
import threading
import fcntl
import json

try:
    mqtt = paho.Client(client_id=socket.gethostname()+'.keypad_client')
    mqtt.connect(mqtt_host, 1883, 60)
    mqtt.loop_start()
except Exception as e:
    print ("MQTT error: "+str(e))
    pass

#device = '/dev/'

hidraw_path = '/sys/class/hidraw'
keypad_actuator_topic = '/actuator/campi/keypad'

keycode_map = {
    40: "enter",
    88: "enter",
    42: "backspace",
    43: "numlock",
    83: "numlock",
    84: "/",
    85: "*",
    86: "-",
    87: "+",
    89: "1",
    90: "2",
    91: "3",
    92: "4",
    93: "5",
    94: "6",
    95: "7",
    96: "8",
    97: "9",
    98: "0",
    99: "."
}

import time
import struct

class MyRepeats (object):
    def __init__ (self):
        self.repeats = {}
        self.delay = {}

    def add (self, topic, val):
        self.delay[topic] = val
        self.repeats[topic] = val

    def remove (self, topic):
        self.delay.pop(topic, None)
        self.repeats.pop(topic, None)

    def process (self):
        for topic, val in self.repeats.items():
            if topic in self.delay:
                self.delay.pop(topic, None)
            else:
                mqtt.publish(topic, val)

repeats = MyRepeats()

class MyKeypad (object):

    def __init__(self, fn, host, dev, type):
        self.type = type
        self.host = host
        self.dev = dev
        self.device = fn
        self.state = []
        self.keycode_map = keycode_map
        self.topic = keypad_actuator_topic
        self.msg = {
            'state': None,
            'type': type,
            'host': host,
            'dev': dev,
            'keycode': None,
            'key': None
        }

    def poll (self):
        try:
            with open(self.device, 'rb') as f:
                buf = f.read(8)
                while buf:
                    bytes = struct.unpack('B'*len(buf), buf)
                    self.process(list(bytes))
                    buf = f.read(8)

        except IOError:
            pass

    def process (self, bytes) :

        if self.type == 'presenter':
            if bytes[0] != 1 or bytes[3] != 0 or bytes[4] != 1:
                return

            if (bytes[1]==2 and bytes[2]==62):
                self.msg['key'] = 'south'
            elif (bytes[1]==0 and bytes[2]==41):
                self.msg['key'] = 'south'
            elif (bytes[1]==0 and bytes[2]==5):
                self.msg['key'] = 'north'
            elif (bytes[1]==0 and bytes[2]==75):
                self.msg['key'] = 'west'
            elif (bytes[1]==0 and bytes[2]==78):
                self.msg['key'] = 'east'
            else:
                return
            self.msg['keycode'] = bytes[2]
            self.msg['state'] = 'up'

            print("{}\t{}".format(self.topic+'/up', json.dumps(self.msg)))
            mqtt.publish(self.topic+'/up', json.dumps(self.msg))

            return

        if self.type == 'wired' and 83 in bytes:
            return

        oldState = list(self.state)
        self.state = []

        for button in bytes:
            if button == 0: continue

            self.msg['keycode'] = button
            try:
                self.msg['key'] = self.keycode_map[button]
            except:
                self.msg['key'] = None

            print (self.msg['key'])

            if button not in oldState:
                self.msg['state'] = 'down'
                mqtt.publish(self.topic+'/down', json.dumps(self.msg))
                self.msg['state'] = 'repeat'
                repeats.add(self.topic+'/repeat', json.dumps(self.msg))

            self.state.append(button)

        for button in oldState:
            if button not in self.state:
                self.msg['state'] = 'up'
                mqtt.publish(self.topic+'/up', json.dumps(self.msg))
                repeats.remove(self.topic+'/repeat')

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
    print ("Failure")

if __name__ == '__main__':

    try:
        daemons = {}

        devs = [f for f in os.listdir(hidraw_path) if "05A4:9840" in os.path.realpath(hidraw_path + '/' + f)]
        for dev in devs:
            print (dev, 'wired')
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wired'))

        devs = [f for f in os.listdir(hidraw_path) if "062A:4182" in os.path.realpath(hidraw_path + '/' + f)]
        for dev in devs:
            print (dev, 'wireless')
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wireless'))

        devs = [f for f in os.listdir(hidraw_path) if "2571:4101" in os.path.realpath(hidraw_path + '/' + f)]
        for dev in devs:
            print (dev, 'presenter')
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'presenter'))

        for dev, daemon in daemons.items():
            daemon.daemon = True
            daemon.start()

        while True:
            time.sleep(0.25)
            repeats.process()

    except (KeyboardInterrupt, SystemExit):
        sys.exit(1)
