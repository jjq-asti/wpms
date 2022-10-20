#!/usr/bin/sh

sudo killall -9 nping
sudo python3 ~/wpms/rfc6349.py --reverse 200000000 202.90.158.6 202.90.158.6 && \
sudo killall -9 nping
sudo python3 ~/wpms/rfc6349.py --forward 100000000 202.90.158.6 202.90.158.6
sudo killall -9 nping
