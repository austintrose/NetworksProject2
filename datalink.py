# The struct library is used for packing exact binary data.
# https://docs.python.org/2/library/struct.html
import struct

from utils import *

class DataLinkLayer(object):
    def __init__(self, physical_layer):
        self.physical_layer = physical_layer
        self.received_data_buffer = ""
        self.is_sr = physical_layer.is_sr
        self.seqnum = 0
        self.acknum = 0
        send_window = []
        if self.is_sr:
            recv_window = []

    def recv_one_frame(self):
        # Expected checksum will be the first byte of a new frame.
        checksum = self.physical_layer.recv(1)

        #Seqnum will be next four bytes of a new frame
        seqnum_packed = self.physical_layer.recv(4)
        seqnum_unpacked = struct.unpack("!I", seqnum_packed)[0]
        print "Seqnum unpacked " + str(seqnum_unpacked)

        #Acknum will be next four bytes of a new frame
        acknum_packed = self.physical_layer.recv(4)
        acknum_unpacked = struct.unpack("!I", acknum_packed)[0]
        print "Acknum unpacked " + str(acknum_unpacked)

        # Payload len with be next 4 bytes of a new frame.
        payload_len_packed = self.physical_layer.recv(4)
        payload_len_unpacked = struct.unpack("!I", payload_len_packed)[0]

        # Receive enough for remaining data.
        if(payload_len_unpacked > 0):
            payload = self.physical_layer.recv(payload_len_unpacked)

        # Compute checksum of data received.
        observed_checksum = self.checksum(seqnum_packed + acknum_packed + payload_len_packed + payload)

        # Compare checksums.
        if checksum == observed_checksum:
            
            #Add the newly received data into the receive buffer
            self.received_data_buffer += payload
            
            #Send an acknowkedgement
            self.acknum = seqnum_unpacked
            print "Sending acknum " + str(self.acknum)
            header = self.build_header("")
            self.physical_layer.send(header)


        # Do nothing if this didn't work.
        # Obviously not what we want.
        # Need to send the nack. Or something.
        else:
            debug_log("Checksum failed.")
        #Acknum to send is the sequence number just received
        self.acknum = seqnum_unpacked
        if(payload_len_unpacked == 0):
            
            header = self.build_header(NULL)



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
        #separate the data into 128 bit chunks
        for i in range(0,len(data) -1, 128):
            
            #increment the sequence number of the data
            self.seqnum = self.seqnum + 1
            print "Sending seqnum " + str(self.seqnum)

            #Get teh data chunk
            tempdata = data[i:i+127]

            # Build the header.
            header = self.build_header(tempdata)

            # Attach the header to the data.
            full_frame = header + tempdata

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
        acknum = struct.pack("!I", self.acknum)
        aseqnum = struct.pack("!I", self.seqnum)
        checksum = self.checksum(acknum + aseqnum + payload_len + data)

        return checksum + aseqnum + acknum + payload_len
