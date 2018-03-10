#!/usr/bin/env python

import binascii
import cmd
import os
import readline
import shlex

import alias
import interp
import overlay
import path

try:
    from IPython import Shell
    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False


class _CommandInterpretor(cmd.Cmd):
    def __init__(self, hash):
        cmd.Cmd.__init__(self)

        self.hash = hash
        self.shell = interp.Interpretor(self.hash.master)
        self.aliastab = {}
        self.cmdtab = {}
        self.prompt = "hash% "

    def postcmd(self, stop, line):
        return True # we only run for 1 iteration

    def emptyline(self):
        return None # we don't want to repeate the last cmd

class CommandInterpretor(_CommandInterpretor):

    def do_shell(self, line):
        os.system(line)

    def do_alias(self, line):
        line = line[5:].strip()
        if not line.strip():
            for k,v in self.aliastab.iteritems():
                print "%s = %s" % (k,v)
        else:
            alias_cmd, sh_cmd = line.split('=', 1)
            self.aliastab[ alias_cmd ] = sh_cmd
            self.cmdtab[alias_cmd] = alias.Alias(self, sh_cmd)

    def do_cd(self, line):
        if line:
            d = line
        else:
            try:
                d = os.environ['HOME']
            except KeyError:
                raise ValueError("No $HOME and no directory")
        os.chdir(d)
    do_chdir = do_cd

    def do_exit(self, line):
        print "Exiting!"
        os._exit(0)

    def do_pwd(self, line):
        print os.getcwd()

    def do_cat(self, line):
        '''cat <file1> [file2 ...filen]'''
        for fn in shlex.split(line):
            buf = open(fn, 'rb').read()
            self.hash.master.write( buf )

    def do_detach(self, line):
        print "Detaching..."
        self.hash.master.detach()
        self.onecmd("exit")

    def do_overlay(self, line):
        args = shlex.split(line)

        # find the binary, check in ~/.hash/bin first
        p = path.path("$HOME/.hash/bin").expand() / args[0]
        if p.access(os.X_OK):
            args[0] = str(p)

        overlay.overlay(self.hash.master.sockname, args)

    if HAS_IPYTHON:
        def do_ipshell(self, line):
            ipshell = Shell.IPShellEmbed()
            ipshell()

    def _get_remote_file(self, fname):
        cmd = "od -tx1 %s|sed -e 's/[0123456789abcdefABCDEF]*[ ]*//'"
        self.shell.init()
        enc_buf = self.shell.run(cmd % fname)
        self.shell.fini()
        return binascii.unhexlify(''.join(enc_buf.split()))

    def get_file(self, rname, lname):
        buf = self._get_remote_file(rname)
        open(lname, 'wb').write(buf)

    def do_get(self, line):
        """get <remote file> [<local file>]"""
        args = shlex.split(line)
        if len(args) == 1:
            rname = args[0]
            lname = path.path(rname).basename()
        elif len(args) == 2:
            rname = args[0]
            lname = args[1]
        else:
            return self.help_get()

        self.get_file(rname, lname)

    def _put_remote_file(self, inbuf, fname):
        buf = binascii.hexlify(inbuf)
        enc_data = []
        tot, rem = divmod(len(buf), 32)

        for off in [i *32 for i in range(0, tot)]:
            encoded = ''
            for x in range(0, 32, 2):
                encoded += '\\x' + buf[off+x:off+x+2]
            enc_data.append(encoded)

        encoded = ''
        for x in range(0, rem, 2):
            encoded += '\\x' + buf[tot*32+x:tot*32+x+2]
        enc_data.append(encoded)

        self.shell.init()
        self.shell.run('> %s' % fname)
        for enc in enc_data:
            self.shell.run('echo -n -e "%s" >> %s' % (enc, fname))
        self.shell.fini()

    def put_file(self, lname, rname):
        buf = open(lname).read()
        self._put_remote_file(buf, rname)

    def do_put(self, line):
        """put <local file> [<remote file>]"""
        args = shlex.split(line)
        if len(args) == 1:
            lname = args[0]
            rname = path.path(lname).basename()
        elif len(args) == 2:
            lname = args[0]
            rname = args[1]
        else:
            return self.help_put()

        self.put_file(lname, rname)

    def default(self, line):
        if line == 'EOF':
            return

        args = shlex.split(line)
        if args[0] in self.cmdtab:
            self.cmdtab[args[0]].process( args[1:] )
        else:
            self.onecmd("overlay " + line)
