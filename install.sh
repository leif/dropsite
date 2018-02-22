#!/bin/bash
set -x
set -e

# Desktop file
cp -v dropsite.desktop /usr/share/applications/dropsite.desktop
# Specific theme
cp -v dropsite.svg /usr/share/icons/Adwaita/scalable/apps/dropsite.svg
cp -v dropsite.png /usr/share/icons/Adwaita/48x48/apps/dropsite.png
# Default image for all themes
cp -v dropsite.png /usr/share/icons/dropsite.png

cp -v dropsite.py /usr/local/bin/dropsite.py
cp -v dropsite-wrapper.sh /usr/local/bin/dropsite
chmod +x /usr/local/bin/dropsite
cp -v /usr/bin/xterm /usr/local/bin/dropsite-oz
cp -v dropsite-roflcopter.json /etc/roflcoptor/filters/dropsite.json
cp -v dropsite-oz.json /var/lib/oz/cells.d/dropsite.json
cp -v dropsite-oz-whitelist.seccomp /var/lib/oz/cells.d/dropsite-whitelist.seccomp
systemctl restart roflcoptor
systemctl reload oz-daemon
#oz-setup remove dropsite
#oz-setup install dropsite
echo "run dropsite like so:"
echo "alias dropsite='dropsite-oz -e /usr/local/bin/dropsite'"
echo "dropsite"
