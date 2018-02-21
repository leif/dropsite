#!/bin/bash
set -x
set -e

cp -v dropsite.py /usr/local/bin/dropsite-oz
chmod +x /usr/local/bin/dropsite-oz
cp -v dropsite-roflcopter.json /etc/roflcoptor/filters/dropsite.json
cp -v dropsite-oz.json /var/lib/oz/cells.d/dropsite.json
cp -v dropsite-oz-whitelist.seccomp /var/lib/oz/cells.d/dropsite-whitelist.seccomp
systemctl restart roflcoptor
systemctl reload oz-daemon
oz-setup install dropsite
