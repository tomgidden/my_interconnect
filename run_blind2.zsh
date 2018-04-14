#!/bin/zsh

mount /mnt/miniprojects 2>/dev/null

set -e
rsync --delete -a /nfs/miniprojects/interconnect/*blind* /root/interconnect

cd /root/interconnect

exec ./blind2_proxy.py
