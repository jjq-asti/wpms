#!/usr/bin/env python3
import subprocess
import re
import json
import csv
import sys
import os
import signal
import uuid
import configparser
from datetime import datetime

import requests
from tenacity import (
    retry,
    wait_fixed,
    stop_after_attempt
    )
from requests.exceptions import ConnectionError

import logging
from logger_settings import Logger

from utils import (
    TCP_HEADER_SIZE,
    TCP_WINDOW_SIZE,
    IP_HEADER_SIZE,
    FRAME_BYTE_SIZE,
    get_max_thpt
    )
logger = logging.getLogger(__name__)
logger = Logger(logger)

config = configparser.ConfigParser()
config_path = '/var/local/config.ini'
csv_path = "/var/local/starmon/"
config.read(config_path)


def get_min_rtt(res):
    rtts = re.findall("rtt: \d+.\d+ms", res)
    if not rtts:
        return False
    min_rtt = rtts[1]
    min_rtt = re.search("\d+.\d+",min_rtt)  # get actual value
    min_rtt = float(min_rtt.group())
    return min_rtt


def get_avg_rtt(res):
    rtts = re.findall("rtt: \d+.\d+ms", res)
    if not rtts:
        return False
    avg_rtt = rtts[2]
    avg_rtt = re.search("\d+.\d+",avg_rtt)  # get actual value
    avg_rtt = float(avg_rtt.group())
    return avg_rtt


"""
RFC 6349 Test Process
1) Find the PMTU
*2) Find the Baseline RTT (Inherent RTT)
*3) Measure the Bottleneck Bandwidth
4) Calculate the BDP by multiplying the results from 2 and 3
*5) Calculate the minimum TCP window, BDP/8
*6) Calculate the Ideal Transfer Time based on a known file size (i.e 100MB)
7) Conduct Iperf test using a know file size and get the actual transfer time.
8) Calculate the Transfer Time Ratio (1st TCP Metrics)
9) Calculate the TCP Efficiency

*2 -- The baseline rtt should be measured during times when the network is not
loaded or uncongested. This is the inherent RTT of the system.

*3 -- The bottleneck bandwidth is the maximum speed that a network/link can support.
Bottleneck bandwidth must be measured using a stateless protocol (UDP) to get a more
accurate BB of the system. Using Iperf in udp mode the jitter can also be measured.

*5 -- The Window Size must be set to equal or greater than the min TCP window/BDP
to achieve the optimal TCP Throughput. When the TCP window is set to equal or greater
than the min TCP window / BDP the theoretical(ideal) maximum TCP throughput can be
derived from the maximum frames per second.

*6 -- The ideal transfer time is derived by dividing a know file size by the
maximum achievable throughput . ie. 100MB/Max_TCP_THPT, remember that MAX_TCP_THPT
can be calculated when the window size is set to equal or greater than the BDP
*7 -- A TCP Throughput must be conducted using a file transfer with a file size equal to
the value used for calculating the Ideal Transfer time.

*9 --
"""


class TcpTest:
    def __init__(self, mode, cir, server_ip, nping_server):
        self.mode = mode
        self.cir = int(cir)
        self.server_ip = server_ip
        self.payload_size = 1500
        self.window_size = 536
        self.mode = "Forward"
        self.target_bitrate = "300M"
        self.server_ip = server_ip
        self.nping_server_ip = nping_server
        self.client_output = None
        self.server_output = None
        self.mtu = 1500
        self.mss = 536  # smallest mss allowed by TCP
        self.rtt = 0
        self.base_rtt = 0
        self.avg_rtt = 0
        self.bdp = 0
        self.bb = 0
        self.jitter = 0
        self.minimum_wnd_size = 0
        self.tcp_wnd_size = 0
        self.max_achievable_thpt = 0
        self.retransmit_bytes = 0
        self.transfer_bytes = 0
        self.thpt = 0
        self.ideal_transfer_time = 0
        self.actual_transfer_time = 0
        self.transfer_time_ratio = 0
        self.tcp_efficiency = 0
        self.buffer_delay = 0
        self.file_size = self.cir  # file size in bits
        self.timestamp = None
        self.iperf_version = None
        self.system_info = None
        self.sndbuf_actual = 0
        self.rcvbuf_actual = 0
        self.sndr_tcp_congestion = ""
        self.rcvr_tcp_congestion = ""
        self.host_system_util = 0
        self.remote_system_util = 0
        self.test_mode = None
        self.jitter = 0

        self.sender = True
        if mode == "--forward":
            self.mode = ""
            self.test_mode = "forward"
            self.sender = True
        else:
            self.mode = "--reverse"
            self.test_mode = "reverse"
            self.sender = False

        logger.debug("init sender %s", self.sender)

    @retry(wait=wait_fixed(10),
           stop=stop_after_attempt(20))
    def pmtu(self):
        """
        Measure MTU using trial and error.
        1) perform a TCP ping (3-way handshake)  with a payload
        2) repeat until no rtt is measured during the process
        3) the MTU is taken from the last payload with a valid rtt
        RTT here doesn't matter and is not used, it is only used
        to confirm that the server was able to capture the data.
        """
        logger.debug("Finding PMTU")
        while True:
            logger.debug("PAYLOAD %s", self.payload_size)
            p = subprocess.run(
                [
                    "nping",
                    "--tcp",
                    "--data-length",
                    str(self.payload_size),
                    "--df",
                    str(server_ip)],
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            min_rtt = get_min_rtt(p.stdout.decode())
            if p.stderr and "failed" in p.stderr.decode():
                logger.error("nping %s", p.stderr.decode())
                raise SystemError("nping connection failed")
            if not min_rtt:
                self.payload_size -= 10
                continue
            break
        self.mss = self.payload_size
        pmtu = self.mss + TCP_HEADER_SIZE + IP_HEADER_SIZE
        self.mtu = int(pmtu)
        return self.mtu


    @retry(wait=wait_fixed(10),
        stop=stop_after_attempt(20))
    def baseline_rtt(self):
        """
        RFC6349 suggests to use TCPTRACE to analyze packets captured to derived the
        rtt of the TCP connection. However, TCPTRACE is no longer maintained and IPERF3
        already has this feature to acquire the RTT from the kernel for the current stream.
        The use of ICMP ping will also be avoided since it gives the least accurate RTT value.
        Instead, we will conduct a TCP throughput test using IPERF and acquire the minimum
        rtt (IPERF automatically includes this in the json data). What's important is to conduct
        this TCP Throughput test during noncongested time, when there is no one using the network
        yet. This will give the inherent rtt of the network.
        """
        logger.debug("Measuring RTT")
        baseline_rtt = float(config['RFC6349']['baseline_rtt'])

        # p = subprocess.run(
        #     [
        #         "iperf3",
        #         "--client",
        #         self.server_ip,
        #         self.mode,
        #         "--bitrate",
        #         "10M",
        #         "--set-mss",
        #         f"{self.mss}",
        #         "--pacing-timer",
        #         "10",
        #         "--time",
        #         "10",
        #         "--interval",
        #         "0.1",
        #         "--json",
        #         "--get-server-output",
        #         "--dont-fragment"
        #         ],
        #     stdout=subprocess.PIPE)
        p = subprocess.run(
            [
                "nping",
                "--icmp",
                "--df",
                self.nping_server_ip
                ],
            stdout=subprocess.PIPE)
        output = p.stdout
        if not output:
            raise ValueError("baseline_rtt Failed subprocess returned None")
        # output = output.decode()
        # data = json.loads(output)
        # if self.sender:
        #     min_rtt = data['end']['streams'][0]['sender']['min_rtt']
        # else:
        #     min_rtt = data['server_output_json']['end']['streams'][0]['sender']['min_rtt']
        min_rtt = get_min_rtt(output.decode())
        min_rtt = float(min_rtt)/1000
        logger.debug("config baseline_rtt %s", baseline_rtt)
        logger.debug("current min rtt %s", min_rtt)
        if min_rtt < baseline_rtt or baseline_rtt == 0:
            baseline_rtt = min_rtt
            config.set("RFC6349", "baseline_rtt", str(baseline_rtt))
            with open(config_path, 'w') as configfile:
                config.write(configfile)
            logger.debug("Baseline RTT was Changed!")

        self.base_rtt = baseline_rtt
        self.rtt = min_rtt  # use the current min rtt for the current test
        return self.base_rtt

    @retry(wait=wait_fixed(10),
           stop=stop_after_attempt(20))
    def bandwidth(self):
        """
        Bottleneck Bandwidth. Based on experiments, raspberry pi 4 can achieve up to
        1000 Mbps UDP burst @ 10 packets with timing spread of 10 without losses.
        Set target bitrate to RPI's link speed (1Gbps) the maximum bandwidth the device
        is capable of transmitting / receiving. Iperf will attempt to achieve the target
        bitrate. All of the tets will be single connection. CPU Affinity is set to 1, this
        seems to solve UDP burst problem of RPI, even though rpi was set as a server during the
        test which can only achieve a 300Mbps speed, setting affinity to 1 solved this and was
        able to reach 956Mbps on a 1Gbps network. The 1st stream result will be omitted since
        based on experiments the first stream sometimes gives a very low value.
        """
        logger.debug("Measuring Bottleneck bandwidth")
        p = subprocess.run(
            [
                "iperf3",
                "--client",
                self.server_ip,
                self.mode,
                "--udp",
                "--bitrate",
                f"{self.cir}/10",
                "--pacing-timer",
                "10",
                "--affinity",
                "1",
                "--time",
                "20",
                "--omit",
                "1",
                "--json",
                "--get-server-output"],
            stdout=subprocess.PIPE)

        output = p.stdout
        if not output:
            logger.error("BB test failed, subprocess returned NoneType")
            raise ValueError("thpt_test failed, subprocess returned NoneType")
        output = output.decode()
        data = json.loads(output)
        if 'error' in data:
            logger.error('Iperf Error %s', data['error'])
            raise ValueError("Invalid Iperf Result")

        if self.sender:
            server_data = data['end']['sum_received']
            bits_per_second = server_data['bits_per_second']
            self.jitter = server_data['jitter_ms']
        else:
            receiver_data = data['end']['sum_received']
            bits_per_second = receiver_data['bits_per_second']
            self.jitter = receiver_data['jitter_ms']
        self.bb = bits_per_second
        self.set_bdp()
        return int(self.bb)

    def calculate_optimal_wnd(self):
        frame_size = self.mtu + FRAME_BYTE_SIZE
        logger.debug("FRAME SIZE %s", frame_size)
        even_multipleof_max_window = int(TCP_WINDOW_SIZE / frame_size)
        unscaled_window = self.mss * even_multipleof_max_window
        self.minimum_wnd_size = unscaled_window
        while self.minimum_wnd_size < self.tcp_wnd_size:
            self.minimum_wnd_size = self.minimum_wnd_size * 2

    def set_bdp(self):
        logger.debug("Calculating Bandwidth Delay Product")
        self.bdp = int(self.rtt * self.bb)  # bits
        self.calculate_bdp_bytes()
        self.calculate_optimal_wnd()

    def calculate_bdp_bytes(self):
        self.tcp_wnd_size = int(self.bdp / 8) # bits to bytes

    # @retry(wait=wait_fixed(10),
    #        stop=stop_after_attempt(20))
    def thpt_test(self):
        """
        TCP throughput test will be conducted without specifying the target bitrate.
        We will let the optimal window size drive that Iperf test, this should give the
        throughput of the system. Rememer that TCP Window size must be set equal or greater
        than the BDP. TCP Window will also be an even multiple of the MTU.
        """
        logger.info("Measuring TCP Throughput")
        rtt_proc = subprocess.Popen(
            [
                "nping",
                "--icmp",
                "--df",
                "-c",
                "1000",
                self.nping_server_ip
                ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        try:
            p = subprocess.run(
                [
                    "iperf3",
                    "--client",
                    server_ip,
                    self.mode,
                    "--window",
                    str(self.minimum_wnd_size),
                    "--set-mss",
                    str(self.mss),
                    "--bytes",
                    f"{self.file_size/8}",
                    "--json",
                    "--get-server-output",
                    ],
                stdout=subprocess.PIPE)
            output = p.stdout
            rtt_proc.send_signal(signal.SIGINT)
            stdout, stderr = rtt_proc.communicate()
            if not output:
                logger.error('thp_test failed, subprocess returned NoneType')
                raise ValueError('Iperf3 NoneType Value Error')
            output = output.decode()
            data = json.loads(output)
            if 'error' in data:
                logger.error('Iperf Error %s', data['error'])
                raise ValueError("Iperf encountered an error.")

            logger.debug("Is Sender %s", self.sender)
            # Test Info
            test_info = data['start']
            test_info_xtras = data['end']
            cpu_util = test_info_xtras['cpu_utilization_percent']
            self.timestamp = test_info['timestamp']['timesecs']
            d = datetime.fromtimestamp(self.timestamp)
            self.timestamp = d.strftime("%m/%d/%Y, %H:%M:%S")
            logger.info("DateTime %s", self.timestamp)
            self.iperf_version = test_info['version']
            self.system_info = test_info['system_info']
            self.sndbuf_actual = test_info['sndbuf_actual']
            self.rcvbuf_actual = test_info['rcvbuf_actual']
            self.sndr_tcp_congestion = test_info_xtras['sender_tcp_congestion']
            self.rcvr_tcp_congestion = test_info_xtras['receiver_tcp_congestion']
            self.host_system_util = cpu_util['host_system']
            self.remote_system_util = cpu_util['remote_system']
            if self.sender:
                sender_data = data['end']['streams'][0]['sender']
                self.thpt = sender_data['bits_per_second']
                self.actual_transfer_time = float(sender_data['seconds'])
                self.avg_rtt = get_avg_rtt(stdout.decode()) / 1000
                self.retransmit_bytes = int(sender_data['retransmits']) * self.mtu
                self.transfer_bytes = int(sender_data['bytes']) \
                    + self.retransmit_bytes
            else:
                receiver_data = data['end']['streams'][0]['receiver']
                sender_data = data['server_output_json']['end']['streams'][0]['sender']
                self.thpt = receiver_data['bits_per_second']
                self.actual_transfer_time = float(receiver_data['seconds'])
                self.avg_rtt = get_avg_rtt(stdout.decode()) / 1000
                self.retransmit_bytes = int(sender_data['retransmits']) * self.mtu
                self.retransmit_bytes = int(sender_data['retransmits']) * self.mtu
                self.transfer_bytes = int(sender_data['bytes']) \
                    + self.retransmit_bytes

            logger.debug("average rtt %s", self.avg_rtt)
            logger.debug("jitter %s", self.jitter)
            return self.thpt
        except:
            raise

    def create_dict(self):

        test_data = {
            "mtu": self.mtu,
            "rtt": self.rtt,
            "avg_rtt":self.avg_rtt,
            "baseline_rtt": self.base_rtt,
            "Jitter": self.jitter,
            "bb": int(self.bb),
            "bdp": self.bdp,
            "rwnd": self.minimum_wnd_size,
            "actual_thpt": int(self.thpt),
            "max_achievable_thpt": int(self.max_achievable_thpt),
            "ideal_transfer_time": self.ideal_transfer_time,
            "actual_transfer_time": self.actual_transfer_time,
            "transfer_time_ratio": self.transfer_time_ratio,
            "tcp_efficiency": self.tcp_efficiency,
            "buffer_delay": self.buffer_delay,
            "timestamp": self.timestamp,
            "iperf_version": self.iperf_version,
            "sndbuf_actual": self.sndbuf_actual,
            "rcvbuf_actual": self.rcvbuf_actual,
            "transfer_bytes": self.transfer_bytes,
            "retransmit_bytes": self.retransmit_bytes,
            "mode": self.test_mode,
            "sender_tcp_congestion": self.sndr_tcp_congestion,
            "receiver_tcp_congestion": self.rcvr_tcp_congestion,
            "host_system_util": self.host_system_util,
            "remote_system_util": self.remote_system_util,
            "test_id": str(uuid.uuid4())
        }

        return test_data


if __name__ == "__main__":
    mode = sys.argv[1]
    cir = sys.argv[2]
    server_ip = sys.argv[3]
    nping_server = sys.argv[4]
    logger.info("mode %s", mode)
    handler = TcpTest(mode, cir, server_ip, nping_server)
    pmtu = handler.pmtu()
    logger.info("PMTU %s", pmtu)
    logger.info("MSS %s", handler.mss)
    baseline_rtt = handler.baseline_rtt()
    logger.info("Baseline RTT %s", baseline_rtt)
    bb = handler.bandwidth()
    logger.info("Bottleneck BW %s", bb)
    logger.info("BDP %s bits", handler.bdp)
    logger.info("BDP Bytes %s", handler.tcp_wnd_size)
    logger.info("Optimal Window Size %s", handler.minimum_wnd_size)
    thpt = handler.thpt_test()
    logger.info("TCP Throughput %s", handler.thpt)
    logger.debug("Calculate Max Achievable THPT")
    handler.max_achievable_thpt = get_max_thpt(handler.cir, handler.mtu)
    logger.info("Maximum Achievable thpt %s", handler.max_achievable_thpt)
    handler.ideal_transfer_time = handler.file_size / handler.max_achievable_thpt
    handler.transfer_time_ratio = handler.actual_transfer_time / handler.ideal_transfer_time
    logger.debug("Ideal Transfer Time %s", handler.ideal_transfer_time)
    logger.debug("Actual Transfer Time %s", handler.actual_transfer_time)
    logger.info("Transfer Time Ratio %s", handler.transfer_time_ratio)
    handler.tcp_efficiency = ((
        handler.transfer_bytes - handler.retransmit_bytes) /
        handler.transfer_bytes) * 100
    logger.info("TCP Efficiency %s%%", handler.tcp_efficiency)
    handler.buffer_delay = ((handler.avg_rtt - handler.base_rtt) /
                            handler.base_rtt) * 100
    logger.info("Buffery delay %s%%", handler.buffer_delay)
    # print("mode: {} \t cir: {}".format(mode, cir))
    # print("uscaled_windows: ", unscaled_window)
    rfc_data = handler.create_dict()
    print(rfc_data)
    # BASE_URL = "http://ec2-108-137-45-5.ap-southeast-3.compute.amazonaws.com/api/"
    # TOKEN_URL = "user/auth-token/"
    # RFC_URL = "netmon/rfcdata/"
    # headers = {
    #     "Accept": "Application/json",
    #     "Content-Type": "application/json"
    # }
    # payload = {
    #     "email": "tester@wpms.com",
    #     "station": "rpi_malvar",
    #     "password": "netmesh!@#"
    # }
    dt = datetime.strptime(handler.timestamp,
                                  "%m/%d/%Y, %H:%M:%S")
    filename = dt.strftime("%m%d%Y_%H%M%S") + ".csv"

    file_path = csv_path + filename
    with open(file_path, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=rfc_data.keys())
        writer.writeheader()
        writer.writerow(rfc_data)

    # auth_obj = None
    # payload = json.dumps(payload)
    # rfc_data = json.dumps(rfc_data)
    # try:
    #     res = requests.post(BASE_URL + TOKEN_URL,
    #                         data=payload,
    #                         headers=headers
    #                         )
    #     auth_obj = res.json()

    # except ConnectionError as e:
    #     logger.error("Connection error %s", e)

    # token = auth_obj.get('token')
    # headers['Authorization'] = f"Token {token}"
    # logger.debug("Token %s", token)
    # res = requests.post(
    #     BASE_URL + RFC_URL,
    #     headers=headers,
    #     data=rfc_data)
    # logger.debug(" %s ", res)
    # logger.debug("RFC POST %s", res.status_code)
