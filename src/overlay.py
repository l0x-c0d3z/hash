#!/usr/bin/env python

import socket
import select
import sys
import os

import dtach

def _copy(ptyfd, sfd):
    while 1:
        r,w,x = select.select([ptyfd, sfd], [], [])

        if ptyfd in r:
            buf = ptyfd.recv(4096)
            sfd.send(buf)

        if sfd in r:
            buf = sfd.recv(4096)
            ptyfd.send(buf)

def chunnel(hash_sock):
    s1, s2 = socket.socketpair(socket.AF_UNIX)

    pid = os.fork()
    if pid == 0:
        sock = s1
        s2.close()

        ptyfd = dtach.attach(hash_sock)

        try:
            _copy(ptyfd, sock)
        #except Exception, e:
            #raise
        finally:
            ptyfd.close()
            sock.close()
            os._exit(0)

    fd = os.dup( s2.fileno() )

    s1.close()
    s2.close()

    return fd

def overlay(hash_sock, argv):
    if type(argv) == type(''):
        argv = (argv,)

    pid = os.fork()
    if pid == 0:
        import resource

        # create a chunnel to the slaved PTY
        fd = chunnel(hash_sock)
        if fd != 3:
            os.dup2(fd, 3)

        # close all the other file descriptors
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        if maxfd == resource.RLIM_INFINITY:
            maxfd = 1024
        for fd in range(4, maxfd):
            try:
                os.close(fd)
            except OSError:
                pass

        os.execlp(argv[0], *argv)
    else:
        os.waitpid(pid, 0)
    return
