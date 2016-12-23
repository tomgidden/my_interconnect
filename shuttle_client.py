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

from shuttlexpress import ShuttleXpress

try:
    mqtt = paho.Client()
    mqtt.connect(mqtt_host, 1883, 60)
    mqtt.loop_start()
except e:
    print "MQTT error: "+str(e)
    pass

device = '/dev/shuttlexpress'

hidraw_path = '/sys/class/hidraw'


class MyShuttleXpress(ShuttleXpress):
    def __init__(self, fn, host, dev):
        self.host = host
        self.dev = dev
        ShuttleXpress.__init__(self, fn)

    def onButton (self, button, val):
        str = "/controller/{}/{}/button/{}".format(self.host, self.dev, button)
        mqtt.publish(str, int(val))
        print "{}:\t{}".format(str, int(val))

    def onRing (self, dir):
        str = '/controller/{}/{}/ring'.format(self.host, self.dev)
        mqtt.publish(str, dir)
        print "{}:\t{}".format(str, dir)

    def onDial (self, pos, delta):
        str = '/controller/{}/{}/dial'.format(self.host, self.dev)
        mqtt.publish(str, delta)
        print "{}:\t{}".format(str, delta)

def thread_device (dev):
    fn = "/dev/"+dev
    shuttle = MyShuttleXpress(fn, platform.node(), dev)

    while True:
        try:
            shuttle.poll()
            if os.path.exists(fn):
                time.sleep(5)
            else:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            sys.exit(1)
        print "Failure"

if __name__ == '__main__':

    devs = [f for f in os.listdir(hidraw_path) if "0B33:0020" in os.path.realpath(hidraw_path + '/' + f)]

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
