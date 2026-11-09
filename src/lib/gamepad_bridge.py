# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
# SPDX-License-Identifier: MIT
"""
gamepad_bridge.py: Persistent state flagging via supervisor boot arguments.
"""
import __main__
from adafruit_argv_file import read_argv

def register_gamepad_presence():
    """Returns the argument array containing the gamepad flag string."""
    # print("--- Gamepad Bridge: State flag packaged into arguments ---")
    return ["HAS_GAMEPAD"]

def verify_bridged_gamepad():
    """Checks if the launcher passed the 'HAS_GAMEPAD' argument string to this app."""
    try:
        # Dynamically read the arguments belonging to the running main app file
        args = read_argv(__main__.__file__)
        if args is not None and "HAS_GAMEPAD" in args:
            return True
    except Exception as e:
        print(f"Bridge read error: {e}")
    return False

def clear_bridge_flag():
    """Placeholder function to keep API consistency."""
    pass
