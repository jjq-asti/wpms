import json
import re
import subprocess
from multiprocessing import Process
from datetime import datetime
from time import time as timer
import asyncio
import socketio

#from wpms.netperf import IperfClient
from wpms import ping
from wpms.ookla import speedtest


sio = socketio.AsyncClient()

last = 0
send_ping_to_server = True

async def send():
    global last
    last = timer()
    await sio.emit('ping_from_client')


@sio.event
async def connect():
    print('connection established')
    await sio.sleep(1)
    await sio.emit('join_dashboard', 'RPI')
    await send()


@sio.event
async def disconnect():
    print('disconnected from server')


@sio.event
async def server_event(data):
    print(data)


@sio.event
async def stop_ping_server():
    global send_ping_to_server
    send_ping_to_server = False


@sio.event
async def pong_from_server():
    global last
    global send_ping_to_server
    latency = timer() - last
    last = latency
    await sio.emit('client_latency', {'data': latency})
    #await sio.sleep(0.1)
    if send_ping_to_server:
        await send()


async def main():
    await sio.connect('http://localhost:5000')
    await sio.wait()


if __name__ == '__main__':
    asyncio.run(main())
