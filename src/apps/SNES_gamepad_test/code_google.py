import array
import time
import usb.core
import adafruit_usb_host_descriptors

# --- Configuration ---
GAMEPAD_ADDRESS = 0x81
BUF_LEN = 64
NR_BYTES = 8

VERBOSE_SCAN = False
GAMEPAD_SHOW2 = True
START_BIT = 0x20  # The value for the START button

BTN_DPAD_UPDOWN_INDEX = 1
BTN_DPAD_LEFTRIGHT_INDEX = 0
BTN_ABXY_INDEX = 5
BTN_OTR_INDEX = 6

# --- Setup Device ---
device = None
print("Searching for gamepad...")
while device is None:
    for d in usb.core.find(find_all=True):
        device = d
        break
    time.sleep(0.1)

device.set_configuration()
if device.is_kernel_driver_active(0):
    device.detach_kernel_driver(0)

# --- Helper Functions ---
def print_array(arr):
    """Prints 8 bytes in a clean hex format."""
    print(" ".join([f"{int(x):02x}" for x in arr]))

def reports_equal(report_a, report_b, length=BUF_LEN):
    """Compares two reports up to the specified length."""
    if report_a is None or report_b is None:
        return False
    for i in range(length):
        if report_a[i] != report_b[i]:
            return False
    return True

# --- Main Logic ---
buf = array.array("B", [0] * BUF_LEN)
last_report = None

print("Monitoring Gamepad... Press Ctrl+C to stop.")


# --- ADD THIS BEFORE YOUR WHILE TRUE LOOP ---
print("Syncing with gamepad... please release all buttons.")

# 1. Flush the USB hardware buffer of any 'old' menu packets
try:
    while True:
        # Read with a tiny timeout until it fails (meaning buffer is empty)
        device.read(GAMEPAD_ADDRESS, buf, timeout=5)
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

while True:
    b_ud_starts = None
    b_lr_starts = None
    b_abxy_starts = None
    b_otr_starts = None
    count = None
    b_val_ud = None
    b_val_lr = None
    b_val_otr = None

    try:
        # NON-BLOCKING READ: We check for a packet for only 10ms.
        # This keeps the loop moving so we never miss the START button.
        count = device.read(GAMEPAD_ADDRESS, buf, timeout=10)
    except usb.core.USBError:
        # No data received within timeout; just try again.
        continue

    if count > 0:
        # 1. Check if the state has actually changed from the last valid read
        if last_report is None or not reports_equal(buf, last_report, BUF_LEN):

            b_ud_starts = [buf[i] for i in range(BTN_DPAD_UPDOWN_INDEX, BUF_LEN, NR_BYTES)]

            b_lr_starts = [buf[i] for i in range(BTN_DPAD_LEFTRIGHT_INDEX, BUF_LEN, NR_BYTES)]

            b_abxy_starts = [buf[i] for i in range(BTN_ABXY_INDEX, BUF_LEN, NR_BYTES)]

            # 2. Extract the START/SELECT row values (6, 14, 22...)
            b_otr_starts = [buf[i] for i in range(BTN_OTR_INDEX, BUF_LEN, NR_BYTES)]

            if GAMEPAD_SHOW:
                print(f"b_ud_starts    = {b_ud_starts}")
                print(f"b_lr_starts    = {b_lr_starts}")
                print(f"b_abxy_starts  = {b_abxy_starts}")
            if GAMEPAD_SHOW2:
                print(f"b_otr_starts = {b_otr_starts}")

            b_val_ud = buf[BTN_DPAD_UPDOWN_INDEX]
            if VERBOSE_SCAN:
                print(f"\nb_val_ud = {b_val_ud}")

            if GAMEPAD_SHOW:
                if b_val_ud == 0x0:
                    print("D-Pad UP pressed")
                elif b_val_ud == 0xFF:
                    print("D-Pad DOWN pressed")

            b_val_lr = buf[BTN_DPAD_LEFTRIGHT_INDEX]
            if VERBOSE_SCAN:
                print(f"\nb_val_lr = {b_val_lr}")
            if GAMEPAD_SHOW:
                if  b_val_lr == 0:
                    print("D-Pad LEFT pressed")
                elif b_val_lr == 0xFF:
                    print("D-Pad RIGHT pressed")

            b_val_abxy = buf[BTN_ABXY_INDEX]
            if VERBOSE_SCAN:
                print(f"\nb_val_abxy = {b_val_abxy}")
            if GAMEPAD_SHOW:
                if b_val_abxy == 0x2F:
                    print("A pressed")
                elif b_val_abxy == 0x4F:
                    print("B pressed")
                elif b_val_abxy == 0x1F:
                    if x_pressed:
                        break # Exit app
                    print("X pressed")
                    print("Do you want to exit this app?")
                    x_pressed = True
                    continue
                elif b_val_abxy == 0x8F:
                    print("Y pressed")

            if GAMEPAD_SHOW2:
                print(f"BTN_OTHER_INDEX = {BTN_OTHER_INDEX}")

            b_val_otr = buf[BTN_OTHER_INDEX]
            if VERBOSE_SCAN or GAMEPAD_SHOW2:
                print(f"\nb_val_otr = {b_val_otr}")

            if GAMEPAD_SHOW2:
                if b_val_otr == 0x01:
                    print("L shoulder pressed")
                elif b_val_otr == 0x02:
                    print("R shoulder pressed")
                elif b_val_otr == 0x10:
                    print("SELECT pressed")
                elif b_val_otr == 0x20:
                    print("START pressed")

            # 3. Handle Detection
            if 0x20 in b_otr_starts:
                print(">>> START BUTTON PRESSED <<<")

            # 4. Optional Debug Display
            if GAMEPAD_SHOW2:
                for i in range(0, BUF_LEN, 8):
                    # Uses f-string padding for alignment in CircuitPython
                    print(f"buf[{i:2}:{i+8:2}] = ", end='')
                    print_array(buf[i:i+8])
                print("-" * 20)

            # 5. Update last_report with a copy to track state changes
            last_report = buf[:]
