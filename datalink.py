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
        self.send_window_base = 0

        # Next packet to send.
        self.next_seq = 0

        # Number of unacked packets which can remain in the window at once.
        self.window_len = 10


        # Start the dedicated receiver thread.
        self.start_receive_thread()

    def start_receive_thread(self):
        self.receive_thread = Thread(target=self.receive_thread_func)
        self.receive_thread.setDaemon(True)
        self.receive_thread.start()

    def receive_thread_func(self):
        while True:
            self.recv_one_frame()
            time.sleep(0.005)

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

        # Create a timer
        self.t = None

        # Expected next sequence_num.
        self.ack = 0

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
            if payload_len_unpacked == 0:
                self.received_ack(ack_num_unpacked)

            # This is the next expected data chunk.
            elif seq_num_unpacked == self.ack:
                self.ack = seq_num_unpacked + 1
                self.received_data_buffer += payload
                self.send_blank_ack()

            # Otherwise resend an ack for the expected chunk
            else :
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
                self.send_window_base += 1

                # Restart timer
                if len(self.send_window) > 0:
                    self.t.cancel
                    self.start_timer_for(self.next_seq)


            else:
                return

    def resend_on_timeout(self, expected):
        debug_log("Timeout \n")
        if self.send_window_base <= expected:
            for packet in self.send_window:
                self.send_packet(packet)
                debug_log("Resending packet with seqnum" + str(packet['seq']))
        if len(self.send_window) > 0:
            self.start_timer_for(self.send_window_base)


    def send(self, data):
        """
        Send data through the data-link layer.
        """

        if len(data) > 256:
            raise Exception('Chunk from application too large.')

        # Block until the window can take one more packet.
        while len(self.send_window) + 1 > self.window_len:
            time.sleep(0.001)

        # New item to add to the window.
        new_packet = {'seq': self.next_seq, 'data': data}

        # Put the given data at the end of the window.
        debug_log("Adding new packet to send window")
        self.send_window.append(new_packet)
        debug_log("Window length now " + str(len(self.send_window)))

        # Send it along the physical layer.
        self.send_packet(new_packet)

        # Start a timer if this is the first packet in the send window
        if len(self.send_window) == 1:
            self.start_timer_for(self.next_seq)
            debug_log("Timer start")

        # Increment the sequence
        self.next_seq += 1

    def send_packet(self, packet):
        packet = self.build_packet(packet['data'], packet['seq'], self.ack)
        self.physical_layer.send(packet)
        # debug_log("DL send:\n" + " ".join(hex(ord(n)) for n in packet))

    def start_timer_for(self, expected):
        self.t = Timer(0.1, self.resend_on_timeout, [expected])
        self.t.start()


class DataLinkLayer_SR(DataLinkLayer):
    def __init__(self, physical_layer):
        super(DataLinkLayer_SR, self).__init__(physical_layer)

        # Create a receive window
        self.recv_window = []

        # Create a receive window base
        self.recv_window_base = 0

    def send_blank_ack(self, recv_seq_num):
        # Send an ack for the given sequence number
        debug_log("Sending ack for packet " + str(recv_seq_num))
        new_packet = {'seq': self.next_seq, 'ack': recv_seq_num, 'data': ''}
        self.send_packet(new_packet)

    def update_recv_window(self, recv_packet):
        debug_log("Updating receive window with packet seq " + str(recv_packet['seq']))
        # If the receive window is empty, append the packet
        if len(self.recv_window) == 0:
            self.recv_window.append(recv_packet)
        # If the packet is the recv base packet, send up appropriate packets and update the window base
        if recv_packet['seq'] == self.recv_window_base:
            trackseq = self.recv_window_base
            while len(self.recv_window) > 0 and self.recv_window[0]['seq'] == trackseq:
                self.received_data_buffer += self.recv_window[0]['data']
                self.recv_window.pop(0)
                self.recv_window_base += 1
                debug_log("Receive window base now " + str(self.recv_window_base))
                trackseq += 1
        # Otherwise insert the recv packet into the correct place in the list
        else:
            insertindex = 0
            for packet in self.recv_window:
                if recv_packet['seq'] == (packet['seq'] + 1):
                    insertindex += 1
                    self.recv_window.insert(packet, recv_packet)
                    return

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
            if payload_len_unpacked == 0:
                self.received_ack(ack_num_unpacked)

            # This is the next expected data chunk.
            elif seq_num_unpacked >= self.recv_window_base:
                recv_packet = {'seq': seq_num_unpacked, 'data' : payload}
                self.update_recv_window(recv_packet)
                self.send_blank_ack(seq_num_unpacked)

            # Otherwise resend an ack for the already gotten chunk
            else :
                self.send_blank_ack(seq_num_unpacked)

        # Do nothing if this didn't work.
        else:
            debug_log("Checksum failed.")
            # self.send_blank_ack() I don't think we need to ack here


            #debug_log("DL recv:\n" + " ".join(hex(ord(n)) for n in checksum + to_check) + "\n")

    def received_ack(self, ack_num):
        """
        Mark acked packet, or pop it from the window and move forward the send base if it's the first
        """
        debug_log("Received ack with ack_num" + str(ack_num))
        if len(self.send_window) == 0:
            return
        elif self.send_window_base <= ack_num:
            if self.send_window_base == ack_num:
                self.send_window.pop(0)
                self.send_window_base += 1
                while len(self.send_window) > 0 and self.send_window[0]['acked'] == True:
                    self.send_window.pop(0)
                    self.send_window_base += 1
            else:
                for packet in self.send_window:
                    if packet['seq'] == ack_num:
                        packet['acked'] = True
                        return

    def resend_on_timeout(self, seqnum):
        debug_log("Timeout \n")
        if self.send_window_base <= seqnum:
            for packet in self.send_window:
                if packet['seq'] == seqnum:
                    if packet['acked'] == False:
                        self.send_packet(packet)
                        debug_log("Resending packet with seqnum" + str(packet['seq']))
                        self.start_timer_for(seqnum)

    def send(self, data):
        """
        Send data through the data-link layer.
        """

        if len(data) > 256:
            raise Exception('Chunk from application too large.')

        # Block until the window can take one more packet.
        while len(self.send_window) + 1 > self.window_len:
            time.sleep(0.001)

        # New item to add to the window.
        new_packet = {'seq': self.next_seq, 'ack': 0, 'acked': False, 'data': data}

        # Put the given data at the end of the window.
        debug_log("Adding new packet to send window")
        self.send_window.append(new_packet)
        debug_log("Window length now " + str(len(self.send_window)))

        # Send it along the physical layer.
        self.send_packet(new_packet)

        # Start timer for packet
        self.start_timer_for(self.next_seq)
        debug_log("Timer start")

        # Increment the sequence
        self.next_seq += 1

    def send_packet(self, packet):
        packet = self.build_packet(packet['data'], packet['seq'], packet['ack'])
        self.physical_layer.send(packet)
        # debug_log("DL send:\n" + " ".join(hex(ord(n)) for n in packet))

    def start_timer_for(self, seqnum):
        t = Timer(0.1, self.resend_on_timeout, [seqnum])
        t.start()
