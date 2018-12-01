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
topic_prefix = '/actuator/bedroom/blind2'

mqtt = paho.Client()
mqtt.connect(mqtt_host, 1883, 60)

exiting = False

mqtt_client = None
serial_proxy = None

max_duration = 1000
move_duration = 250
creep_up = 16
last_sent = None
last_pos_recv = None
speed = None
target = None
pos = None

timer = None
timer_freq = 0.1

def get_now():
    return int(time.time() * 1000)

def do_stop():
    speed = None
    target = None
    duration = None
    last_sent = get_now()
    print ("Stop motor")
    serial_proxy.send_move(0, 0)

def periodic_update():
    global timer, max_duration, last_pos_recv
    global speed, duration, target

    if timer is not None:
        timer.cancel()
        timer = None

    now = get_now()

    if (target is not None or speed is not None):
        # If we're intended to be moving
        print ("Periodic moving")

        if (last_pos_recv is None or now - last_pos_recv > max_duration):
            # Position update not received; quit
            do_stop()
        else:
            # Position has updated
            if target is not None:
                if pos == target:
                    # No new schedule
                    do_stop()
                else:
                    # This will schedule the next periodic update
                    do_target(speed, target)
            else:
                print ("Null speed and duration")
                speed = None
                duration = None
                target = None

def schedule_update():
    global timer, timer_freq
    if timer is not None:
        timer.cancel()
    timer = threading.Timer(timer_freq, periodic_update)
    timer.start()

def do_reset():
    serial_proxy.send_reset()

def do_target(_speed, _target):
    global pos, speed, target, move_duration, creep_up

    _speed = int(_speed)
    _target = int(_target)

    if pos is None:
        _speed = 1 if _speed >= 0 else -1
    else:
        if _speed < 1 and _speed > -1: _speed = 1 # Make sure it's not zero(ish)
        # Correct speed direction
        if pos < _target and _speed < 0: _speed = -_speed
        if pos > _target and _speed > 0: _speed = -_speed

        # Slow down if close
        if   pos > _target and pos - _target < creep_up:  _speed = _speed / 2
        elif pos < _target and pos - _target > -creep_up: _speed = _speed / 2

    target = _target
    speed = _speed

    serial_proxy.send_move(speed, move_duration)
    print ("Sending {}, {} (target {})".format(speed, move_duration, target))
    schedule_update()

    #speed = '+{}'.format(speed) if speed >= 0 else speed
    #target = '+{}'.format(target) if target >= 0 else target
    #print 'T{}{}'.format(speed, target)
    #self.send_line('T{}{}'.format(speed, target))

def do_move(_speed, _duration=None):
    global speed, duration, target, move_duration

    if _duration is None:
        _duration = move_duration

    speed = int(_speed)
    duration = int(_duration)
    target = None

    serial_proxy.send_move(speed, duration)
    print ("Sending move {}, {}".format(speed, duration))
    schedule_update()


class mqttClient(threading.Thread):
    def __init__(self, mqtt):
        super(mqttClient, self).__init__()
        self.mqtt = mqtt

    def run(self):
        global exiting
        self.mqtt.on_message = self.onMessage
        self.mqtt.on_disconnect = self.onDisconnect
        self.mqtt.subscribe([(topic_prefix+'/#', 0)])
        try:
            self.mqtt.loop_forever()
        except Exception as e:
            print ("mqttClient Exception:")
            print (e)
            exiting = True
            sys.exit(123)

    def onDisconnect(self, client, userdata, rc):
        print ("Disconnected from MQTT server with code: %s" % rc)
        while rc != 0:
            try:
                rc = self.mqtt.reconnect()
            except Exception as e:
                print ("onDisconnect:")
                print (e)
                sys.exit(124)
        print ("Reconnected to MQTT server.")

    def onMessage (self, mqtt, obj, msg):
        global exiting

        if msg.topic.endswith("/watchdog"):
            return

        print ("{}:\t{}".format(msg.topic, msg.payload))

        if msg.topic.endswith("/restart"):
            exiting = True
            sys.exit(124)

        elif msg.topic.endswith("/target"):
            _target = int(msg.payload)
            do_target(255, _target)

        elif msg.topic.endswith("/direction"):
            _speed = 255 if int(msg.payload) > 0 else -255
            do_move(_speed, None)

        elif msg.topic.endswith("/reset"):
            do_reset()

class serialProxy(serial.threaded.LineReader):
    TERMINATOR = b'\n'
    ENCODING = 'utf-8'
    UNICODE_HANDLING = 'replace'

    def __init__(self):
        super(serialProxy, self).__init__()
        global serial_proxy
        serial_proxy = self

    def handle_packet(self, packet):
        global exiting
        try:
            self.handle_line(packet.decode(self.ENCODING, self.UNICODE_HANDLING))
        except Exception as e:
            print ("handle_line Exception:")
            print (e)
            exiting = True

    def connection_lost(self, e):
        global exiting
        print ("connection_lost Exception:")
        print (e)
        exiting = True

    def send_line(self, s):
        global exiting
        try:
            self.write_line(s)
        except Exception as e:
            print ("send_line Exception:")
            print (e)
            exiting = True

    def send_move(self, speed, duration):
        speed = '+{}'.format(int(speed)) if speed >= 0 else speed
        duration = '+{}'.format(int(duration)) if duration >= 0 else duration
        self.send_line('S{}{}'.format(speed, duration))

    def send_reset(self):
        self.send_line('Z')

    def handle_line (self, line):
        global mqtt_client, pos, last_pos_recv

        if line[0] == 'R':
            pos = int(line[1:])
            last_pos_recv = int(time.time() * 1000)
            print ("Set pos to {}".format(pos))
        else:
            mqtt_client.mqtt.publish(topic_prefix+"/output", payload=line, retain=False)

if __name__ == '__main__':

    print ("Starting")

    while True:
        try:
            # For some reason, systemd passes HUP to the job when starting, so we
            # have to ignore HUP.  Then it has trouble with INT, so best to
            # explicitly exit on INT, and configure systemd to use INT.
            def shutdown_handler(signum, frame):
                print ("Setting running to False")
                shutdown_handler.running = False

            shutdown_handler.running = True
            signal.signal(signal.SIGINT, shutdown_handler)

            # Ignore HUP
            def ignore_handler(signum, frame):
                pass
            signal.signal(signal.SIGHUP, ignore_handler)

            # Find Arduino Nano fake
            dev = [port.device for port in serial.tools.list_ports.comports() if port.vid==0x1a86 and port.pid==0x7523]
            print ("Got dev "+str(dev))
            ser = serial.serial_for_url(dev[0], baudrate=115200)
            print ("Got serial port")
            t = serial.threaded.ReaderThread(ser, serialProxy)
            t.start()

            mqtt_client = mqttClient(mqtt=mqtt)
            mqtt_client.daemon = True
            mqtt_client.start()

            while shutdown_handler.running and not exiting:
                mqtt_client.mqtt.publish(topic_prefix+"/watchdog", payload='ping', retain=False)
                time.sleep(5)

            raise SystemExit()

        except (KeyboardInterrupt, SystemExit) as e:
            mqtt_client.mqtt.publish(topic_prefix+"/exit", payload=str(e), retain=False)
            sys.exit(0)

        except Exception as e:
            print ("Main exception:")
            print (e)
            try:    mqtt_client.mqtt.publish(topic_prefix+"/error", payload=str(e), retain=False)
            except: pass
            time.sleep(5)
            sys.exit(125)
