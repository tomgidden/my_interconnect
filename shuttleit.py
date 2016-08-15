#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import urllib2
import time
from subprocess import call
import struct
import socket
import threading

from shuttlexpress import ShuttleXpress

device = '/dev/shuttlexpress'

#blind_sock = ('192.168.7.60', 3000)
blind_path = '/dev/rfcomm0'

hidraw_path = '/sys/class/hidraw'


class MyShuttleXpress(ShuttleXpress):
    def __init__(self, device):
        ShuttleXpress.__init__(self, device)
        self.blind_pos = 50
        self.states = {}

    def onButton (self, button, val):
        tokens = [
            None,
            ('irsend','bank1','BANK1_2'), # bed
            ('irsend','bank3','BANK3_4'), # desk
            ('irsend','bank3','BANK3_3'), # fluo
            ('irsend','bank1','BANK1_1'), # fan
            ('url','http://pile/~gid/sleep.php',None), # monitor
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

    def onDial (self, pos, delta):
        self.blind_pos += delta*5

        if self.blind_pos > 100:
            self.blind_pos = 100
        elif self.blind_pos < 0:
            self.blind_pos = 0

        b = 10 * int(self.blind_pos / 10)
        b = (b - 50) * 6 / 5

        open(blind_path, "a").write("servo1.angle({})\r".format(b))

        #s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #s.connect(blind_sock)
        #s.send("blind/tilt/{}\n".format(self.blind_pos))
        #s.close()

def thread_device (dev):
    fn = "/dev/"+dev
    shuttle = MyShuttleXpress(fn)

    while True:
        shuttle.poll()
        if os.path.exists(fn):
            time.sleep(5)
        else:
            time.sleep(60)

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

#    shuttle = MyShuttleXpress(device)

#    while True:
#        shuttle.poll()
#        time.sleep(5)
