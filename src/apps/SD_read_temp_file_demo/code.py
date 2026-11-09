# SPDX-FileCopyrightText: 2026 Paulus Schulinck (Github @PaulskPt)
# SPDX-License-Identifier: MIT

"""
CircuitPython Essentials SD Card Read temperature file Demo

The SD Card is automatically mounted by CircuitPython on the Fruit Jam.
"""

import time
import microcontroller

# Use the filesystem as normal! Our files are under /sd
filename = "/sd/temperature.txt"
print("Reading temperatures from file: ", end='')
print(filename)

# Read from the file!
# while True:
# open file for read
cnt = 0
line_cnt = 0

try:
    with open(filename, "r") as f:
        for line in f:
            value = float(line.strip())
            t = "%0.1f" % value
            print("%03d: " % line_cnt, end='')
            print("Temperature = ", end='')
            print(t)
            cnt += 1
            line_cnt += 1
            if cnt == 10:
                time.sleep(5) # wait a bit before reading the file again
                cnt = 0

    # file is read
    time.sleep(1)
except OSError:
    print("Could not open file: ", filename)
