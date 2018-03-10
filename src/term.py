#!/usr/bin/env python

import sys
import tty
import os
import fcntl
import struct

class GetMixin(object):
    fields = {}

    def _mapslice(self, key):
        s, e, step = key.start, key.stop, key.step
        if s in self.fields:
            s = self.fields[s]
        if e in self.fields:
            e = self.fields[e]
        return slice(s, e, step)
    def _mapkey(self, key):
        if isinstance(key, tuple):
            pass
        elif isinstance(key, slice):
            key = self._mapslice(key)
        elif key in self.fields:
            key = self.fields[key]
        return key

    def __getitem__(self, key):
        key = self._mapkey(key)
        return super(GetMixin, self).__getitem__(key)
    def __getattr__(self, name):
        if name in self.fields:
            return self[self.fields[name]]
        raise AttributeError, \
              "object has no attribute '%s'" % name

class SetMixin(GetMixin):
    def __setitem__(self, key, value):
        key = self._mapkey(key)
        super(SetMixin, self).__setitem__(key, value)
    def __setattr__(self, name, value):
        if name in self.fields:
            o = self.fields[name]
            self[o] = value
        else:
            self.__dict__[name] = value

class termattrs(SetMixin, list):
    fields = {"iflag" : 0, "oflag" : 1, "cflag" : 2, "lflag" : 3,
              "ispeed" :4, "ospeed" : 5, "cc" : 6}

class winsize(SetMixin, list):
    fields = {"row" : 0, "col" : 1, "xpixel" : 2, "ypixel" : 3}

def SETBIT(k, v): k |= v
def CLEARBIT(k, v): k &= ~(v)

class Terminal(object):
    def __init__(self, fd=None):
        if fd is None:
            fd = sys.stdin.fileno()
        self.fileno = fd
        self._orig_term = None
    # load() / store() ??
    def get_termattrs(self):
        t = tty.tcgetattr(self.fileno)
        return termattrs(t)
    def set_termattrs(self, ttyattrs, when=tty.TCSAFLUSH):
        tty.tcsetattr(self.fileno, when, ttyattrs)
    def getwinsize(self):
        rv = fcntl.ioctl(self.fileno, tty.TIOCGWINSZ, '12345678')
        return winsize( struct.unpack('4H', rv) )
    def setwinsize(self, row=None, col=None, winsz=None):
        if winsz:
            t = winsz #struct.pack('4H', winsz)
        elif (row is not None and col is not None):
            t = struct.pack('4H', row, col, 0, 0)
        else:
            raise ValueError("Either row & col, or winsz, is required!")
        fcntl.ioctl(self.fileno, tty.TIOCSWINSZ, t)
    # save/restore settings
    def save(self):
        self._orig_term = self.get_termattrs()
    def restore(self):
        if not self._orig_term:
            raise ValueError("must call save() first. No orig_term found")
        self.set_termattrs(self._orig_term)

    # short and nice settings
    def raw(self):
        tty.setraw(self.fileno)
    def noraw(self):
        ta = self.get_termattrs()
        ta.iflag |= (tty.BRKINT|tty.ICRNL|tty.INPCK|tty.ISTRIP|tty.IXON)
        ta.oflag |= tty.OPOST
        ta.cflag |= (tty.CSIZE | tty.PARENB)
        ta.cflag &= ~(tty.CS8)
        ta.lflag |= (tty.ECHO|tty.ICANON|tty.IEXTEN|tty.ISIG)
        self.set_termattrs(ta)
    cooked = noraw
    def echo(self):
        ttyattrs = self.get_termattrs()
        SETBIT(ttyattrs.lflag, (tty.ECHO | tty.ECHOE | tty.ECHOK | tty.ECHONL))
        SETBIT(ttyattrs.oflag, (tty.ONLCR))
        self.set_termattrs(ttyattrs)
    def noecho(self):
        ttyattrs = self.get_termattrs()
        CLEARBIT(ttyattrs.lflag, (tty.ECHO | tty.ECHOE | tty.ECHOK | tty.ECHONL))
        CLEARBIT(ttyattrs.oflag, (tty.ONLCR))
        self.set_termattrs(ttyattrs)
    def issinglemode(self):
        ttyattrs = self.get_termattrs()
        if ttyattrs.lflag & (tty.ICANON|tty.ECHO) == 0:
            if ttyattrs.cc[tty.VMIN] == 1:
                return True
        return False
    def setblocking(self, *args):
        blocking = True
        if args:
            blocking = args[0]
        flags = fcntl.fcntl(self.fileno, fcntl.F_GETFL, 0)

        if blocking:
            flags &= ~os.O_NONBLOCK
        else:
            flags |= os.O_NONBLOCK

        fcntl.fcntl(self.fileno, fcntl.F_SETFL, flags)

if __name__ == "__main__":
    term = Terminal()

    term.raw()
    while True:
        ch = os.read(sys.stdin.fileno(), 1)
        if ch == 'X':
            print 'READ!'
            break
        os.write(sys.stdout.fileno(), ch)
    term.noraw()
