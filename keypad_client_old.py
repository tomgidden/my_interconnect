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
unknown_actuator_topic = '/actuator/bedroom/keypad/unknown'

import time
import struct

class MyRepeats (object):
    def __init__ (self):
        self.repeats = {}

    def add (self, topic, val):
        self.repeats[topic] = val

    def remove (self, topic):
        self.repeats.pop(topic, None)

    def process (self):
        for topic, val in self.repeats.iteritems():
            mqtt.publish(topic, val)
            print "{}:\t{}".format(topic, val)

repeats = MyRepeats()

class MyKeypad (object):

    def __init__(self, fn, host, dev):
        self.host = host
        self.dev = dev
        self.device = fn
        self.state = []
        self.map = {
                40: ("/actuator/bedroom/unknown/enter", "toggle", False), # Enter
            88: ("/actuator/bedroom/unknown/enter", "toggle", False), # Enter
                42: ("/actuator/bedroom/unknown/back", "toggle", False), # BACK
                43: ("/actuator/bedroom/desk_monitor", "toggle", False),
            83: ("/actuator/bedroom/desk_monitor", "toggle", False), # NumLock
                84: ("/actuator/bedroom/tower_fan", "toggle", False), # /
                85: ("/actuator/bedroom/desk_fan", "toggle", False), # *
                86: ("/actuator/bedroom/blind2/direction", -10, True), # -
                87: ("/actuator/bedroom/blind2/direction", +10, True), # +
                89: ("/actuator/bedroom/bed_light", "toggle", False), # 1
                90: ("/actuator/bedroom/desk_light", "toggle", False), # 2
                91: ("/actuator/bedroom/shelf_light", "toggle", False), # 3
                92: ("/actuator/bedroom/blind1/direction", 7, False), # 4
                93: ("/actuator/bedroom/medicine_reset", "toggle", False), # 5
                94: ("/actuator/bedroom/unknown/6", "toggle", False), # 6
                95: ("/actuator/bedroom/blind1/direction", -7, False), # 7
                96: ("/actuator/bedroom/oramorph_dose", 10, False), # 8
                97: ("/actuator/bedroom/unknown/9", "toggle", False), # 9
                98: ("/actuator/bedroom/ceiling_light", "toggle", False), # 0
                99: ("/actuator/bedroom/unknown/dot", "toggle", False) # .
        }

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

        for button in bytes:
            if button == 0: continue

            try:
                topic, val, repeat = self.map[button]

                self.state.append(button)
                if button not in oldState:
                    mqtt.publish(topic, val)
                    print "{}:\t{}".format(topic, val)
                    if repeat:
                        repeats.add(topic, val)

            except KeyError:
                mqtt.publish(unknown_actuator_topic, button)
                print button
                pass

        for button in oldState:
            if button not in self.state:
                try:
                    topic, val, repeat = self.map[button]
                    repeats.remove(topic)
                except KeyError:
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
            repeats.process()
            time.sleep(0.2)

    except (KeyboardInterrupt, SystemExit):
        sys.exit(1)
