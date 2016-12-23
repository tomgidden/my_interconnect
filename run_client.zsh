#!/bin/zsh

mount /mnt/miniprojects 2>/dev/null

set -e
rsync --delete -a /nfs/miniprojects/shuttlexpress/ /root/shuttlexpress

cd /root/shuttlexpress

screen -S shuttleclient -d -m ./shuttle_client.py

