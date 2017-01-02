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
        self.states = {}

        self.mqtt.on_message = self.onMessage
        self.mqtt.subscribe([('/actuator/bedroom/+',0)])
        self.mqtt.loop_forever()

    def onMessage (self, mqtt, obj, msg):
        print "{}:\t{}".format(msg.topic, msg.payload)

        map = {
            '/actuator/bedroom/bed_light':     ('/actuator/bedroom/rf', 1, 2),
            '/actuator/bedroom/desk_light':    ('/actuator/bedroom/rf', 3, 4),
            '/actuator/bedroom/desk_fan':      ('/actuator/bedroom/rf', 3, 3),
            '/actuator/bedroom/tower_fan':     ('/actuator/bedroom/rf', 1, 1),
            '/actuator/bedroom/desk_monitor':  ('/actuator/bedroom/rf', 3, 2),
            '/actuator/bedroom/ceiling_light': ('/actuator/bedroom/ir/ceiling_light', None, None),
            '/actuator/bedroom/limpet_light':  ('/actuator/bedroom/ir/limpet_light', None, None)
        }

        try:
            (ntopic, bank, chan) = map[msg.topic]
            # Will have failed if not registered

            if msg.payload == '0':
                val = '0'
            elif msg.payload == '1':
                val = '1'
            else:
                bankchan = 'b:{},c:{}'.format(bank,chan)
                try:
                    self.states[bankchan] = not self.states[bankchan]
                except:
                    self.states[bankchan] = True
                val = '1' if self.states[bankchan] else '0'

            if bank is None:
                nmsg = val
            else:
                nmsg = '{'+'"bank":{},"channel":{},"value":{}'.format(bank,chan,val)+'}'

            self.mqtt.publish(ntopic, nmsg)
            print "=> {}: {}".format(ntopic, nmsg)
            return;

        except KeyError:
            # Not in the map, so it's a dial thing; the blind itself
            # should handle it.
            pass

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

