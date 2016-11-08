import sys

# Verbose mode.
DEBUG = False

# Port the application server listens on.
SERVER_PORT = 8765
SERVER_ADDRESS = ('localhost', SERVER_PORT)

# Probability, from 0 to 100, for dropping each data link frame. Default is 0.
DEFAULT_DROP_RATE = 0

# Probability, from 0 to 100, for altering one random byte in each data link
# frame. Default is 0.
DEFAULT_CORRUPTION_RATE = 0

def debug_log(s):
    """
    Print message to standard out only if we're in verbose mode.
    """
    if DEBUG:
        print s


def sigint_handle(sig, frame):
    """
    Handler for exiting gracefully on SIGINT.
    """

    print
    print "Bye bye."
    exit(0)

def log_func(inst):
    with open('logfile', 'a') as f:
        line = "%s\t%0.2f\t%0.2f\t%s\t%d\t%d\t%d\t%d\t%d\t%0.2f\n" % \
        (
            "SR" if inst.is_sr else "GBN",
            inst.physical_layer.drop_rate,
            inst.physical_layer.corrupt_rate,
            "Client" if inst.is_client else "Server",
            inst.statistics['acks_received'],
            inst.statistics['acks_sent'],
            inst.statistics['frames_transmitted'],
            inst.statistics['duplicates_received'],
            inst.statistics['retransmissions'],
            inst.statistics['time_to_recognize']
        )
        f.write(line)

