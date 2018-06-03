#!/bin/zsh

mount /mnt/miniprojects 2>/dev/null

set -e
rsync --delete -a /nfs/miniprojects/interconnect/ /root/interconnect

cd /root/interconnect

exec python3 ./keypad_client.py
