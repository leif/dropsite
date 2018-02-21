#!/bin/bash -x

/usr/bin/python3.5 /usr/local/bin/dropsite.py -t -S /home/user/Downloads/
echo $?
echo "exiting in ~30 seconds"
sleep 30
