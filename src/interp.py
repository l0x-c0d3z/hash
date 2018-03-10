#!/usr/bin/env python

import os
import time
import fdpexpect

TIMEOUT=fdpexpect.TIMEOUT

class Interpretor(fdpexpect.fdspawn):
    SH_SET_PROMPT='export PS1="[XSH]\$"'
    PROMPT='\[XSH\][$#]'
    EOC='\r\n'
    def __init__(self, sock, cmd="/bin/bash", maxread=4096, searchwinsize=None):
        super(Interpretor, self).__init__(sock, maxread=maxread, \
                                            searchwindowsize=searchwinsize)
        self.sock = sock
        self.cmd = cmd
    def set_prompt(self):
        self.sendline(self.SH_SET_PROMPT)
        i = self.expect([TIMEOUT, self.PROMPT], timeout=10)
        if i == 1:
            return True
        return False
    def init(self, orig_prompts=r"][#$]|~[#$]|bash.*?[#$]|[#$] ", timeout=10):
        self.sendline( self.cmd )
        self.expect([TIMEOUT, orig_prompts], timeout=timeout)
        self.sendline('unset HISTFILE')
        self.expect([TIMEOUT, orig_prompts], timeout=timeout)

        if not self.set_prompt():
            return False
        return True

    def prompt(self, timeout=20):
        i = self.expect([TIMEOUT, self.PROMPT], timeout=timeout)
        if i == 1:
            return True
        return False

    def fini(self):
        self.sendline('exit')

    def send(self, s):
        time.sleep(self.delaybeforesend)
        if self.logfile is not None:
            self.logfile.write(s)
            self.logfile.flush()
        return self.sock.write(s)

    def sendline(self, s):
        n = self.send(s)
        n += self.send(os.linesep)
        return n

    def run(self, command, timeout=60):
        self.sendline(command)
        self.prompt(timeout)
        result = self.before
        return result.lstrip(command).lstrip('\r').lstrip('\n')

    def system(self, command):
        self.init()
        result = self.run(command)
        self.fini()
        return result

class Shell(Interpretor):
    SH_SET_PROMPT='export PS1="[XSH]\$"'
    PROMPT='\[XSH\][$#]'
    EOC='\r\n'
    def __init__(self, sock, maxread=4096, searchwinsize=None):
        super(Shell, self).__init__(sock, maxread, searchwinsize, cmd="bash")
    # move the shell specific stuff out of the Interpretor class into this one
    # then create other ones, such as Perl, Python, Ruby
