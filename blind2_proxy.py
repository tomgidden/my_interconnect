#!/usr/bin/env python

mqtt_host = 'mqtt.home'

import sys
import paho.mqtt.client as paho
import os
import datetime
import threading
import serial
import serial.threaded
import serial.tools.list_ports
import re
import signal
import time

serial_dev = '/dev/ttyUSB'

mqtt = paho.Client()
mqtt.connect(mqtt_host, 1883, 60)

mqtt_client = None
serial_proxy = None

class mqttClient(threading.Thread):
    def __init__(self, mqtt):
        super(mqttClient, self).__init__()
        self.mqtt = mqtt

    def run(self):
        self.mqtt.on_message = self.onMessage
        self.mqtt.on_disconnect = self.onDisconnect
        self.mqtt.subscribe([('/actuator/bedroom/blind2/#', 0)])
        self.mqtt.loop_forever()

    def onDisconnect(self, client, userdata, rc):
        print "Disconnected from MQTT server with code: %s" % rc
        while rc != 0:
            try:
                rc = self.mqtt.reconnect()
            except:
                time.sleep(1)
        print "Reconnected to MQTT server."

    def onMessage (self, mqtt, obj, msg):

        print "{}:\t{}".format(msg.topic, msg.payload)

        if msg.topic.endswith("/direction"):
            speed = 255 if int(msg.payload) > 0 else -255
            serial_proxy.write_line('S{}+10'.format(speed))

class serialProxy(serial.threaded.LineReader):
    TERMINATOR = b'\n'
    ENCODING = 'utf-8'
    UNICODE_HANDLING = 'replace'

    def __init__(self):
        super(serialProxy, self).__init__()
        global serial_proxy
        serial_proxy = self

    def handle_packet(self, packet):
        self.handle_line(packet.decode(self.ENCODING, self.UNICODE_HANDLING))

    def handle_line (self, line):
        global mqtt_client

        print "RX: {}".format(line)

        mqtt_client.mqtt.publish("/actuator/bedroom/blind2", line)

if __name__ == '__main__':

    print "Starting"

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

        # Find Arduino Nano fake
        dev = [port.device for port in serial.tools.list_ports.comports() if port.vid==0x1a86 and port.pid==0x7523]
        ser = serial.serial_for_url(dev[0], baudrate=115200)
        t = serial.threaded.ReaderThread(ser, serialProxy)
        t.start()

        mqtt_client = mqttClient(mqtt=mqtt)
        mqtt_client.daemon = True
        mqtt_client.start()

        while shutdown_handler.running:
            time.sleep(1)
        sys.exit(0)

    except (KeyboardInterrupt, SystemExit) as e:
        print e
        sys.exit(1)

#    except OSError as e:
#        t.reconnect()

    except Exception as e:
        print e
        pass

