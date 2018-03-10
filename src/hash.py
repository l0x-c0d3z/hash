#!/usr/bin/env python

import sys
import os
import select
import readline
import signal
import errno
import termios
import fcntl
import optparse

from curses import ascii

import dtach
import term
import linebuf
import hashcmd


def clear_screen():
    os.write(1, '\33[H\33[J')

class Hash(object):
    HASH_KEY=ascii.ctrl('\\')
    prompt="hash% "

    def __init__(self):
        self.line = linebuf.LineBuf()
        self.term = term.Terminal(0)

        signal.signal(signal.SIGWINCH, self.setwinsize)

    def setwinsize(self, signum=None, stack=None):
        if not self.master:
            return
        ws = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, "")
        self.master.setwinsize( ws )

    def load_commands(self):
        import command
        import commands
        import filetransfer

        self.cmdtab = {}
        for cmd in command.list_commands():
            self.cmdtab[ cmd.name ] = cmd(self)

    def attach(self, hashname):
        self.master = dtach.attach(hashname)
        self.setwinsize()
        self.master.redraw(ctrl_l=True)
        self.cmd = hashcmd.CommandInterpretor( self )

    def spawn(self, hashname, command, args=[], env=None):
        dtach.dtach(hashname, command, args, env)
        while 1:
            import time
            if os.access(hashname, os.R_OK):
                break

            time.sleep(0.01)
        self.attach(hashname)

    def interact(self):
        self.term.raw()
        try:
            self.loop()
        except (IOError, OSError):
            self.term.cooked()
        try:
            self.master.close()
        except (OSError):
            pass

    def stdin_read(self, fd):
        c = os.read(fd, 1)
        if c != self.HASH_KEY:
            return c

        self.line.blank()
        self.term.cooked()

        try:
            self.cmd.cmdloop()
        except KeyboardInterrupt:
            pass

        self.term.raw()
        self.line.display()
        return ''

    def loop(self):
        while 1:
            try:
                r,w,x = select.select([self.master, 0], [], [])
            except select.error, err:
                if err[0] == errno.EINTR:
                    continue
                raise

            if self.master in r:
                data = self.master.read(4096)
                self.line.process(data)
                os.write(1, data)
            if 0 in r:
                data = self.stdin_read(0)
                while data != '':
                    n = self.master.write(data)
                    data = data[n:]

def parse_opts(argv):
    parser = optparse.OptionParser()
    parser.add_option("-a", "--attach", dest="attach",
            help="attach to SOCKNAME")
    parser.add_option('-v', '--verbose', dest="verbose",
            action="store_true", default=False)
    opt, args = parser.parse_args(argv)

    if opt.attach:
        opt.hashname = opt.attach
    else:
        opt.hashname = "/tmp/hash.%d" % os.getpid()

    if opt.verbose:
        print "Using:", opt.hashname

    if args:
        command = args

def main(argv):
    readline.parse_and_bind('tab: complete')
    hsh = Hash()

    if argv[1:]:
        hashname = argv[1]
        hsh.attach(hashname)
    else:
        hashname =  "/tmp/hash.%d" % os.getpid()
        hsh.spawn(hashname, "/bin/bash -i", env=os.environ)

    hsh.interact()

if __name__ == "__main__":
    t = term.Terminal(0)
    t.save()
    try:
        main(sys.argv)
    finally:
        t.restore()
