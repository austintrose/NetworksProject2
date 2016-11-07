import socket
import random
import time

from threading import Thread

from utils import *


class PhysicalLayer(object):

    def __init__(self, drop_rate, corrupt_rate):
        # Create a socket.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Set SO_REUSEADDR option.
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Store frame drop rate.
        self.drop_rate = float(drop_rate) / 100

        # Store frame corrupt rate.
        self.corrupt_rate = float(corrupt_rate) / 100

        # The receive thread will constantly put things in this buffer.
        self.received_data_buffer = ""

        debug_log("Frame drop rate: %s." % self.drop_rate)
        debug_log("Frame corrupt rate: %s." % self.corrupt_rate)

    def receive_thread_func(self):
        while True:
            got = self.sock.recv(128)

            if got == '':
                print "Connection ended. Nothing to do. Ctrl-C to exit."
                exit(0)

            self.received_data_buffer += got
            time.sleep(0.01)

    def decide_to_drop(self):
        """
        Returns True, at a probablity configured by the --drop command line
        parameter.
        """

        # Don't give a chance to drop if rate is 0.0.
        if self.drop_rate == 0.0:
            return False

        return random.random() < self.drop_rate

    def maybe_corrupt(self, data):
        """
        Returns `data` back, possibly with one byte changed, at a probability
        configured by the --corrupt command line parameter.
        """

        # Don't give it a chance to corrupt if rate is 0.0.
        if self.corrupt_rate == 0.0:
            return data

        # If random doesn't pass rate, then return without corrupting.
        if random.random() > self.corrupt_rate:
            return data

        # Select data index to corrupt.
        corrupt_index = random.randint(0, len(data) - 1)

        # Generate corrupted byte.
        corrupt_byte = chr(random.randint(0, 255))

        # Corrupt the data and return it.
        c_data = list(data)
        c_data[corrupt_index] = corrupt_byte
        c_data = "".join(c_data)

        return c_data

    def start_receive_thread(self):
        self.receive_thread = Thread(target=self.receive_thread_func)
        self.receive_thread.setDaemon(True)
        self.receive_thread.start()

    def send(self, data):
        """
        Send data through the physical layer.
        """

        # Maybe drop and return immediately.
        if self.decide_to_drop():
            return

        # Maybe corrupt the data.
        data = self.maybe_corrupt(data)

        # Send it.
        self.sock.sendall(data)

    def recv(self, n):
        """
        Receive up to n bytes of data from the physical layer.
        """

        # Block until enough data is available.
        while len(self.received_data_buffer) < n:
            pass

        to_return, self.received_data_buffer = \
            self.received_data_buffer[:n], self.received_data_buffer[n:]

        return to_return

class PhysicalLayer_Client(PhysicalLayer):
    def __init__(self, drop_rate, corrupt_rate):
        super(PhysicalLayer_Client, self).__init__(drop_rate, corrupt_rate)

        # Connect to server.
        try:
            self.sock.connect(SERVER_ADDRESS)
        except socket.error:
            print "Connection refused. Exiting."
            sys.exit(0)
        debug_log("Physical Layer client started.")

        # Launch the receiving thread.
        self.start_receive_thread()


class PhysicalLayer_Server(PhysicalLayer):
    def __init__(self, drop_rate, corrupt_rate):
        super(PhysicalLayer_Server, self).__init__(drop_rate, corrupt_rate)

        # Bind socket.
        self.sock.bind(SERVER_ADDRESS)

        # Start listening.
        self.sock.listen(1)

        debug_log("Server listening...")

        # Accept the first connection that comes.
        self.sock, self.remote_addr = self.sock.accept()
        debug_log("Accepted connection from %s." % str(self.remote_addr))

        # Launch the receiving thread.
        self.start_receive_thread()
