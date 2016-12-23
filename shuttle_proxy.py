#!/usr/bin/python
# -*- coding: utf-8 -*-

mqtt_host = 'mqtt.home'

import paho.mqtt.client as mqtt

import re
import sys
import os
import urllib2
import time
from subprocess import call
import struct
import socket
import threading


class shuttleProxy(object):

    def __init__(self, mqtt=None):
        self.mqtt = mqtt
        self.blind_pos = 50
        self.states = {}
        self.rung = None

        self.mqtt.on_message = self.onMessage
        self.mqtt.subscribe([('/controller/+/+/button/+',0),
                             ('/controller/+/+/dial', 0),
                             ('/controller/+/+/ring', 0)])
        self.mqtt.loop_forever()

    def onMessage (self, mqtt, obj, msg):
        print "{}:\t{}".format(msg.topic, msg.payload)

        m = re.search('/controller/.+/(button|dial|ring)(/(\d))?', msg.topic)

        if m is not None:
            if m.group(1) == 'button' and m.group(3):
                self.onButton(int(m.group(3)), int(msg.payload))

            elif m.group(1) == 'ring':
                self.onRing(int(msg.payload))

            elif m.group(1) == 'dial':
                self.onDial(int(msg.payload))

    def onButton (self, button, val):

        tokens = [
            None,
            ('irsend','bank1','BANK1_2'), # bed
            ('irsend','bank3','BANK3_4'), # desk
            ('irsend','bank3','BANK3_3'), # fluo
            ('irsend','bank1','BANK1_1'), # fan
            ('irsend','bank3','BANK3_2')  # Dell monitor
#            ('url','http://pile/~gid/sleep.php',None), # monitor
        ]

        if val:
            if tokens[button] is not None:

                (cmd, bank, chan) = tokens[button]

                if cmd == 'irsend':
                    try:
                        self.states[chan] = not self.states[chan]
                    except:
                        self.states[chan] = True

                    x = '1' if self.states[chan] else '0'
                    call(['/usr/bin/irsend','SEND_ONCE','--count=3',bank, chan+x])

                elif cmd == 'url':
                    urllib2.urlopen(bank).read()

    def tilt (self):
        str = "/actuator/blind1/tilt"
        print "{}:\t{}".format(str, self.blind_pos)
        self.mqtt.publish(str, self.blind_pos)

    def onRing (self, dir):

        if dir == 0:
            self.rung = None

        elif dir < -1 and self.rung != -1:
            self.blind_pos = 0
            self.tilt()
            self.rung = -1

        elif dir > 1 and self.rung != 1:
            self.blind_pos = 100
            self.tilt()
            self.rung = 1

    def onDial (self, delta):
        self.rung = None
        self.blind_pos += delta*5

        if self.blind_pos > 100:
            self.blind_pos = 100
        elif self.blind_pos < 0:
            self.blind_pos = 0

        self.tilt()


if __name__ == '__main__':

    while True:
        try:
            client = mqtt.Client()
            client.connect(mqtt_host, 1883, 60)

            handler = shuttleProxy(mqtt=client)
            handler.loop()

        except (KeyboardInterrupt, SystemExit):
            sys.exit(1)

        except Exception as e:
            print e
            pass

