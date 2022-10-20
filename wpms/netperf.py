from attr import attrib
from iperf3 import Client

allowed_keys = [
    'duration',
    'bind_address',
    'server_hostname',
    'port',
    'blksize',
    'num_streams',
    'zerocopy',
    'verbose',
    'reverse',
    'json_output',
    'serveroutput'
]


class IperfClient(Client):
    """Iperf3 object that accepts
    params: bandwidth- bits/sec
    blksize- bulksize
    duration- duration in seconds
    num_stream- number of streams to use
    protocol- socket protocol tcp/udp
    reverse- server sends, client receives
    server_hostname- server hostname/IP
    zercopy- toggle zerocopy
     """

    def __init__(self, **kwargs):
        super().__init__()
        self.valid_keys = []
        for k in kwargs:
            if k in allowed_keys:
                self.valid_keys.append(k)
                self.__setattr__(k, kwargs[k])
            else:
                print("key not valid: ", k)

    def do_test(self):
        return self.run()

    def get_config(self):
        return self.valid_keys
