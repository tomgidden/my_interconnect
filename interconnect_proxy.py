#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

mqtt_host = 'mqtt.home'

import paho.mqtt.client as mqtt

import signal
import re
import sys
import os
import urllib2
import time
from subprocess import call
import struct
import socket
import threading

import logging
from logging.handlers import TimedRotatingFileHandler


mqttlogh = TimedRotatingFileHandler('/nfs/scratch/interconnect.log', when='midnight')
mqttlogh.setFormatter(logging.Formatter('%(asctime)s\t%(message)s'))

mqttlog = logging.getLogger('interconnect')
mqttlog.setLevel(logging.INFO)
mqttlog.addHandler(mqttlogh)




class shuttleProxy(threading.Thread):

    def __init__(self, mqtt=None):
        super(shuttleProxy, self).__init__()
        self.mqtt = mqtt
        self.states = {}

    def run(self):
        self.mqtt.on_message = self.onMessage
        self.mqtt.on_disconnect = self.onDisconnect
        self.mqtt.subscribe([('/actuator/bedroom/+',0)])
        self.mqtt.loop_forever()

    def onDisconnect(self, client, userdata, rc):
        print "Disconnected from MQTT server with code: %s" % rc
        while rc != 0:
            time.sleep(1)
            rc = self.mqtt.reconnect()
        print "Reconnected to MQTT server."

    def onMessage (self, mqtt, obj, msg):
        print "{}:\t{}".format(msg.topic, msg.payload)
        mqttlog.info("{}\t{}".format(msg.topic, msg.payload))

        map = {
            '/actuator/bedroom/bed_light':     ('/actuator/bedroom/rf', 1, 2, msg.payload),
            '/actuator/bedroom/desk_light':    ('/actuator/bedroom/rf', 3, 4, msg.payload),
            '/actuator/bedroom/shelf_light':   ('/actuator/bedroom/rf', 3, 1, msg.payload),
            '/actuator/bedroom/desk_fan':      ('/actuator/bedroom/rf', 3, 3, msg.payload),
            '/actuator/bedroom/tower_fan':     ('/actuator/bedroom/rf', 1, 1, msg.payload),
            '/actuator/bedroom/desk_monitor':  ('/actuator/bedroom/rf', 3, 2, msg.payload),
            '/actuator/bedroom/ceiling_light': ('/actuator/bedroom/rf', 4, 1, 0),
            '/actuator/bedroom/limpet_light':  ('/actuator/bedroom/ir/limpet_light', None, None, 'toggle')
        }

        try:
            (ntopic, bank, chan, val) = map[msg.topic]
            # Will have failed if not registered

            if val == 'toggle':
                bankchan = 'b:{},c:{}'.format(bank,chan)
                try:
                    self.states[bankchan] = not self.states[bankchan]
                except:
                    self.states[bankchan] = True
                val = '1' if self.states[bankchan] else '0'

            val = str(val)

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

    try:
        # For some reason, systemd passes HUP to the job when starting, so we
        # have to ignore HUP.  Then it has trouble with INT, so best to
        # explicitly exit on INT, and configure systemd to use INT.
        def shutdown_handler(signum, frame):
            print "Setting running to False"
            shutdown_handler.running = False

        shutdown_handler.running = True
        signal.signal(signal.SIGINT, shutdown_handler)

        # Ignore HUP
        def ignore_handler(signum, frame):
            pass
        signal.signal(signal.SIGHUP, ignore_handler)


        client = mqtt.Client()
        client.connect(mqtt_host, 1883, 60)

        handler = shuttleProxy(mqtt=client)
        handler.daemon = True
        handler.start()

        while shutdown_handler.running:
            time.sleep(1)
        sys.exit(0)

    except (KeyboardInterrupt, SystemExit):
        sys.exit(1)

    except Exception as e:
        print e
        pass

