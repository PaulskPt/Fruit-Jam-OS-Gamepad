# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
# SPDX-License-Identifier: MIT

import adafruit_pathlib as pathlib
import storage
import supervisor
from adafruit_argv_file import read_argv, write_argv
import sys

# Send ANSI terminal escape codes to erase the console history and home the cursor
# \x1bc = Reset terminal, \x1b[2J = Clear screen, \x1b[H = Move cursor to top-left
sys.stdout.write("\x1b[2J\x1b[H")

supervisor.runtime.autoreload = False

my_debug = False

# ------------------- Temporary code by Google AI ------------------------------------
# Internal clone helper to bypass Windows Write-Protection
# Just used one time (After use, MS Windows 11 Pro PC sees drive CPSAVES (H:) with file launcher_conf.json in it!)
copy_file = False
remove_file = False

if copy_file:
    import os
    import gc
    if my_debug:
        print("boot.py: --- Internal Storage Helper: Checking /saves/ partition ---")
    # Verify if the file is missing from the true internal partition
    try:
        # Note that an eventually existing file: /saves/launcher_conf.json will be overwritten!
        # Read from the root of the F: drive
        with open("/launcher_conf_backup.json", "r") as source:
            config_data = source.read()
            
        # Write directly to the protected H: partition internal space
        with open("/saves/launcher_conf.json", "w") as dest:
            dest.write(config_data)
        if my_debug:
            print("boot.py: Cloning complete! launcher_conf.json successfully injected inside /saves/.")
    except Exception as e:
        print(f"boot.py: Internal copy failed: {e}")
    
    gc.collect()
    
if remove_file:
    import os

    try:
        if my_debug:
            print("boot.py: --- Internal Storage Helper: Removing file ---")
        os.remove("/saves/launcher_conf.json")
        if my_debug:
            print("Success! /saves/launcher_conf.json has been permanently deleted.")
    except OSError:
        print("boot.py: Notice: File was already missing or could not be found.")

# -------------------- end of temporary code ----------------------------------------------

"""
boot.py arguments

  0: storage readonly flag, False means writable to CircuitPython,
     True means read-only to CircuitPython
  1: next code files
2-N: args to pass to next code file

"""


args = read_argv(__file__)
if args is not None and len(args) > 0:
    readonly = args[0]
    next_code_file = None
    remaining_args = None

    if len(args) >= 1:
        next_code_file = args[1]
    if len(args) >= 2:
        remaining_args = args[2:]

    if remaining_args is not None:
        write_argv(next_code_file, remaining_args)

    # if my_debug:
    #     print(f"setting storage readonly to: {readonly}")
    storage.remount("/", readonly=readonly)

    supervisor.set_next_code_file(
        next_code_file,
        sticky_on_reload=False,
        reload_on_error=True,
        working_directory="/".join(next_code_file.split("/")[:-1]),
    )

elif supervisor.runtime.display is None:
    supervisor.set_next_code_file("code.py")
else:
    from launcher_config import LauncherConfig

    supervisor.set_next_code_file(LauncherConfig().boot_animation)
