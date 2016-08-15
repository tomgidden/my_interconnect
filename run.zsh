#!/bin/zsh

mount /mnt/miniprojects 2>/dev/null

set -e
rsync --delete -a /mnt/miniprojects/shuttlexpress/ /root/shuttlexpress

cd /root/shuttlexpress

screen -S blindbt -d -m ./bt_conn.sh
screen -S shuttle -d -m ./shuttleit.py

