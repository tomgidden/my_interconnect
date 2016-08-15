import time
import struct

class ShuttleXpress () :

    def __init__(self, device):

        self.device = device

        self.state = {
            'ring': 0,
            'dial': 999,
            'delta': 0,
            'button1': 0,
            'button2': 0,
            'button3': 0,
            'button4': 0,
            'button5': 0
        }

    def poll (self):

        try:
            with open(self.device, 'r') as f:

                buf = f.read(5)
                while buf:
                    bytes = struct.unpack('bBBBB', buf)

                    self.process(bytes)

                    buf = f.read(5)

        except IOError:
            pass

    def process (self, bytes) :

        oldState = self.state

        self.state = {
            'ring': bytes[0],
            'dial': bytes[1],
            'button1': (bytes[3] & 16) != 0,
            'button2': (bytes[3] & 32) != 0,
            'button3': (bytes[3] & 64) != 0,
            'button4': (bytes[3] & 128) != 0,
            'button5': (bytes[4] != 0)
        }

        if oldState['dial'] == 999:
            self.state['delta'] = 0
        elif oldState['dial'] > 240 and self.state['dial'] < 10:
            self.state['delta'] = oldState['dial'] - self.state['dial'] - 254
        elif oldState['dial'] < 10 and self.state['dial'] > 240:
            self.state['delta'] = oldState['dial'] - self.state['dial'] + 254
        else:
            self.state['delta'] = self.state['dial'] - oldState['dial']

        try:
            if oldState['ring'] != self.state['ring']:
                self.onRing(self.state['ring'])
        except AttributeError:
            pass

        try:
            if self.state['delta'] != 0:
                self.onDial(self.state['dial'], self.state['delta'])
        except AttributeError:
            pass

        for x in range(1,6):
            utton = 'utton' + str(x)
            if oldState['b'+utton] != self.state['b'+utton]:
                try:
                    getattr(self, 'onB'+utton)(self.state['b'+utton])
                except AttributeError as e:
                    pass

                try:
                    self.onButton(x, self.state['b'+utton])
                except AttributeError as e:
                    pass
