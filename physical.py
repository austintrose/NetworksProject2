import argparse
import socket
import random

from utils import *


class PhysicalLayer(object):
    def __init__(self):
        # Parse command line args.
        p = argparse.ArgumentParser()
        p.add_argument('--client', action='store_true')
        p.add_argument('--drop', type=int, default=DEFAULT_DROP_RATE)
        p.add_argument('--corrupt', type=int, default=DEFAULT_CORRUPTION_RATE)

        args = p.parse_args()

        # Create a socket.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Set SO_REUSEADDR option.
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Store whether we're started as client or server.
        self.is_client = args.client

        # Store frame drop rate.
        self.drop_rate = float(args.drop) / 100

        # Store frame corrupt rate.
        self.corrupt_rate = float(args.corrupt) / 100

        # Initialize as appropriate, either as client or as server.
        if self.is_client:
            self.init_client()
        else:
            self.init_server()

    def init_client(self):
        """
        Initialize physical layer as application client.
        """
        debug_log("Client starting...")
        debug_log("Frame drop rate: %s." % self.drop_rate)
        debug_log("Frame corrupt rate: %s." % self.corrupt_rate)

        # Connect to server.
        try:
            self.sock.connect(SERVER_ADDRESS)
        except socket.error:
            print "Connection refused. Exiting."
            sys.exit(0)
        debug_log("Client started.")

    def init_server(self):
        """
        Initialize physical layer as application server.
        """
        debug_log("Server starting...")
        debug_log("Frame drop rate: %s." % self.drop_rate)
        debug_log("Frame corrupt rate: %s." % self.corrupt_rate)

        # Bind socket.
        self.sock.bind(SERVER_ADDRESS)

        # Start listening.
        self.sock.listen(1)

        debug_log("Server listening...")

        # Accept the first connection that comes.
        self.sock, self.remote_addr = self.sock.accept()
        debug_log("Accepted connection from %s." % str(self.remote_addr))

    def decide_to_drop(self):
        """
        Returns True, at a probablity configured by the --drop command line
        parameter.
        """
        return random.random() < self.drop_rate

    def maybe_corrupt(self, data):
        """
        Returns `data` back, possibly with one byte changed, at a probability
        configured by the --corrupt command line parameter.
        """

        # Return immediately, or corrupt the data.
        if random.random() > self.corrupt_rate:
            return data

        # Select data index to corrupt.
        corrupt_index = random.randint(0, len(data) - 1)

        # Generate corrupted byte.
        corrupt_byte = chr(random.randint(0, 255))

        # Corrupt the data and return it.
        data = list(data)
        data[corrupt_index] = corrupt_byte
        data = "".join(data)

        debug_log("Corrupted frame.")

        return data

    def send(self, data):
        """
        Send data through the physical layer.
        """

        # Maybe drop and return immediately.
        if self.decide_to_drop():
            debug_log("Dropped frame.")
            return

        # Maybe corrupt the data.
        data = self.maybe_corrupt(data)

        # Send it.
        self.sock.sendall(data)

    def recv(self, n):
        """
        Receive up to n bytes of data from the physical layer.
        """
        got = self.sock.recv(n)

        if got == '':
            print "Connection ended. Exiting."
            sys.exit(0)

        return got
