import signal
import argparse

from physical import PhysicalLayer_Client, PhysicalLayer_Server
from datalink import DataLinkLayer_SR, DataLinkLayer_GBN
from application import ClientApplicationLayer, ServerApplicationLayer
from utils import *


# Register sigint handler.
signal.signal(signal.SIGINT, sigint_handle)

if __name__ == "__main__":
    # Parse command line args.
    p = argparse.ArgumentParser()
    p.add_argument('--client', action='store_true')
    p.add_argument('--drop', type=int, default=DEFAULT_DROP_RATE)
    p.add_argument('--corrupt', type=int, default=DEFAULT_CORRUPTION_RATE)
    p.add_argument('--sr', action='store_true')

    args = p.parse_args()

    # Physical layer needs to know drop and corruption rates.
    if args.client:
        physical_layer = PhysicalLayer_Client(args.drop, args.corrupt)
    else:
        physical_layer = PhysicalLayer_Server(args.drop, args.corrupt)

    # Data link layer only needs to know about the physical layer.
    # Different subclasses are implemented for SR and GBN.
    if args.sr:
        data_link = DataLinkLayer_SR(physical_layer)
    else:
        data_link = DataLinkLayer_GBN(physical_layer)

    # Application layer only needs to know about data link layer.
    # Different sublasses are implemented for client, or server.
    if args.client:
        application = ClientApplicationLayer(data_link)
    else:
        application = ServerApplicationLayer(data_link)
