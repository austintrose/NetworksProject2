import curses
from time import sleep


def playfile(filename):

    # Figure out frame size
    with open(filename) as fi:
        xlen = 0
        ylen = 0
        for line in fi:
            if not line.strip == "end":
                ylen += 1
            else:
                xlen = len(line.strip())
                break


    # Initialize ncurses screen
    myscreen = curses.initscr()

    # Create border
    myscreen.border(0)

    # Get size of the window
    y,x = myscreen.getmaxyx()


    # Read file line by line
    with open(filename) as fp:
        yini = (y/2)
        ydown = yini
        xini = (x/2)
        for line in fp:

            # Stop signifies end of the movie
            if line.strip() == "stop":
                return

            # Until the end of a frame, add line by line to the window
            if not line.strip() == "end":
                # Add a text string to the myscreen object
                myscreen.addstr(ydown, xini, line)
                ydown += 1

            # Once a frame is received display
            elif not line.strip() == "stop":
                ydown = yini
                # Display window once complete
                myscreen.refresh()
                sleep(.5)

    # Wait for an input character
    myscreen.getch()

    # End window
    curses.endwin()

    print "xlen " + str(xlen)
    print "ylen " + str(ylen)


playfile('starwars.mov')


