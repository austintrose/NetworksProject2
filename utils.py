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
