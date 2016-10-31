import sys


class ApplicationLayer(object):
    def __init__(self, datalink_layer):
        self.datalink_layer = datalink_layer

        # The physical layer object knows whether this was started as a client
        # or as a server.
        self.is_client = self.datalink_layer.physical_layer.is_client

        if self.is_client:
            self.start_client()
        else:
            self.start_server()

    def start_client(self):
        """
        Begin main loop as client.
        """
        while True:
            user_command = sys.stdin.readline()
            self.send(user_command)

    def start_server(self):
        """
        Begin main loop as server.
        """
        while True:
            got = self.recv(1)
            sys.stdout.write(got)

    def send(self, data):
        """
        Send data to remote application.
        """
        self.datalink_layer.send(data)

    def recv(self, n):
        """
        Receive up to n bytes from remote application.
        """
        return self.datalink_layer.recv(n)
