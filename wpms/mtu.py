from time import time
from ofunctions.network import probe_mtu


def timeit(fn):
    def start(x):
        t1 = time()
        mtu = fn(x)
        print(time() - t1)
        return mtu
    return start


@timeit
def get_mtu(x):
    mtu = probe_mtu(x)
    print(mtu)


if __name__ == "__main__":
    get_mtu("202.90.158.6")
