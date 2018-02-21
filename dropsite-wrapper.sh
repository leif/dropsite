#!/bin/bash -x

/usr/bin/python /usr/local/bin/dropsite.py -t -S /home/user/Downloads/
echo $?
echo "exiting in ~30 seconds"
sleep 30
