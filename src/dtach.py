#!/usr/bin/env python

import os
import sys
import socket
import signal
import pty
import struct
import atexit
import asyncore
import shlex
import daemon
import tty
import fcntl

try:
    from struct import Struct as _Struct
except ImportError:
    class _Struct(object):
        def __init__(self, fmt):
            self.format = fmt
            self.size = struct.calcsize(fmt)
        def pack(self, *args):
            return struct.pack(self.format, *args)
        def unpack(self, *args):
            return struct.unpack(self.format, *args)

MSG_PUSH = 0
MSG_ATTACH = 1
MSG_DETACH = 2
MSG_WINCH = 3
MSG_REDRAW = 4

REDRAW_UNSPEC = 0
REDRAW_NONE = 1
REDRAW_CTRL_L = 2
REDRAW_WINCH = 3

BUFSIZE = 4096

class NotAttachedError(Exception): pass

class Server(asyncore.dispatcher):
    def __init__(self, sockname, cwd, prog, args, env, max_clients=128):
        asyncore.dispatcher.__init__(self)

        self.sockname = sockname
        self.clients = []
        
        self.pty = SlavePty(self, cwd, prog, args, env)

        self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.bind(self.sockname)
        self.listen(max_clients)
        os.chmod(self.sockname, 0600)

        atexit.register(lambda x: os.unlink(x), self.sockname)

    def writable(self):
        return False

    def mainloop(self):
        try:
            asyncore.loop(timeout=30.0)
        except Exception, e:
            log = open("/tmp/hasherr.log", 'a')
            log.write('%r\n' % e)
        finally:
            self.close()
            os.unlink(self.sockname)

    def handle_accept(self):
        result = self.accept()
        if result:
            sock,addr = result
            client = Client(self, sock)
            self.clients.append(client)

    def handle_close(self):
        self.log_info("server handle_close()")
        self.close()

    def close(self):
        self.log_info("server close()")
        asyncore.dispatcher.close(self)
        for client in self.clients:
            client.close()
        self.log_info("%s" % asyncore.socket_map)

    def __del__(self):
        os.unlink(self.sockname)

class Client(asyncore.dispatcher):
    def __init__(self, dtach, sock):
        asyncore.dispatcher.__init__(self, sock)
        self.dtach = dtach
        self.attached = False

    def handle_close(self):
        self.close()

    def close(self):
        self.attached = False
        if self in self.dtach.clients:
            ndx = self.dtach.clients.index(self)
            del self.dtach.clients[ ndx ]
        asyncore.dispatcher.close(self)

    def writable(self):
        return False

    def handle_connect(self):
        self.attached = True

    def handle_read(self):
        try:
            buf = self.recv(10)
        except:
            self.close()
            return

        if len(buf) != 10:
            self.close()
            return

        typ,subtyp,data = struct.unpack('BB8s', buf)

        if typ == MSG_PUSH:
            self.dtach.pty.send(data[:subtyp])
        elif typ == MSG_ATTACH:
            self.attached = True
        elif typ == MSG_DETACH:
            self.attached = False
            self.del_channel()
        elif typ == MSG_WINCH:
            self.dtach.pty.setwinsize(data)
        elif typ == MSG_REDRAW:
            method = subtyp

            if subtyp == REDRAW_UNSPEC:
                method = REDRAW_CTRL_L
            elif subtyp == REDRAW_NONE:
                return

            self.dtach.pty.setwinsize(data)

            if method == REDRAW_CTRL_L:
                c = '\f'

                if self.dtach.pty.issinglemode():
                    self.dtach.pty.send(c)

            elif method == REDRAW_WINCH:
                self.dtach.pty.kill(signal.SIGWINCH)

class SlavePty(asyncore.file_dispatcher):
    def __init__(self, dtach, cwd, command, args, env):
        self.dtach = dtach

        self.pid, self.ptyfd = pty.fork()

        if self.pid == 0:
            os.chdir(cwd)
            if env:
                os.execvpe(command, args, env)
            else:
                os.execvp(command, args)
            print >> sys.stderr, "Damn, that is seriously annoying"
            os._exit(1)

        asyncore.file_dispatcher.__init__(self, self.ptyfd)

    def setwinsize(self, winsz):
        # stuct.pack('4H', winsz) ... if it is a tuple / list
        fcntl.ioctl(self.ptyfd, tty.TIOCSWINSZ, winsz)
        self.kill(signal.SIGWINCH)

    def issinglemode(self):
        attrs = tty.tcgetattr(self.ptyfd)
        if attrs[3] & (tty.ICANON | tty.ECHO) == 0:
            if attrs[6][tty.VMIN] == 1:
                return True
        return False

    def kill(self, sig):
        os.kill(self.pid, sig)

    def writable(self):
        return False

    def handle_close(self):
        self.log_info("slave pty close()")
        self.close()

    def close(self):
        self.kill(signal.SIGTERM)
        #os.waitpid(self.pid, 0)
        asyncore.file_dispatcher.close(self)
        self.dtach.close()

    def handle_read(self):
        try:
            buf = self.recv(BUFSIZE)
        except:
            os._exit(2)

        for client in [clt for clt in self.dtach.clients if clt.attached]:
            client.send(buf)

class Socket(object):
    packet = _Struct('BB8s')

    def __init__(self, sockname):
        self.sockname = sockname
        self.sock = None

        if self.sockname:
            self.attach()

    def attach(self, sockname=None):
        if not sockname:
            sockname = self.sockname
        self.sockname = sockname
        if not self.sockname:
            raise ValueError("sockname is required!")

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect( self.sockname )
        self.fd = self.sock.fileno()

        os.write(self.fileno(), self.packet.pack(MSG_ATTACH, 0, ''))

        #self.redraw(ctrl_l=True)

    def detach(self):
        if not self.sock:
            return
        try:
            os.write(self.fileno(), self.packet.pack(MSG_DETACH, 0, ''))
        except OSError:
            pass # The socket is closed on the other end already
        self.sock.close()
        self.sock = None
        self.fd = -1
    close = detach

    def fileno(self):
        if self.sock:
            return self.sock.fileno()
        return -1

    def read(self, cnt=None):
        if not self.sock:
            raise NotAttachedError("Not attached to dtach.Daemon!")

        if not cnt or cnt < 0:
            cnt = BUFSIZE
        return os.read(self.fileno(), cnt)
    recv = read

    def getch(self):
        return self.read(1)

    def write(self, buf):
        if not self.sock:
            raise NotAttachedError("Not attached to master!")
        nr = 0
        while len(buf):
            if len(buf) > 8:
                b = buf[:8]
                l = 8
            else:
                b = buf[:]
                l = len(b)
            os.write(self.fileno(), self.packet.pack(MSG_PUSH, l, b))
            nr += len(b)
            buf = buf[l:]
        return nr
    send = write

    def setwinsize(self, ws):
        if not self.sock:
            raise NotAttachedError("Not attached to master!")
        os.write(self.fileno(), self.packet.pack(MSG_REDRAW, REDRAW_WINCH, ws))

    def redraw(self, x=None, y=None, ctrl_l=None):
        if not self.sock:
            raise NotAttachedError("Not attached to master!")

        if ctrl_l:
            if x is not None or y is not None:
                raise ValueError("Only one of (x,y) or ctrl_l supported!")
            subtype = REDRAW_CTRL_L
            ws = '\x00' * 8
        else:
            if x is None or y is None:
                raise ValueError("Both (x,y) required!")
            subtype = REDRAW_WINCH
            ws = struct.pack('HHHH', x, y, 0, 0)
        os.write(self.fileno(), self.packet.pack(MSG_REDRAW, subtype, ws))

    def __getattr__(self, name):
        if hasattr(self, 'sock'):
            return getattr(self.sock, name)
        raise AttributeError("no such attribute: %s" % name)


def dtach(sockname, command, args=[], env=None, max_clients=128):
    if os.access(sockname, os.F_OK):
        raise ValueError("sockname '%s' already exists" % sockname)

    if type(args) not in (type([]), type((0,))):
        raise ValueError("args is not a list type!")

    if args == []:
        argv = shlex.split(command)
        command = argv[0]
    else:
        argv = args[:]
        argv.insert(0, command)

    pid = os.fork()

    if pid == 0:
        cwd = os.getcwd()

        pid = daemon.fork()
        if not pid:
            dtachd = Server(sockname, cwd, command, argv, env, max_clients)
            dtachd.mainloop()
        os._exit(0)
    else:
        os.waitpid(pid, 0)

def attach(sockname):
    return Socket(sockname)
