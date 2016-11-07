import curses, curses.panel
from time import sleep
import sys


def make_panel(height,length, y,x, matrix):
 window = curses.newwin(height,length, y,x)
 window.erase()
 
 window.addstr(2, 2, matrix[0]);
 window.addstr(3, 2, matrix[1]);
 window.addstr(4, 2, matrix[2]);
 window.addstr(5, 2, matrix[3]);
 window.addstr(6, 2, matrix[4]);
 window.addstr(7, 2, matrix[5]);
 window.addstr(8, 2, matrix[6]);
 
 
 

 panel = curses.panel.new_panel(window)
 return window, panel
def refresh(n,stdscr):
 curses.panel.update_panels();
 stdscr.refresh();
 sleep(1 * n);

def test(stdscr):
 
#Splitting files into frames for display
 filelines = [];
 with open("stars.txt","r") as f:
  content = f.readlines();
 lines_in_frame, total_frames = 8, len(content)/8;
 matrix = [[0 for x in range(0,lines_in_frame)] for y in range(total_frames)];
 curr_line = 0;
 for x in range(len(content)/8):
  for y in range(0,8):
   matrix[x][y] = content[curr_line];
   curr_line = curr_line + 1;

#ncurses module starts

 curses.curs_set(0)
 
 stdscr.box()
 
 stdscr.addstr(2, 2, "Project 2")

 for next in range(len(content)/8):
 
  window1, panel1 = make_panel(15,50, 5,5, matrix[next])
 
  refresh(1,stdscr);

 
 refresh(1,stdscr);
 sleep(1);

 

 
if __name__ == '__main__':
 curses.wrapper(test)
