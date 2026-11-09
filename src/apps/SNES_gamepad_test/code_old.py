# SPDX-FileCopyrightText: Copyright (c) 2025 Tim Cocks for Adafruit Industries
#
# SPDX-License-Identifier: MIT
# downloaded from: https://learn.adafruit.com/usb-game-controller-with-snes-like-layout/circuitpython
# by @PaulskPt
# version 2026-04-22, version 2.0
#
import array
import time
import usb.core
import adafruit_usb_host_descriptors
import supervisor

# Set to true to print detailed information about all devices found
GAMEPAD_ADDRESS = 0x81
VERBOSE_SCAN = False
GAMEPAD_SHOW = True
GAMEPAD_SHOW2 = True

BTN_DPAD_UPDOWN_INDEX = 1
BTN_DPAD_LEFTRIGHT_INDEX = 0
BTN_ABXY_INDEX = 5
BTN_OTR_INDEX = 6
BUF_LEN = 64
NR_BYTES = 8

DIR_IN = 0x80
controller = None

if VERBOSE_SCAN:
    for device in usb.core.find(find_all=True):
        controller = device
        zPid = hex(device.idProduct)
        zVid = hex(device.idVendor)
        zMan = device.manufacturer
        zProd = device.product
        zSer = device.serial_number
        zPortNrs = device.port_numbers
        noInfo = "---"
        if zProd == "USB Keyboard":
            continue  # do not print the USB Keyboard info
        print("type zSer = ", end='')
        print(type(zSer))
        print("pid: ", end='')
        if zPid is not None:
            print(zPid)
        else:
            print(noInfo)
        #zVid = hex(device.idVendor)
        print("vid: ", end='')
        if zVid is not None:
            print(zVid)
        else:
            print(noInfo)
        #zMan = device.manufacturer
        print("manufacturer: ", end='')
        if zMan is not None:
            print(zMan, end='')
        else:
            print(noInfo)
        #zProd = device.product
        print("product: ", end='')
        if zProd is not None:
            print(zProd)
        else:
            print(noInfo)
        #zSer = device.serial_number
        print("serial: ", end='')
        if zSer is not None:
            print(zSer)
        else:
            print(noInfo)
        print("port numbers: ", end='')
        if zPortNrs is not None:
            print(zPortNrs)
        else:
            print(noInfo)
        print("config[0]: ")
        config_descriptor = adafruit_usb_host_descriptors.get_configuration_descriptor(
            device, 0
        )

        i = 0
        while i < len(config_descriptor):
            descriptor_len = config_descriptor[i]
            descriptor_type = config_descriptor[i + 1]
            if descriptor_type == adafruit_usb_host_descriptors.DESC_CONFIGURATION:
                config_value = config_descriptor[i + 5]
                print(f" value: {config_value:d}")
            elif descriptor_type == adafruit_usb_host_descriptors.DESC_INTERFACE:
                interface_number = config_descriptor[i + 2]
                interface_class = config_descriptor[i + 5]
                interface_subclass = config_descriptor[i + 6]
                print(f" interface[{interface_number:d}]")
                print(
                    f"  class: {interface_class:02x} subclass: {interface_subclass:02x}"
                )
            elif descriptor_type == adafruit_usb_host_descriptors.DESC_ENDPOINT:
                endpoint_address = config_descriptor[i + 2]
                if endpoint_address & DIR_IN:
                    print(f"  INput: 0x{endpoint_address:02x}")
                else:
                    print(f"  OUTput: 0x{endpoint_address:02x\n}")
            print(f"descriptor_len = {descriptor_len}\n")
            print(f"i = {i}\n")
            i += descriptor_len
    # ------- Test to move this part into the IF .... part

    if zMan is None:
        zManTxt = "Manufacturer unknown"
    else:
        zManTxt = "Manufacturer" + zMan
    if zProd is None:
        zProdTxt = "Product unknown"
    else:
        zProdTxt = "Product" + zProd
    if zSer is None:
        zSerTxt = "Serial device nr unknown"
    else:
        zSerTxt = "Serial device nr = " + zSer
    print(
        f"configuration set for: {zManTxt}, {zProdTxt}, {zSerTxt}" # device.manufacturer}, {device.product}, {device.serial_number}"
    )
    # ------- end of move part -------------------

# get the first device found
device = None
while device is None:
    for d in usb.core.find(find_all=True):
        device = d
        break
    time.sleep(0.1)

if VERBOSE_SCAN:
    if device is not None:
        print(f"device = {type(device)}\n")
        print("dir(device) = ")
        for d1 in dir(device):
            print(f"\t{d1}")

# set configuration so we can read data from it
device.set_configuration()

# Test to see if the kernel is using the device and detach it.
if device.is_kernel_driver_active(0):
    if VERBOSE_SCAN:
        print("detaching device from kernel")
    device.detach_kernel_driver(0)

def print_array(arr, max_index=None, fmt="hex"):
    """
    Print the values of an array
    :param arr: The array to print
    :param max_index: The maximum index to print. None means print all.
    :param fmt: The format to use, either "hex" or "bin"
    :return: None
    """
    out_str = ""
    if max_index is None or max_index >= len(arr):
        length = len(arr)
    else:
        length = max_index

    for _ in range(length):
        if fmt == "hex":
            out_str += f"{int(arr[_]):02x} "
        elif fmt == "bin":
            out_str += f"{int(arr[_]):08b} "
    print(out_str)


def reports_equal(report_a, report_b, check_length=None):
    global VERBOSE_SCAN
    """
    Test if two reports are equal. If check_length is provided then
    check for equality in only the first check_length number of bytes.

    :param report_a: First report data
    :param report_b: Second report data
    :param check_length: How many bytes to check
    :return: True if the reports are equal, otherwise False.
    """

    if VERBOSE_SCAN:
        print(f"param report_a = \"{report_a}\"\n")
        print(f"param report_b = \"{report_b}\"\n")

    if (
        report_a is None
        and report_b is not None
        or report_b is None
        and report_a is not None
    ):
        return False

    length = len(report_a) if check_length is None else check_length
    for _ in range(length):
        if report_a[_] != report_b[_]:
            return False
    return True

#idle_state = None
#prev_state = None
pr_cnt = 0
x_pressed = False
y_pressed = False
buf = array.array("B", [0] * BUF_LEN)
count = 0

# Empty the gamepad buffer:
# --- Add this right before "while True:" ---
print("Flushing buffer...")
try:
    # Read everything currently waiting until it's empty
    while device.read(GAMEPAD_ADDRESS, buf, timeout=10):
        pass
except usb.core.USBError:
    pass


# 2. Wait until the controller actually reports an IDLE state (all zeros at index 6)
# This prevents the script from 'catching' the tail end of the menu's START press.
while True:
    try:
        count = device.read(GAMEPAD_ADDRESS, buf, timeout=10)
        if count > 0:
            # Check the specific byte that was 0x20 in your output
            if buf[6] == 0x00:
                print("Gamepad ready!")
                break
    except usb.core.USBError:
        # If no data is coming at all, the controller is already idle
        print("Gamepad ready (no data)!")
        break

# Now start the actual monitoring
last_report = None # was: buf[:]
# --------------------------------------------

idle_state = None
prev_state = None

sDP = "D-Pad"
sP = " pressed"
sSH = "Shoulder"

b_val_ud   = 0
b_val_lr   = 0
b_val_abxy = 0
b_val_otr  = 0

while True:
    # Initiate / clean buffer
    buf = array.array("B", [0] * BUF_LEN)

    try:
        while True:
            count = device.read(GAMEPAD_ADDRESS, buf, timeout=10) # --- READ THE GAMEPAD DATA ---
            if count > 0:
                #print(f"device bytes read: {count}")
                #count = 0
                break

    except usb.core.USBTimeoutError:
        if VERBOSE_SCAN:
            print("usb.core TimeoutError occurred!")
        continue
    except KeyboardInterrupt:
        print("KeyboardInterrupt! Exiting app...")
        break

    if idle_state is None:
        idle_state = buf[:]
        print("Idle state: ", end='')
        print_array(idle_state[:8], max_index=count, fmt="hex")
        print()

    equals_a = reports_equal(buf, prev_state, NR_BYTES)
    equals_b = reports_equal(buf, idle_state, NR_BYTES)

    if not equals_a and not equals_b:

        b_val_ud   = buf[BTN_DPAD_UPDOWN_INDEX]
        b_val_lr   = buf[BTN_DPAD_LEFTRIGHT_INDEX]
        b_val_abxy = buf[BTN_ABXY_INDEX]
        b_val_otr  = buf[BTN_OTR_INDEX]

        if b_val_ud == 0x0:
            print(f"{sDP} UP {sP}")
        elif b_val_ud == 0xFF:
            print(f"{sDP} DOWN {sP}")

        if  b_val_lr == 0:
            print(f"{sDP} LEFT {sP}")
        elif b_val_lr == 0xFF:
            print(f"{sDP} RIGHT {sP}")

        if b_val_abxy == 0x2F:
            print(f"A {sP}")
        elif b_val_abxy == 0x4F:
            print(f"B {sP}")
        elif b_val_abxy == 0x1F:
            print(f"X {sP}")
            print("Next press Y when you want to exit this app")
            x_pressed = True
            prev_state = buf[:]
            continue
        elif b_val_abxy == 0x8F:
            print(f"Y {sP}")
            if x_pressed:
                break # Exit app
        else:
            x_pressed = False

        if b_val_otr == 0x01:
            print(f"L {sSH} {sP}")
        elif b_val_otr == 0x02:
            print(f"R {sSH} {sP}")
        elif b_val_otr == 0x10:
            print(f"SELECT {sP}")
        elif b_val_otr == 0x20:
            print(f"START {sP}")
            # break

    prev_state = buf[:]

# Go back to the main code.py
print("Exiting app in three seconds...\n\n")
time.sleep(3)
supervisor.reload()
