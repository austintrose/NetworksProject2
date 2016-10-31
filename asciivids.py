import signal

from physical import PhysicalLayer
from datalink import DataLinkLayer
from application import ApplicationLayer
from utils import *


# Register sigint handler.
signal.signal(signal.SIGINT, sigint_handle)

if __name__ == "__main__":
    # Physical layer doesn't need anything else.
    physical_layer = PhysicalLayer()

    # Data link layer only needs to know about the physical layer.
    data_link = DataLinkLayer(physical_layer)

    # Application layer only need to know about the data link layer.
    application = ApplicationLayer(data_link)
