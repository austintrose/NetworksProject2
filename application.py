import struct
import threading

from utils import *

# Constant strings for names of command types the client can issue.
LIST_QUERY = "LIST_QUERY"

# Constant strings for names of response types the server can issue.
LIST_ANSWER = "LIST_ANSWER"

class ApplicationLayer(object):
    def __init__(self, datalink_layer):
        """
        Shared initialization for client and server.
        """

        self.datalink_layer = datalink_layer

        # Mapping from command name to one-byte code.
        self.command_codes = {
            LIST_QUERY: 'A',
            LIST_ANSWER: 'B'
        }

    def send(self, data):
        """
        Send data to remote application.
        """

        self.datalink_layer.send(data)
        # debug_log("AL send:\n" + " ".join(hex(ord(n)) for n in data))

    def recv(self, n):
        """
        Receive n bytes from remote application.
        """

        got = self.datalink_layer.recv(n)
        # debug_log("AL got:\n" + " ".join(hex(ord(n)) for n in got))
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
    def __init__(self, datalink_layer):
        super(ClientApplicationLayer, self).__init__(datalink_layer)

        # Handler functions for different command codes.
        self.command_handlers = {
            'B': self.handle_LIST_ANSWER
        }

        # Start the receiving thread.
        self.start_receive_thread()

        # Main loop as client.
        while True:
            user_command = sys.stdin.readline()

            if user_command == "LIST\n":
                self.send_command(LIST_QUERY)

            else:
                print "Available commands:\nLIST"

    def handle_LIST_ANSWER(self, payload):
        """
        Handler for a LIST_ANSWER message the client receives.
        """

        print payload


class ServerApplicationLayer(ApplicationLayer):
    def __init__(self, datalink_layer):
        super(ServerApplicationLayer, self).__init__(datalink_layer)

        # Handler functions for different command codes.
        self.command_handlers = {
            'A': self.handle_LIST_QUERY
        }

        # Main loop as server.
        self.receive_thread_func()

    def handle_LIST_QUERY(self, payload):
        """
        Handler for a LIST_QUERY message the server receives.
        """
        self.send_command(LIST_ANSWER, 'wowowowow')


