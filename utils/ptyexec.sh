#!/bin/bash 

TIMEOUT_SECONDS=1
STDPTY=3

_ptyexec() {
	cmd="$*"
	file="/tmp/.hash_output.$$"

	echo "$cmd" >&$STDPTY 
	cat <&$STDPTY > $file &
	cmd_pid=$!

	sleep $TIMEOUT_SECONDS | (read nothing
	kill $cmd_pid 2>/dev/null)&
	wait_pid=$!

	wait $cmd_pid
	kill $wait_pid 2>/dev/null

	cat $file
	rm $file
}

ptyexec() {
	_ptyexec $* 2>/dev/null
}

CR=`printf "\r"`
ptyrun() {
	cmd=$*
	ptyexec $cmd | sed -e "s/$CR//" | grep -v "^$cmd$"
}

if [[ "x$*" -ne "x" ]]; then # called with arguments, lets act like a script
	ptyexec $*
fi
