import os
"""
Transfer Time: The time it takes to transfer a block of data.
Transfer Time Ratio is the ratio of the actual transfer time (measured)
and ideal transfer time (derived from the calculated maximum TCP throughput.
"""

TCP_HEADER_SIZE = 20
IP_HEADER_SIZE = 20

"""
This is the maximum TCP WINDOW based on the original TCP standards.
This field has only 2 bytes and can no longer be extended. To overcome, a
scaling factor is used to increase the advertised window.
In iperf the -w or --window is used to manipulate the value of the adv_window
The Linux operating must be tuned to allow iperf to change the adv_window
"""
TCP_WINDOW_SIZE = 65535

ETHERNET_BYTE_SIZE = 14
CRC32_BYTE_SIZE = 4
IFG_BYTE_SIZE = 12
PREAMBLE_BYTE_SIZE = 7
SFD_BYTE_SIZE = 1

FRAME_BYTE_SIZE = ETHERNET_BYTE_SIZE + CRC32_BYTE_SIZE + IFG_BYTE_SIZE \
    + PREAMBLE_BYTE_SIZE + SFD_BYTE_SIZE

"""
TCP Metrics
1) Transfer Time Ratio
2) TCP Efficiecy
3) Buffer Delay
"""


def get_filesize(file_path):
    return os.path.getsize(file_path)


def get_max_thpt(link_speed, mtu):
    """
    Maximum TCP Throughput is calculated based on the Link Speed and MTU.
    If the received window is greater or equal to the BDP then the Max THPT
    is calculated based on the Frame Rate per Seconds(FPS).
    :Link Speed (bps)
    :Maximum Transmission Unit
    :returns max_thpt in bps
    """
    max_fps = link_speed / ((mtu + FRAME_BYTE_SIZE) * 8)
    max_thpt = max_fps * (mtu-40) * 8  # bps

    return max_thpt


class TcpCalc:
    def __init__(self):
        self.ttr = 0

    def get_ttr(self, att, itt):
        """
        TCP Transfer Time Ratio
        :Actual TCP Transfer Time (att)
        :Ideal TCP Transfer Time (itt)
        returns ttr (ms)
        *itt is derived from the Maximum Achievable Throughput
        """
        return att/itt

    def get_itt(self, block_size, max_thpt):
        """
        The Ideal Transfer Time is the theoretical(calculated) time it take to transfer
        a data block of block_size given the maximum achievable TCP Throughput.
        """
        return block_size / max_thpt # time in seconds

    def get_tcp_efficiency(self, tx_bytes, rtx_bytes):
        """
        :tx_bytes is the original transmitted bytes
        :rtx_bytes is the retransmitted bytes
        :returns TCP Efficiency in %
        """
        total_tx_bytes = tx_bytes + rtx_bytes
        return ((total_tx_bytes - rtx_bytes) / total_tx_bytes) * 100

    def get_avg_rtt(self, rtts, duration):
        """
        :rtts is the list of rtts taken at every second during the entire =duration=
        :duration is the duration of the test
        """
        try:
            avg_rtt = sum(rtts) /duration
        except TypeError:
            raise("rtts and duration must be float or numbers")

        return avg_rtt

    def get_buffer_delay(self, avg_rtt, baseline_rtt):
        """
        Represents the increase in rtt during throughput test vs the baseline
        It is important to note that the baseline rtt must be taken on non-congested
        network to get a more accurate baseline rtt and buffer delay calculation.
        :avg_rtt - average rtt during a tcp connection
        :baseline_rtt - baseline / inherent non-congested rtt
        :returns buffer delay in %
        """
        return ((avg_rtt -baseline_rtt)/baseline_rtt) * 100


class TcpMetrics(TcpCalc):
    pass
