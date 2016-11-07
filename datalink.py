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

'''
class DataLinkLayer_GBN(DataLinkLayer):
    def __init__(self, physical_layer):
        super(DataLinkLayer_GBN, self).__init__(physical_layer)

        # Expected sequence_num.
        self.ack = 0

        #Timer
        self.t = None

    def send_blank_ack(self, acknum):
        new_packet = {'seq': self.next_seq, 'ack': acknum, 'data': ''}
        debug_log("Sending ack for packet " + str(acknum))
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
                debug_log("Received packet with sequence number " + str(seq_num_unpacked))
                self.received_data_buffer += payload
                self.ack += 1
                self.send_blank_ack(seq_num_unpacked)

            # Otherwise resend an ack for the last correctly received packet
            else :
                if not self.ack == 0 :
                    self.send_blank_ack(self.ack - 1)
                else:
                    self.send_blank_ack(0)

        # Do nothing if this didn't work.
        else:
            debug_log("Checksum failed.")
            if not self.ack == 0:
                self.send_blank_ack(self.ack - 1)
            else:
                self.send_blank_ack(0)

    def received_ack(self, ack_num):
        """
        Pop things off the window which have been acked.
        """
        debug_log("Received ack for packet " + str(ack_num))
        debug_log("Current send window base is " + str(self.send_window_base))
        for apacket in self.send_window:
            debug_log("Send window has packet " + str(apacket['seq']))

        # If the send window is empty return
        if len(self.send_window) == 0:
            return

        # If the ack value is below the window base or above the threshold return
        elif self.send_window[0]['seq'] > ack_num or ack_num > (self.send_window[0]['seq'] + self.window_len):
            return

        else:

            # Send up all packets with sequence numbers up to the ack value
            while len(self.send_window) > 0 and self.send_window[0]['seq'] <= ack_num:
                self.send_window.pop(0)
                self.send_window_base += 1
                debug_log("New send window base is " + str(self.send_window_base))

            # Restart the timer
            if len(self.send_window) > 0:
                self.t.cancel
                self.start_timer_for(self.next_seq)

    def resend_on_timeout(self, expected):
        debug_log("Timeout")
        # On timeout, resend all packets in the window
        if len(self.send_window) > 0:
            for packet in self.send_window:
                self.send_packet(packet)
                debug_log("Resending packet " + str(packet['seq']))

            # Restart the timer
            self.start_timer_for(self.next_seq)

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
        new_packet = {'seq': self.next_seq, 'ack': 0, 'data': data}

        debug_log("Sending packet " + str(new_packet['seq']))

        # Put the given data at the end of the window.
        self.send_window.append(new_packet)

        # Send it along the physical layer.
        self.send_packet(new_packet)

        # Start a timer if this is the first packet in the send window
        if len(self.send_window) == 1:
            self.start_timer_for(self.next_seq)
            debug_log("Timer start")

        # Increment the sequence
        self.next_seq += 1

    def send_packet(self, packet):
        packet = self.build_packet(packet['data'], packet['seq'], packet['ack'])
        self.physical_layer.send(packet)

    def start_timer_for(self, expected):
        self.t = Timer(0.1, self.resend_on_timeout, [expected])
        self.t.start()
'''

class DataLinkLayer_GBN(DataLinkLayer):
    def __init__(self, physical_layer):
        super(DataLinkLayer_GBN, self).__init__(physical_layer)

        #Expected sequence number
        self.ack = 0

    def send_blank_ack(self, recv_seq_num):
        # Create a packet containing the ack number
        debug_log("Sending ack for packet " + str(recv_seq_num))
        new_packet = {'seq': self.next_seq, 'ack': recv_seq_num, 'data': ''}

        #Send the ack packet
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
            debug_log("Received packet " + str(ack_num_unpacked))
            # This is just a blank ack of our data.
            if payload_len_unpacked == 0:
                self.received_ack(ack_num_unpacked)

            # This is an expected data chunk
            elif seq_num_unpacked == self.ack:
                debug_log("Sending up packet " + str(seq_num_unpacked))
                self.received_data_buffer += payload
                self.send_blank_ack(seq_num_unpacked)
                self.ack = seq_num_unpacked + 1
                debug_log("New ack value " + str(self.ack))

            # Otherwise resend an ack for the already gotten chunk
            else :
                if not self.ack == 0:
                    self.send_blank_ack(self.ack)
                else:
                    self.send_blank_ack(0)

        # Do nothing if this didn't work.
        else:
            debug_log("A Checksum failed.")
            if not self.ack == 0:
                self.send_blank_ack(self.ack)
            else:
                self.send_blank_ack(0)
            # self.send_blank_ack() I don't think we need to ack here

    def received_ack(self, ack_num):
        """
        Mark acked packet, or pop it from the window and move forward the send base if it's the first
        """

        debug_log("Received ack for " + str(ack_num))

        # Do nothing if the send window is empty
        if len(self.send_window) == 0:
            return

        elif not ack_num < self.send_window_base and not ack_num > (self.send_window_base + self.window_len):

            # Remove all consecutive acked packets whose sequence values match the increasing base
            while len(self.send_window) > 0 and self.send_window[0]['seq'] < ack_num:
                debug_log("Pop frame " + str(self.send_window[0]['seq']))
                self.send_window.pop(0)
                self.send_window_base += 1
                debug_log("Send window base now " + str(self.send_window_base))

            # Reset timer
            if len(self.send_window) > 0:
                self.start_timer_for(self.send_window[0]['seq'])

    def resend_on_timeout(self, seqnum):
        debug_log("Timeout \n")

        # If the timer runs out resend all packets in window
        if not self.send_window_base > seqnum:
            if len(self.send_window) > 0:
                for packet in self.send_window:
                    debug_log("Resending packet " + str(packet['seq']))
                    self.send_packet(packet)
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
        new_packet = {'seq': self.next_seq, 'ack': 0, 'data': data}

        # Put the given data at the end of the window.
        self.send_window.append(new_packet)

        # Send it along the physical layer.
        self.send_packet(new_packet)

        debug_log("Sending packet " + str(self.next_seq))

        # Start timer for packet if it is the only thing in the send window
        if len(self.send_window) == 1:
            self.start_timer_for(self.next_seq)
            debug_log("Timer start")

        # Increment the sequence
        self.next_seq += 1

    def send_packet(self, packet):
        packet = self.build_packet(packet['data'], packet['seq'], packet['ack'])
        self.physical_layer.send(packet)
        # debug_log("DL send:\n" + " ".join(hex(ord(n)) for n in packet))

    def start_timer_for(self, seqnum):
        t = Timer(0.2, self.resend_on_timeout, [seqnum])
        t.start()
"""
-------
-------
-------
-------
"""

class DataLinkLayer_SR(DataLinkLayer):
    def __init__(self, physical_layer):
        super(DataLinkLayer_SR, self).__init__(physical_layer)

        # Create a receive window
        self.recv_window = []

        # Create a receive window base
        self.recv_window_base = 0

    def send_blank_ack(self, recv_seq_num):
        # Create a packet containing the ack number
        new_packet = {'seq': self.next_seq, 'ack': recv_seq_num, 'data': ''}

        #Send the ack packet
        self.send_packet(new_packet)

    def update_recv_window(self, recv_packet):
        """
        Update the receive window
        """
        # If the new packet has the sequence number of the receive window base
        if recv_packet['seq'] == self.recv_window_base:

            # Send up the packet and increase the base
            self.received_data_buffer += recv_packet['data']
            self.recv_window_base += 1
            trackseq = self.recv_window_base

            # For each consecutive packet with a sequence number matching the base
            # Send it up and increase the base once more
            while len(self.recv_window) > 0 and self.recv_window[0]['seq'] == trackseq:
                self.received_data_buffer += self.recv_window[0]['data']
                self.recv_window.pop(0)
                self.recv_window_base += 1
                trackseq += 1
            self.send_blank_ack(recv_packet['seq'])

        # Otherwise insert the recv packet into the correct place in the list
        elif not recv_packet['seq'] >= self.recv_window_base + self.window_len:

            # If receive window is empty append the packet
            if len(self.recv_window) == 0:
                self.recv_window.append(recv_packet)
            else:
                insertindex = 0
                found = False

                # Find the largest prequel to the packet sequence number
                for packet in self.recv_window:
                    if recv_packet['seq'] > packet['seq']:
                        insertindex += 1
                    elif recv_packet['seq'] == [packet['seq']]:
                        found = True
                    else:
                        return
                if not found:
                    # If the packet is not already in the list insert it
                    self.recv_window.insert(insertindex, recv_packet)
            self.send_blank_ack(recv_packet['seq'])

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

            # This may be an expected data chunk
            elif seq_num_unpacked >= self.recv_window_base:
                recv_packet = {'seq': seq_num_unpacked, 'data' : payload}
                self.update_recv_window(recv_packet)

            # Otherwise resend an ack for the already gotten chunk
            else :
                self.send_blank_ack(seq_num_unpacked)

        # Do nothing if this didn't work.
        else:
            debug_log("Checksum failed.")
            # self.send_blank_ack() I don't think we need to ack here

    def received_ack(self, ack_num):
        """
        Mark acked packet, or pop it from the window and move forward the send base if it's the first
        """
        # Do nothing if the send window is empty
        if len(self.send_window) == 0:
            return
        elif self.send_window_base <= ack_num:

            # If the ack number is the window base remove the first packet and increase the base
            if self.send_window_base == ack_num:
                self.send_window.pop(0)
                self.send_window_base += 1

                # Remove all consecutive acked packets whose sequence values match the increasing base
                while len(self.send_window) > 0 and self.send_window[0]['acked'] == True:
                    self.send_window.pop(0)
                    self.send_window_base += 1
            else:

                # Mark the packet with the matching sequence number acked
                for packet in self.send_window:
                    if packet['seq'] == ack_num:
                        packet['acked'] = True
                        return

    def resend_on_timeout(self, seqnum):
        debug_log("Timeout \n")

        # If the timer runs out on an unacked packet resend
        if self.send_window_base <= seqnum:
            for packet in self.send_window:
                if packet['seq'] == seqnum:
                    if packet['acked'] == False:
                        self.send_packet(packet)
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
        self.send_window.append(new_packet)

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
