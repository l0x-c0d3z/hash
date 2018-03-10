#!/usr/bin/env python

import os
import string

class LineBuf(object):
    def __init__(self):
        self.buf = ''
    def output(self, buf):
        os.write(0, buf)
    def display(self):
        self.output(self.buf)
    def blank(self):
        l = 0
        in_ansi = False
        for c in self.buf:
            if c == '\x1b': # start ANSI
                in_ansi = True
                continue
            if in_ansi:
                if c == 'm':
                    in_ansi = False
                continue
            if c in string.printable:
                l += 1

        self.output('\b' * l)
        self.output(' ' * l)
        self.output('\b' * l)

    def process(self, buf):
        #self.output(buf)

        self.buf += buf
        ndx = self.buf.rfind('\n')

        if ndx != -1:
            self.buf = self.buf[ndx+1:]
