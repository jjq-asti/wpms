import subprocess
import json

proc = subprocess.Popen(['./speedtest', '-f', 'jsonl'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')

while True:
    d = proc.stdout.readline()
    if d == '' and proc.poll() is not None:
        break
    if d:
        value = d.strip()
        serialize = json.loads(value)
        msg_type = serialize.pop('type')
        print(serialize)
        #if  msg_type == 'testStart':
        #    print(serialize)
        #elif msg_type == 'result':
        #    print('result: \t', serialize)
        
    #print('errs: ',  errs)

