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

        # Next packet to send.
        self.next_seq = 0

        # Number of unacked packets which can remain in the window at once.
        self.window_len = 10

    def start_receive_thread(self):
        self.receive_thread = Thread(target=self.receive_thread_func)
        self.receive_thread.setDaemon(True)
        self.receive_thread.start()

    def receive_thread_func(self):
        while True:
            self.recv_one_frame()
            time.sleep(0.05)

    def recv(self, n):
        """
        Receive n correctly-ordered bytes from the data-link layer.
        """

        # Block the application from receiving until we have enough data.
        while len(self.received_data_buffer) < n:
            time.sleep(0.5)

        # Remove `n` bytes from beginning of received data buffer.
        to_return, self.received_data_buffer = \
            self.received_data_buffer[:n], self.received_data_buffer[n:]

        return to_return

    @staticmethod
    def checksum(data, pack=True):
        """
        Returns a one-byte checksum of the data.
        """
        checksum = 0
        for character in data:
            checksum += ord(character)

        for character in data[::2]:
            checksum += ord(character)

        for character in data[1::2]:
            checksum += ord(character)

        for character in data[1::3]:
            checksum += ord(character)

        # Keep it below four byte unsigned max.
        checksum = checksum % (2**32)

        if pack:
            return struct.pack("!I", checksum)
        else:
            return checksum


    def build_packet(self, payload, seq):
        seq_num = struct.pack("!I", seq)
        ack_num = struct.pack("!I", self.ack)
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

        # Expected sequence number
        self.ack = 0

        # Start the dedicated receiver thread.
        self.start_receive_thread()

    def send_blank_ack(self):
        # Create a packet containing the ack number
        new_packet = {'seq': self.next_seq, 'data': ''}

        #Send the ack packet
        self.send_packet(new_packet)

    def recv_one_frame(self):

        # Expected checksum will be first 2 bytes of a new frame.
        checksum_packed = self.physical_layer.recv(4)
        checksum_unpacked = struct.unpack("!I", checksum_packed)[0]

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
        if payload_len_unpacked > 0:
            payload = self.physical_layer.recv(payload_len_unpacked)
        else:
            payload = ''

        # This is the data which should match the checksum.
        to_check = seq_num_packed + ack_num_packed + payload_len_packed + \
                   payload

        # Compute checksum of data received.
        observed_checksum = self.checksum(to_check, pack=False)

        # Compare checksums.
        if checksum_unpacked == observed_checksum:
            print "Got SEQ:%d ACK:%d" % (seq_num_unpacked, ack_num_unpacked)
            self.received_ack(ack_num_unpacked)

            # This is an expected data chunk
            if seq_num_unpacked == self.ack and len(payload) > 0:
                self.received_data_buffer += payload
                self.ack = seq_num_unpacked + 1

        if payload_len_unpacked != 0:
            self.send_blank_ack()


    def received_ack(self, ack_num):
        """
        The next packet they expect is `ack_num`. Remove anything else from
        send window.
        """

        # Do nothing if the send window is empty
        if len(self.send_window) == 0:
            return

        while True:
            if self.send_window and self.send_window[0]['seq'] < ack_num:
                self.send_window = self.send_window[1:]
            else:
                break

    def resend_on_timeout(self, seqnum):
        if len(self.send_window) == 0:
            return

        if self.ack <= seqnum:
            for packet in self.send_window:
                if packet['seq'] <= seqnum:
                    self.send_packet(packet)
            if len(self.send_window) != 0:
                self.start_timer_for(self.send_window[0]['seq'])
        else:
            self.start_timer_for(self.next_seq - 1)


    def send(self, data):
        """
        Send data through the data-link layer.
        """

        if len(data) > 256:
            raise Exception('Chunk from application too large.')

        # Block until the window can take one more packet.
        while len(self.send_window) + 1 > self.window_len:
            time.sleep(0.5)

        # New item to add to the window.
        new_packet = {'seq': self.next_seq, 'data': data}

        # Put the given data at the end of the window.
        self.send_window.append(new_packet)

        # Send it along the physical layer.
        self.send_packet(new_packet)

        # Start timer for packet if it is the only thing in the send window.
        if len(self.send_window) == 1:
            self.start_timer_for(self.next_seq)

        # Increment the sequence
        self.next_seq += 1

    def send_packet(self, pk):
        packet = self.build_packet(pk['data'], pk['seq'])
        self.physical_layer.send(packet)
        print "Sent SEQ:%d ACK:%d" % (pk['seq'], self.ack)

    def start_timer_for(self, seqnum):
        t = Timer(0.3, self.resend_on_timeout, [seqnum])
        t.start()

class DataLinkLayer_SR(DataLinkLayer):
    pass
