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
except e:
    print "MQTT error: "+str(e)
    pass

#device = '/dev/'

hidraw_path = '/sys/class/hidraw'

import time
import struct

class MyKeypad (object):

    def __init__(self, fn, host, dev):
        self.host = host
        self.dev = dev
        self.device = fn
        self.state = []

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

        if 83 in bytes:
            return

        oldState = list(self.state)
        self.state = []

        for x in bytes:
            if x == 0: continue

            self.state.append(x)

            if x not in oldState:
                self.onButton(x, True)

        for x in oldState:
            if x not in self.state:
                self.onButton(x, False)

    def onButton (self, button, state):
        if state:
            map = {
                98: "/actuator/bedroom/ceiling_light",
                89: "/actuator/bedroom/bed_light",
                90: "/actuator/bedroom/desk_light",
                85: "/actuator/bedroom/desk_fan",
                84: "/actuator/bedroom/tower_fan",
                43: "/actuator/bedroom/desk_monitor",
                91: "/actuator/bedroom/limpet_light"
            }

            try:
                val = "toggle" #'1' if state else '0'
                topic = map[button]
                mqtt.publish(topic, val)
                print "{}:\t{}".format(topic, val)

            except KeyError:
                print button
                pass


def thread_device (dev):
    fn = "/dev/"+dev
    keypad = MyKeypad(fn, platform.node(), dev)

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

    devs = [f for f in os.listdir(hidraw_path) if "05A4:9840" in os.path.realpath(hidraw_path + '/' + f)]

    daemons = {}

    try:
        for dev in devs:
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,))
            daemons[dev].daemon = True
            daemons[dev].start()

        while True:
            time.sleep(5)

    except (KeyboardInterrupt, SystemExit):
        sys.exit(1)
