import subprocess
from pathlib import Path

def run(target):
    """create speedtest and return process"""
    proc = subprocess.Popen(['ping', target], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        encoding='utf-8',
        errors='replace')

    return proc