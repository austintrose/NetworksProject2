# The struct library is used for packing exact binary data.
# https://docs.python.org/2/library/struct.html
import struct

from utils import *


class DataLinkLayer(object):
    def __init__(self, physical_layer):
        self.physical_layer = physical_layer
        self.received_data_buffer = ""

    def recv_one_frame(self):
        # Expected checksum will be first byte of a new frame.
        checksum = self.physical_layer.recv(1)

        # Payload len with be next 4 bytes of a new frame.
        payload_len_packed = self.physical_layer.recv(4)
        payload_len_unpacked = struct.unpack("!I", payload_len_packed)[0]

        # Receive enough for remaining data.
        payload = self.physical_layer.recv(payload_len_unpacked)

        # Compute checksum of data received.
        observed_checksum = self.checksum(payload_len_packed + payload)

        # Compare checksums.
        if checksum == observed_checksum:
            self.received_data_buffer += payload

        # Do nothing if this didn't work.
        # Obviously not what we want.
        # Need to send the nack. Or something.
        else:
            debug_log("Checksum failed.")

    def recv(self, n):
        """
        Receive n correctly-ordered bytes from the data-link layer.
        """
        if len(self.received_data_buffer) < n:
            self.recv_one_frame()

        # Remove `n` bytes from beginning of received data buffer.
        to_return, self.received_data_buffer = \
            self.received_data_buffer[:n], self.received_data_buffer[n:]

        return to_return

    def send(self, data):
        """
        Send data through the data-link layer.
        """

        # Build the header.
        header = self.build_header(data)

        # Attach the header to the data.
        full_frame = header + data

        # Send the full frame through the physical layer.
        self.physical_layer.send(full_frame)

    @staticmethod
    def checksum(data):
        """
        Returns a one-byte checksum of the data.
        """
        checksum = 0
        for character in data:
            checksum ^= ord(character)

        return chr(checksum)

    def build_header(self, data):
        """
        The data link layer header is:
        1 byte  unsigned | checksum of rest of data (header + payload)
        4 bytes unsigned | length of payload to follow
        """

        payload_len = struct.pack("!I", len(data))
        checksum = self.checksum(payload_len + data)

        return payload_len + checksum
