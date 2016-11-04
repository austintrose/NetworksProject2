# The struct library is used for packing exact binary data.
# https://docs.python.org/2/library/struct.html
import struct
import time
from threading import Thread, Timer

from utils import *


class DataLinkLayer(object):
    def __init__(self, physical_layer):
        self.physical_layer = physical_layer

        # Buffer for data that has been processed correctly, but that the
        # application has not requested.
        self.received_data_buffer = ""

        # Buffer for data that the application has sent, but that has not been
        # acked yet. This must not be longer than `self.window_len`
        self.send_window = []

        # What packet send_window starts at.
        self.window_base = 0

        # Next packet to send.
        self.next_seq = 0

        # Number of unacked packets which can remain in the window at once.
        self.window_len = 10

        # Expected next sequence_num.
        self.ack = 0

        # Start the dedicated receiver thread.
        self.start_receive_thread()

    def start_receive_thread(self):
        self.receive_thread = Thread(target=self.receive_thread_func)
        self.receive_thread.setDaemon(True)
        self.receive_thread.start()

    def receive_thread_func(self):
        while True:
            self.recv_one_frame()
            time.sleep(0.05)

    def send_blank_ack(self):
        new_packet = {'seq': self.next_seq, 'data': ''}
        self.send_packet(new_packet)

    def recv_one_frame(self):

        # Expected checksum will be first byte of a new frame.
        checksum = self.physical_layer.recv(1)

        # Sequence number is next 4 bytes.
        seq_num_packed = self.physical_layer.recv(4)
        seq_num_unpacked = struct.unpack("!I", seq_num_packed)[0]

        # Acknowledgement number is next 4 bytes.
        ack_num_packed = self.physical_layer.recv(4)
        ack_num_unpacked = struct.unpack("!I", ack_num_packed)[0]

        # Payload len is next byte.
        payload_len_packed = self.physical_layer.recv(1)
        payload_len_unpacked = struct.unpack("!B", payload_len_packed)[0]

        # Receive enough for remaining data.
        payload = self.physical_layer.recv(payload_len_unpacked)

        # This is the data which should match the checksum.
        to_check = seq_num_packed + ack_num_packed + payload_len_packed + \
                   payload

        # Compute checksum of data received.
        observed_checksum = self.checksum(to_check)


        # Compare checksums.
        if checksum == observed_checksum:

            # This is just a blank ack of our data.
            if len(payload) == 0:
                self.received_ack(ack_num_unpacked)

            # This is the next expected data chunk.
            elif seq_num_unpacked == self.ack:
                self.ack = seq_num_unpacked + 1
                self.received_data_buffer += payload
                self.send_blank_ack()

        # Do nothing if this didn't work.
        else:
            debug_log("Checksum failed.")
            self.send_blank_ack()


        #debug_log("DL recv:\n" + " ".join(hex(ord(n)) for n in checksum + to_check) + "\n")

    def received_ack(self, ack_num):
        """
        Pop things off the window which have been acked.
        """

        while True:
            if len(self.send_window) == 0:
                return

            elif self.send_window[0]['seq'] < ack_num:
                self.send_window.pop(0)
                self.window_base += 1

            else:
                return

    def recv(self, n):
        """
        Receive n correctly-ordered bytes from the data-link layer.
        """

        # Block the application from receiving until we have enough data.
        while len(self.received_data_buffer) < n:
            pass

        # Remove `n` bytes from beginning of received data buffer.
        to_return, self.received_data_buffer = \
            self.received_data_buffer[:n], self.received_data_buffer[n:]

        return to_return

    def send(self, data):
        """
        Send data through the data-link layer.
        """

        if len(data) > 256:
            raise Exception('Chunk from application too large.')

        # Block until the window can take one more packet.
        while len(self.send_window) + 1 > self.window_len:
            time.sleep(0.01)

        # New item to add to the window.
        new_packet = {'seq': self.next_seq, 'data': data}

        # Put the given data at the end of the window.
        self.send_window.append(new_packet)

        # Send it along the physical layer.
        self.send_packet(new_packet)

        # Start a timer for resending if this wasn't acked.
        self.start_timer_for(self.next_seq)
        self.next_seq += 1

    def send_packet(self, packet):
        packet = self.build_packet(packet['data'], packet['seq'], self.ack)
        self.physical_layer.send(packet)
        # debug_log("DL send:\n" + " ".join(hex(ord(n)) for n in packet))

    def start_timer_for(self, expected):
        t = Timer(0.1, self.resend_on_timeout, [expected])
        t.start()

    def resend_on_timeout(self, expected):
        if self.window_base < expected:
            for packet in self.send_window:
                self.send_packet(packet)


    @staticmethod
    def checksum(data):
        """
        Returns a one-byte checksum of the data.
        """
        checksum = 0
        for character in data:
            checksum ^= ord(character)

        return chr(checksum)

    def build_packet(self, payload, seq, ack):
        seq_num = struct.pack("!I", seq)
        ack_num = struct.pack("!I", ack)
        payload_len = struct.pack("!B", len(payload))

        # The data to prepend a checksum to.
        to_check = seq_num + ack_num + payload_len + payload

        # Compute checksum.
        checksum = self.checksum(to_check)

        # Return full packet.
        return checksum + to_check


class DataLinkLayer_GBN(DataLinkLayer):
    def __init__(self, physical_layer):
        super(DataLinkLayer_GBN, self).__init__(physical_layer)


class DataLinkLayer_SR(DataLinkLayer):
    def __init__(self, physical_layer):
        super(DataLinkLayer_SR, self).__init__(physical_layer)
