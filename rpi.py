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


def get_min_rtt(res):
    rtts = re.findall("rtt: \d+.\d+ms", res)
    min_rtt = rtts[1]
    min_rtt = re.search("\d+.\d+",min_rtt) # get actual value
    if not min_rtt:
        return False
    min_rtt = float(min_rtt.group())
    return min_rtt

async def send():
    global last
    last = timer()
    await sio.emit('ping_from_client')


#async def background_task(msg):
#    task = msg.get('task')
#    print("running ookla speedtest")
#    if task == 1: # ookla speedtest
#        proc = speedtest.run()
#        while task:
#            out = proc.stdout.readline()
#            if out == '' and proc.poll() is not None:
#                break
#            if out:
#                serialize = json.loads(out)
#                await sio.sleep(0.1)
#                await sio.emit('ookla', serialize)
#
#    elif task == 2: # Ping test
#        addr = msg.get('data')
#        proc = ping.run(addr)
#        print(proc)
#        while task:
#            out = proc.stdout.readline()
#            match = re.search("time=\d+.\d+", out)
#            if match is not None:
#                match = match.group(0)
#                rtt = match.split("=")[1]
#                await sio.sleep(0.1)
#                await sio.emit('ping_event', {'data': rtt})
#    elif task == 3: # iperf3
#        config = msg.get('data')
#        server = config.get('server')
#        reverse = config.get(int('reverse'))
#        iperf3 = IperfClient(
#            server_hostname=server,
#            reverse=reverse,
#            json_output=True,
#            serveroutput=True)
#        proc = iperf3.run(server)
#
#    elif task == 4:  # rfc
#        # 1) Find Path MTU Using nping with different payload size
#        # set interface mtu size to maximum then then test until rtt is measured.
#        # RPI max MTU=1500, Max payload = 1500 - 20(TCP) - 20(IP) = 1460(Default)
#        payload_size = 1460
#        while True:
#            p = subprocess.run(f"sudo nping --tcp --data-length {payload_size} --df  --echo-client  \
#            test 192.168.1.214", shell=True, stdout=subprocess.PIPE)
#            min_rtt = get_min_rtt(p.stdout.decode())
#            if not min_rtt:
#                payload_size -= 10
#                continue
#            break
#        pmtu = payload_size
#        print(pmtu)
#
#        # 2) Find RTT
#        # Using nping with data-length set to largest MTU from 1
#        p = subprocess.run("sudo nping --tcp --data-length 1460 --df  --echo-client  \
#        test 192.168.1.214", shell=True, stdout=subprocess.PIPE)
#        min_rtt = get_min_rtt(p.stdout.decode())
#        print(min_rtt)





@sio.event
async def run_task(msg):
    print(msg)
    # we run one task at a time
    await background_task(msg)


@sio.event
async def connect():
    print('connection established')
    await sio.sleep(1)
    await sio.emit('join_dashboard')
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
