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
            time.sleep(0.1)

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

        # Keep it below two byte unsigned max.
        checksum = checksum % 65536

        if pack:
            return struct.pack("!H", checksum)
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
        checksum_packed = self.physical_layer.recv(2)
        checksum_unpacked = struct.unpack("!H", checksum_packed)[0]

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

            # This is just a blank ack of our data.
            if payload_len_unpacked == 0:
                debug_log("Received blank. SEQ: %d, ACK: %d" % (
                    seq_num_unpacked, ack_num_unpacked))
                self.received_ack(ack_num_unpacked)

            # This is an expected data chunk
            elif seq_num_unpacked == self.ack:
                debug_log("Received data. SEQ: %d, ACK: %d" % (
                    seq_num_unpacked, ack_num_unpacked))
                self.received_data_buffer += payload
                self.ack = seq_num_unpacked + 1
                self.received_ack(ack_num_unpacked)
                self.send_blank_ack()

            else:
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
                self.send_window.pop(0)
            else:
                break

    def resend_on_timeout(self, seqnum):
        debug_log("Resend on timeout for seq %d" % seqnum)

        if len(self.send_window) == 0:
            return

        # If the timer runs out resend all packets in window
        for packet in self.send_window:
            if packet['seq'] <= seqnum:
                self.send_packet(packet)

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
        if len(pk['data']) > 2:
            debug_log("Sending data. SEQ: %d, ACK: %d" % (pk['seq'],
                                                          self.ack))
        else:
            debug_log("Sending blank. SEQ: %d, ACK: %d" % (pk['seq'],
                                                          self.ack))
        self.physical_layer.send(packet)

    def start_timer_for(self, seqnum):
        t = Timer(1, self.resend_on_timeout, [seqnum])
        t.start()

class DataLinkLayer_SR(DataLinkLayer):
    pass
