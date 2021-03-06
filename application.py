import struct
import threading
import time

from utils import *
from pycurse import *

# Constant strings for names of command types the client can issue.
LIST_QUERY = "LIST_QUERY"
STREAM_QUERY = "STREAM_QUERY"

# Constant strings for names of response types the server can issue.
LIST_ANSWER = "LIST_ANSWER"
STREAM_ANSWER = "STREAM_ANSWER"

ERROR = "ERROR"

class ApplicationLayer(object):
    def __init__(self, datalink_layer):
        """
        Shared initialization for client and server.
        """

        self.datalink_layer = datalink_layer

        # Mapping from command name to one-byte code.
        self.command_codes = {
            LIST_QUERY: 'A',
            LIST_ANSWER: 'B',
            STREAM_QUERY: 'C',
            STREAM_ANSWER: 'D',
            ERROR: 'E'
        }

    def send(self, data):
        """
        Send data to remote application.
        """

        self.datalink_layer.send(data)

    def recv(self, n):
        """
        Receive n bytes from remote application.
        """

        got = self.datalink_layer.recv(n)
        return got

    def send_command(self, command_name, payload=''):
        """
        Send the given command type, with the given payload.
        """
        command_code = self.command_codes[command_name]

        payload_len_unpacked = len(payload)
        payload_len_packed = struct.pack("!B", payload_len_unpacked)

        full_packet = command_code + payload_len_packed + payload
        self.send(full_packet)
        self.started = time.time()

    def handle_one_command(self):
        """
        Receive and handle one command from the datalink layer.
        """

        # First byte is command type.
        command_type = self.recv(1)

        # Next byte is length of payload.
        payload_len_packed = self.recv(1)
        payload_len_unpacked = struct.unpack("!B", payload_len_packed)[0]

        # Receive a payload if there is one.
        payload = ''
        if payload_len_unpacked > 0:
            payload = self.recv(payload_len_unpacked)

        # Pass the payload on to appropriate handler.
        handler = self.command_handlers[command_type]
        handler(payload)

    def receive_thread_func(self):
        """
        Function for a dedicated receiver thread to run.
        """

        while True:
            self.handle_one_command()

    def start_receive_thread(self):
        """
        Start and daemonize a dedicated receiver thread.
        """

        receive_thread = threading.Thread(target=self.receive_thread_func)
        receive_thread.setDaemon(True)
        receive_thread.start()


class ClientApplicationLayer(ApplicationLayer):
    requesting_filename = "default.mov"
    requesting_file = None

    def __init__(self, datalink_layer):
        super(ClientApplicationLayer, self).__init__(datalink_layer)

        # Handler functions for different command codes.
        self.command_handlers = {
            'B': self.handle_LIST_ANSWER,
            'D': self.handle_STREAM_ANSWER,
            'E': self.handle_ERROR

        }

        # Start the receiving thread.
        self.start_receive_thread()

        self.datalink_layer.is_client = True

        if DEBUG:
            self.send_command(LIST_QUERY)
            while True:
                pass

        # Main loop as client.
        while True:
            user_command = sys.stdin.readline()

            if user_command == "LIST\n":
                self.send_command(LIST_QUERY)

            elif "STREAM " in user_command:
                payload = user_command[user_command.find(" ")+1:user_command.find("\n")]
                self.requesting_filename = payload
                self.send_command(STREAM_QUERY, payload)

            else:
                print "Available commands:\n  LIST\n  STREAM <videoname>"

    def handle_LIST_ANSWER(self, payload):
        """
        Handler for a LIST_ANSWER message the client receives.
        """
        if DEBUG:
            if self.datalink_layer.statistics['time_to_recognize'] == 0.0:
                self.datalink_layer.statistics['time_to_recognize'] = time.time() - self.started
            else:
                log_func(self.datalink_layer)
                print "Done"
        else:
            print payload

    def handle_STREAM_ANSWER(self, payload):
        if self.requesting_file is None:
            print "Saving as asciivids_%s..." % self.requesting_filename
            self.requesting_file = open("asciivids_" + self.requesting_filename, 'w')

        if payload == "":
            self.requesting_file.close()
            self.requesting_file = None
            print "Done receiving asciivids_%s. Press any key to play." % \
                  self.requesting_filename
            playfile("asciivids_" + self.requesting_filename)

        else:
            self.requesting_file.write(payload)

    def handle_ERROR(self, payload):
        if self.requesting_file:
            self.requesting_file.close()
            self.requesting_file = None
        print "ERROR from server: ", payload


class ServerApplicationLayer(ApplicationLayer):
    def __init__(self, datalink_layer):
        super(ServerApplicationLayer, self).__init__(datalink_layer)

        # Handler functions for different command codes.
        self.command_handlers = {
            'A': self.handle_LIST_QUERY,
            'C': self.handle_STREAM_QUERY
        }

        self.datalink_layer.is_client = False

        # Main loop as server.
        self.receive_thread_func()

    def handle_LIST_QUERY(self, payload):
        """
        Handler for a LIST_QUERY message the server receives.
        """
        self.send_command(LIST_ANSWER, "Available Videos:")
        self.send_command(LIST_ANSWER, "starwars.mov")

    def handle_STREAM_QUERY(self, payload):
        try:
            with open(payload, 'r') as f:
                while True:
                    got = f.read(128)
                    if got == "":
                        break
                    self.send_command(STREAM_ANSWER, got)
                self.send_command(STREAM_ANSWER)
        except IOError:
            self.send_command(ERROR, "Requested file not found.")


