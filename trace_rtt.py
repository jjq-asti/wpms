import numpy
import pandas as pd
import subprocess
import csv
from io import StringIO


p = subprocess.run("tcptrace -l -r --csv -f'rtt_min > 0' ./iperf31.dump", shell=True, stdout=subprocess.PIPE)
d_str = p.stdout.decode()
csv_file = StringIO(d_str)
csv_reader = csv.reader(csv_file)
line = 1
rows = []
for row in csv_reader:
    if line < 9 or len(row) < 140:
        line += 1
        continue
    rows.append(row)
headers = rows.pop(0)

df = pd.DataFrame(data=rows, columns=headers)
df_a2b = df['RTT_min_a2b'].apply(lambda x: float(x))
df_b2a = df['RTT_min_b2a'].apply(lambda x: float(x))
print((df_a2b))
print(df_b2a)


