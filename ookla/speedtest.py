import subprocess
import sys
from pathlib import Path

speedtest = Path('wmp/wpms') / 'ookla' / 'speedtest'
print("SPEDTEST PATH: ",speedtest)
sys.exit(0)

def run(server=None):
    """create speedtest and return process"""
    proc = subprocess.Popen([speedtest, '-f', 'jsonl'], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        encoding='utf-8',
        errors='replace')

    return proc
