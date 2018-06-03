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
            serial_proxy.send_move(speed, '+10')

        elif msg.topic.endswith("/target"):
            target = int(msg.payload)
            serial_proxy.send_target(255, target)

        elif msg.topic.endswith("/reset"):
            serial_proxy.send_reset()

class serialProxy(serial.threaded.LineReader):
    TERMINATOR = b'\n'
    ENCODING = 'utf-8'
    UNICODE_HANDLING = 'replace'

    def __init__(self):
        super(serialProxy, self).__init__()
        global serial_proxy
        serial_proxy = self
        self.pos = None

    def handle_packet(self, packet):
        self.handle_line(packet.decode(self.ENCODING, self.UNICODE_HANDLING))

    def send_move(self, speed, distance):
        speed = int(speed)
        speed = '+{}'.format(speed) if speed > 0 else speed

        distance = int(distance)
        distance = '+{}'.format(distance) if distance > 0 else distance

        self.write_line('S{}{}'.format(speed, distance))

    def send_reset(self):
        self.write_line('Z')

    def send_target(self, speed, target):
        speed = int(speed)
        target = int(target)

        if self.pos is None:
            speed = 1 if speed >= 0 else -1
        else:
            if self.pos < target and speed < 0: speed = -speed
            if self.pos > target and speed > 0: speed = -speed

            if   self.pos > target and self.pos - target < 20:  speed = speed / 2
            elif self.pos < target and self.pos - target > -20: speed = speed / 2

        speed = '+{}'.format(speed) if speed >= 0 else speed
        target = '+{}'.format(target) if target >= 0 else target

        print 'T{}{}'.format(speed, target)
        self.write_line('T{}{}'.format(speed, target))

    def handle_line (self, line):
        global mqtt_client

        if line[0] == 'R':
            mqtt_client.mqtt.publish("/actuator/bedroom/blind2/position", payload=line[1:], retain=True)
            self.pos = int(line[1:])
            print "Set pos to {}".format(self.pos)
        else:
            mqtt_client.mqtt.publish("/actuator/bedroom/blind2/output", payload=line, retain=False)

if __name__ == '__main__':

    print "Starting"

    while True:
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
            sys.exit(0)

    #    except OSError as e:
    #        t.reconnect()

        except Exception as e:
            print e
            sys.exit(1)
