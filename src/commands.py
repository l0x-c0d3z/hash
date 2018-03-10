#!/usr/bin/env python

import command
import os
import sys

try:
    from IPython import Shell
    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

class ChdirCommand(command.Command):
    name = 'cd'
    help = 'change directory'
    def execute(self, *args):
        if args:
            d = args[0]
        else:
            if 'HOME' in os.environ:
                d = os.environ['HOME']
        try:
            os.chdir(d)
        except Exception, e:
            print 'Error', e

class ExitCommand(command.Command):
    name = 'exit'
    help = 'exit the program'
    def execute(self, *args):
        print 'Exiting!'
        os._exit(0)

class PwdCommand(command.Command):
    name = 'pwd'
    help = 'print current working directory'
    def execute(self, *args):
        print os.getcwd()

class CatCommand(command.Command):
    name = 'cat'
    help = 'dump files to shell'
    def execute(self, *args):
        for fn in args:
            buf = open(fn, 'rb').read()
            self.sock.write(buf)

class AliasCommand(command.Command):
    name = 'alias'
    help = 'create shell command aliases'
    def execute(self, *args):
        # shit, too complex here.. maybe move into process?
        return

        if self.argv[0] != 'alias':
            self.sock.write(self.alias_tab[argv[0]] + '\n')
        else:
            self.alias_tab[argv[1]] = ' '.join(argv[1:])
            self.hash.cmdtab[argv[1]] = self

class HelpCommand(command.Command):
    name = 'help'
    help = 'take a guess, genius'
    def execute(self, *args):
        for cmd in self.hash.cmdtab.values():
            print '    %s\t%s' % (cmd.name, cmd.help)

class CkVarsCommand(command.Command):
    name = 'ckvars'
    help = 'check for suspicious environ variables'
    def execute(self, *args):
        self.shell.init()
        path = self.shell.run("echo $PATH").strip()
        print 'Non standard: %r' % [t for t in path.split(':') if t not in
                ('/bin', '/sbin', '/usr/bin', '/usr/sbin', '/usr/local/bin',
                    '/usr/local/sbin', '/usr/X11R6/bin')]

        preload = self.shell.run("echo $LD_PRELOAD").strip()
        if preload:
            print 'PRELOAD:',
        lib_path = self.shell.run("echo $LD_LIBRARY_PATH").strip()
        if lib_path:
            print 'LD_LIBRARY_PATH:', lib_path
        self.shell.fini()

class DetachCommand(command.Command):
    name = 'detach'
    help = 'unimplemented!'
    def execute(self, *args):
        self.hash.master.detach()
        self.hash.process("exit")

if HAS_IPYTHON:
    class IPShellCommand(command.Command):
        name = 'ipshell'
        help = 'Embedded IPython Shell'

        def execute(self, *args):
            ipshell = Shell.IPShellEmbed()
            ipshell()
