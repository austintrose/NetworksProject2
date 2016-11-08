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

        self.send_window_base = 0

        # Next packet to send.
        self.next_seq = 0

        self.statistics = {
            'frames_transmitted': 0,
            'retransmissions': 0,
            'acks_sent': 0,
            'acks_received': 0,
            'duplicates_received': 0,
            'time_to_recognize': 0.0
        }

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

        # Number of unacked packets which can remain in the window at once.
        self.window_len = 5

        self.is_sr = False

    def send_blank_ack(self):
        # Create a packet containing the ack number
        new_packet = {'seq': self.next_seq, 'data': ''}

        #Send the ack packet
        self.send_packet(new_packet)
        self.statistics['acks_sent'] += 1

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
            if payload_len_unpacked == 0:
                self.statistics['acks_received'] += 1

            self.received_ack(ack_num_unpacked)

            # This is an expected data chunk
            if seq_num_unpacked == self.ack and len(payload) > 0:
                self.received_data_buffer += payload
                self.ack = seq_num_unpacked + 1
            elif seq_num_unpacked < self.ack:
                self.statistics['duplicates_received'] += 1

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

                if DEBUG:
                    if "starwars" in self.send_window[0]['data']:
                        log_func(self)
                        print "Done"

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
                    self.statistics['retransmissions'] += 1
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
        self.statistics['frames_transmitted'] += 1
        packet = self.build_packet(pk['data'], pk['seq'])
        self.physical_layer.send(packet)

    def start_timer_for(self, seqnum):
        t = Timer(0.3, self.resend_on_timeout, [seqnum])
        t.start()

class DataLinkLayer_SR(DataLinkLayer):
    def __init__(self, physical_layer):
        super(DataLinkLayer_SR, self).__init__(physical_layer)

        # Create a receive window
        self.recv_window = []

        # Create a receive window base
        self.recv_window_base = 0

        self.start_receive_thread()

        # Number of unacked packets which can remain in the window at once.
        self.window_len = 30
        self.is_sr = True

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

    def send_blank_ack(self, recv_seq_num):
        # Create a packet containing the ack number
        new_packet = {'seq': self.next_seq, 'ack': recv_seq_num, 'data': ''}

        #Send the ack packet
        self.send_packet(new_packet)
        self.statistics['acks_sent'] += 1

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
                else:
                    self.statistics['duplicates_received'] += 1
            self.send_blank_ack(recv_packet['seq'])

    def recv_one_frame(self):
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
        payload = self.physical_layer.recv(payload_len_unpacked)

        # This is the data which should match the checksum.
        to_check = seq_num_packed + ack_num_packed + payload_len_packed + \
                   payload

        # Compute checksum of data received.
        observed_checksum = self.checksum(to_check, pack=False)

        # Compare checksums.
        if checksum_unpacked == observed_checksum:


            # This is just a blank ack of our data.
            if payload_len_unpacked == 0:
                self.received_ack(ack_num_unpacked)
                self.statistics['acks_received'] += 1

            # This may be an expected data chunk
            elif seq_num_unpacked >= self.recv_window_base:
                recv_packet = {'seq': seq_num_unpacked, 'data' : payload}
                self.update_recv_window(recv_packet)

            # Otherwise resend an ack for the already gotten chunk
            else :
                self.send_blank_ack(seq_num_unpacked)
                self.statistics['duplicates_received'] += 1

        # Do nothing if this didn't work.

    def received_ack(self, ack_num):
        """
        Mark acked packet, or pop it from the window and move forward the send base if it's the first
        """
        if DEBUG:
            if 'starwars' in self.send_window[0]['data']:
                log_func(self)
                print "Done"

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

        # If the timer runs out on an unacked packet resend
        if self.send_window_base <= seqnum:
            for packet in self.send_window:
                if packet['seq'] == seqnum:
                    if packet['acked'] == False:
                        self.send_packet(packet)
                        self.statistics['retransmissions'] += 1
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

        # Increment the sequence
        self.next_seq += 1

    def send_packet(self, pk):
        packet = self.build_packet(pk['data'], pk['seq'], pk['ack'])
        self.statistics['frames_transmitted'] += 1
        self.physical_layer.send(packet)

    def start_timer_for(self, seqnum):
        t = Timer(0.1, self.resend_on_timeout, [seqnum])
        t.start()
