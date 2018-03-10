#!/usr/bin/env python

import interp

class Command(object):
    def __init__(self, hash):
        self.hash = hash
        self.sock = hash.master
        self.shell = interp.Interpretor(hash.master)

    def execute(self, *args):
        pass
    def process(self, argv):
        self.argv = argv
        self.execute(*argv[1:])

def list_commands():
    return Command.__subclasses__()
