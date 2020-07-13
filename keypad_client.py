#!/usr/bin/python3
# -*- coding: utf-8 -*-

mqtt_host = 'mqtt.home'

import paho.mqtt.client as paho

import platform
import sys
import os
#import urllib2
import hid
import time
from subprocess import call
import struct
import socket
import select
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
keypad_actuator_topic = '/actuator/bedroom/keypad'

keycode_map = {
    40: "KEY_ENTER",
    88: "KEY_ENTER",
    42: "KEY_BACKSPACE",
    43: "KEY_NUMLOCK",
    83: "KEY_NUMLOCK",
    84: "KEY_KPSLASH",
    85: "KEY_KPASTERISK",
    86: "KEY_KPMINUS",
    87: "KEY_KPPLUS",
    89: "KEY_KP1",
    90: "KEY_KP2",
    91: "KEY_KP3",
    92: "KEY_KP4",
    93: "KEY_KP5",
    94: "KEY_KP6",
    95: "KEY_KP7",
    96: "KEY_KP8",
    97: "KEY_KP9",
    98: "KEY_KP0",
    99: "KEY_KPDOT"
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

    def __init__(self, fn, host, type):
        self.type = type
        self.host = host
        self.fn = fn
        self.state = []
        self.keycode_map = keycode_map
        self.topic = keypad_actuator_topic
        self.msg = {
            'state': None,
            'type': type,
            'host': host,
            'dev': str(fn),
            'keycode': None,
            'key': None
        }


    def poll (self):
        while True:
            try:
                print ("Polling "+str(self.fn))
                poll = select.poll()
                f = os.open(self.fn, os.O_RDONLY)

                os.set_blocking(f, False)
                poll.register(f)

                for fd,ev in poll.poll():
                    buf = os.read(f, 16)
                    bytes = struct.unpack('B'*len(buf), buf)
                    self.process(list(bytes))

            except IOError as e:
                raise e


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
            mqtt.publish(self.topic+'/up', json.dumps(self.msg))
            return

        if self.type == 'wired' and 83 in bytes:
            return

        oldState = list(self.state)
        self.state = []

        for button in bytes:
            if button == 0: continue
            if button == 1: continue

            self.msg['keycode'] = button
            try:
                self.msg['key'] = self.keycode_map[button]
            except:
                self.msg['key'] = None

            if button not in oldState:
                self.msg['state'] = 'down'
                mqtt.publish(self.topic+'/down', json.dumps(self.msg))
                print ("{}\t{}".format(self.topic+'/down', json.dumps(self.msg)))

                self.msg['state'] = 'repeat'
                repeats.add(self.topic+'/repeat', json.dumps(self.msg))

            self.state.append(button)

        for button in oldState:
            if button not in self.state:
                self.msg['state'] = 'up'
                mqtt.publish(self.topic+'/up', json.dumps(self.msg))
                print ("{}\t{}".format(self.topic+'/up', json.dumps(self.msg)))

                repeats.remove(self.topic+'/repeat')


def thread_device (hid, type):
    keypad = MyKeypad(hid, platform.node(), type)

    while True:
        try:
            keypad.poll()
            time.sleep(5)
        except (KeyboardInterrupt, SystemExit):
            sys.exit(1)
    print ("Failure")

if __name__ == '__main__':

    try:
        daemons = {}
        hids = hid.enumerate()
        for f in hids:
            print ("{}\tvendor={:04x}\tproduct={:04x}".format(f['path'], f['vendor_id'], f['product_id']))

        devs = [f['path'] for f in hids if f['product_id'] == 0x7021 and f['vendor_id'] == 0x04e8]
        for dev in devs:
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'bt302'))

        devs = [f['path'] for f in hids if f['product_id'] == 0x9840 and f['vendor_id'] == 0x05a4]
        for dev in devs:
            print (dev)
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wired'))

        devs = [f['path'] for f in hids if f['product_id'] == 0x4182 and f['vendor_id'] == 0x062a]
        for dev in devs:
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wireless'))

        devs = [f['path'] for f in hids if f['product_id'] == 0x4101 and f['vendor_id'] == 0x2571]
        for dev in devs:
            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'presenter'))

#        devs = [f for f in os.listdir(hidraw_path) if "05A4:9840" in os.path.realpath(hidraw_path + '/' + f)]
#        for dev in devs:
#            print (dev, 'wired')
#            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wired'))

        # devs = [f for f in os.listdir(hidraw_path) if "062A:4182" in os.path.realpath(hidraw_path + '/' + f)]
        # for dev in devs:
        #     print (dev, 'wireless')
        #     daemons[dev] = threading.Thread(target=thread_device, args=(dev,'wireless'))

        # devs = [f for f in os.listdir(hidraw_path) if "04E8:7021" in os.path.realpath(hidraw_path + '/' + f)]
        # for dev in devs:
        #     print (dev, 'bt302')
        #     daemons[dev] = threading.Thread(target=thread_device, args=(dev,'bt302'))

#        devs = [f for f in os.listdir(hidraw_path) if "2571:4101" in os.path.realpath(hidraw_path + '/' + f)]
#        for dev in devs:
#            print (dev, 'presenter')
#            daemons[dev] = threading.Thread(target=thread_device, args=(dev,'presenter'))

        for dev, daemon in daemons.items():
            daemon.daemon = True
            daemon.start()

        while True:
            time.sleep(0.25)
            repeats.process()

    except (KeyboardInterrupt, SystemExit):
        sys.exit(1)
