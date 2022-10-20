from wmps.netperf import IperfClient


def test_client_init_ok():
    config = {
        'server_hostname': '127.0.0.1',
        'port': 5201
    }
    client = IperfClient(**config)
    assert list(config) == client.get_config()