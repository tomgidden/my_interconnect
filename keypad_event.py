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
import select
import threading
import fcntl
import json
import evdev


try:
    mqtt = paho.Client(client_id=socket.gethostname()+'.keypad_client')
    mqtt.connect(mqtt_host, 1883, 60)
    mqtt.loop_start()
except Exception as e:
    print ("MQTT error: "+str(e))
    pass

#device = '/dev/'

keypad_actuator_topic = '/actuator/bedroom/keypad'

class MyKeypad (object):

    def __init__(self, fn, host):
        self.host = host
        self.dev = evdev.InputDevice(fn)
        self.state = []
        self.topic = keypad_actuator_topic
        self.msg = {
            'state': None,
            'host': host,
            'dev': str(fn),
            'key': None
        }


    def loop (self):
        for event in self.dev.read_loop():
            print (event)
            if event.type == evdev.ecodes.EV_KEY:
                try:
                    key = evdev.ecodes.KEY[event.code]
                    state = ['up', 'down', 'repeat'][event.value]
                    self.msg['key'] = key
                    self.msg['state'] = state
                    mqtt.publish(self.topic+'/'+state, json.dumps(self.msg))
                    print (self.msg)
                except KeyError as e:
                    print ("Key not found: {}".format(event.value))
                    print (event)


if __name__ == '__main__':

    fn = sys.argv[1]

    try:
        keypad = MyKeypad(fn, platform.node())
        while True:
            keypad.loop()
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        sys.exit(1)
