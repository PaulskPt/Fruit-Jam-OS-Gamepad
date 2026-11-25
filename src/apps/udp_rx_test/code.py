# _*_ coding: utf-8 _*_
# SPDX-FileCopyrightText: 2026 Paulus Schulinck
#
# SPDX-License-Identifier: MIT
##############################
# udp rx test
# For Fruit-Jam-OS
# Adafruit FruitJam board
# App receives, decodes, unpacks and prints to REPL
# UDP Packets sent by X-Plane11 app running on its host pc
# App created with help of Google AI
##############################
import os
import sys
import time
import board  # type: ignore
import busio  # type: ignore
import displayio  # type: ignore
from adafruit_display_text import label # type: ignore
import terminalio  # type: ignore
import atexit
import struct
from digitalio import DigitalInOut  # type: ignore
from adafruit_esp32spi import adafruit_esp32spi # type: ignore
from adafruit_esp32spi import adafruit_esp32spi_socketpool as socketpool # type: ignore
from adafruit_fruitjam.peripherals import Peripherals, VALID_DISPLAY_SIZES, request_display_config  # type: ignore
import neopixel  # type: ignore
import supervisor  # type: ignore

import terminalio   # type: ignore
from adafruit_anchored_group import AnchoredGroup   # type: ignore
from adafruit_anchored_tilegrid import AnchoredTileGrid   # type: ignore
from adafruit_argv_file import read_argv, write_argv   # type: ignore
from adafruit_bitmap_font import bitmap_font # type: ignore
from adafruit_display_text.bitmap_label import Label   # type: ignore
from adafruit_display_text.text_box import TextBox   # type: ignore
from adafruit_displayio_layout.layouts.grid_layout import GridLayout   # type: ignore
from launcher_config import LauncherConfig # type: ignore

# --- Configuration & Debug Flags ---
DEST_PORT = 49000
my_debug = False
use_fruitjam = True
use_neopixels = True
use_display = True
Stop = False

show_hex_grid = True
show_cockpit_telemetry = True

fruitjam = Peripherals()
BLINK_ALL_NEOPIXELS = 100
fruitjam.neopixels.brightness = 0.1

GREEN = (0,   255, 0)
RED   = (255,   0, 0)
OFF   = (0,     0, 0)

# --- Hardware Initialization (Adafruit FruitJam) ---
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = board.SPI()
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
sock = None

app = {} # Create an empty dict

#  Invalid display size. Must be one of: {(360, 200), (720, 400), (320, 240), (640, 480)}
try:
    if VALID_DISPLAY_SIZES is not None:
        print(f"global: VALID_DISPLAY_SIZES = {VALID_DISPLAY_SIZES}")
    else:
        VALID_DISPLAY_SIZES = {(360, 200), (720, 400), (320, 240), (640, 480)}
except NameError:
    VALID_DISPLAY_SIZES = {(360, 200), (720, 400), (320, 240), (640, 480)}

# Display settings copied from /code.py
if (width_config := os.getenv("CIRCUITPY_DISPLAY_WIDTH")) is not None:
    if type(width_config) is str and width_config.isdigit():
        width_config = int(width_config)
    if width_config not in [x[0] for x in VALID_DISPLAY_SIZES]:
        raise ValueError(f"Invalid display size. Must be one of: {VALID_DISPLAY_SIZES}")
    for display_size in VALID_DISPLAY_SIZES:
        if display_size[0] == width_config:
            break
else:
    display_size = (720, 400)

print(f"global: display_size= {display_size}")
request_display_config(*display_size)
display = supervisor.runtime.display

launcher_config = LauncherConfig()

my_debug = launcher_config.data.get("my_debug", False)

SCREENSAVER_TIMEOUT = launcher_config.screensaver_timeout
last_interaction_time = time.monotonic()
screensaver = None
previous_mouse_location = [0, 0]

grps_dict = { 0: "udp_rx_group",
              1: "msgs_group",
              2: "hex_grid_group",
              3: "telemetry_group"
}

grps_dict_rev = { "udp_rx_group": 0,
                  "msgs_group": 1,
                  "hex_grid_group": 2,
                  "telemetry_group": 3
}

telemetry_dict = {  0: "HEAD",
                    3: "Speeds",
                   17: "Pos & Alt",
                   20: "Pitch, Roll & Hdg",
                   96: "COMs",
                   97: "NAVs",
                  102: "DME"}

scale = 1
if display.width > 360:
    scale = 1  # was: 2 -- When scale = 1 then fill_hex_grid is more complete, however the text font is smaller

font_file = "/fonts/terminal.lvfontbin"
font = bitmap_font.load_font(font_file)
# 1. Instantiate your main root scaled group container
scaled_group = displayio.Group(scale=scale)
display.root_group = scaled_group

# 2. FIX: Scale down the background bitmap allocation size
# Since it lives inside scaled_group, the scale factor multiplies it back to full screen!
background_bmp = displayio.Bitmap(display.width // scale, display.height // scale, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = launcher_config.palette_bg
bg_tg = displayio.TileGrid(bitmap=background_bmp, pixel_shader=bg_palette)
scaled_group.append(bg_tg)

# 3. Canvas constraints calculations
WIDTH = int(298 / 360 * display.width // scale)
HEIGHT = int(182 / 200 * display.height // scale)

# 4. Main screen menu title banner element
menu_title_txt = Label(font, text="X-Plane11 UDP RX test", color=launcher_config.palette_fg)
menu_title_txt.anchor_point = (0.5, 0.5)
menu_title_txt.anchored_position = (display.width // (2 * scale), 2)
scaled_group.append(menu_title_txt)

startup_splash_txt = Label(font, text="Wait, starting up...", color=launcher_config.palette_fg)
startup_splash_txt.anchor_point = (0.5, 0.5)
# Centers it horizontally, and drops it vertically right to the center of the viewport
startup_splash_txt.anchored_position = (display.width // (2 * scale), display.height // (2 * scale))
scaled_group.append(startup_splash_txt)

# 5. Instantiate views nested directly within the scaled system coordinate plane
msgs_group = displayio.Group()  
scaled_group.append(msgs_group)

telemetry_group = displayio.Group()
scaled_group.append(telemetry_group)

hex_grid_group = displayio.Group()
scaled_group.append(hex_grid_group)

# Telemetry Group Index Mappings
TLM_TITLE = 0
TLM_LINE1 = 1
TLM_SPEEDS = 2
TLM_PRH    = 3
TLM_POSALT = 4
TLM_COMS   = 5
TLM_NAVS   = 6
TLM_DME    = 7
TLM_LINE2  = 8

# Hex Grid Group Index Mappings
HEX_TITLE    = 0
HEX_HDG      = 1
HEX_DIVIDER1 = 2
HEX_GRID_TXT = 3
HEX_DIVIDER2 = 4


# --- 1. Fix the Visibility Helper Functions ---
def hide_all_groups():
    """Hides all text view layers entirely."""
    # Hide the main background menu title if we are actively viewing data
    menu_title_txt.hidden = True
    msgs_group.hidden = True
    telemetry_group.hidden = True
    hex_grid_group.hidden = True

def _unhide_msgs_group():
    hide_all_groups()
    msgs_group.hidden = False

def _unhide_telemetry_group():
    hide_all_groups()
    telemetry_group.hidden = False
    
def _unhide_hex_grid_group():
    hide_all_groups()
    hex_grid_group.hidden = False

def strip_glyph(msg: str=""):
    TAG = "strip_glyph(): "
    clean_msg = ""
    
    if not isinstance(msg, str):
        return clean_msg
    le = len(msg)
    if len == 0:
        return clean_msg
    
    if msg.find("° ") >= 0:
        clean_msg = msg.replace("° ", "* ")
        print(TAG+"degrees glyph found and replaced")
    elif msg.find("👉 ") >= 0:
        clean_msg = msg.replace("👉 ", " ")
        print(TAG+"hand glyph found and replaced")
    elif msg.find("⏸️ ") >= 0:
        clean_msg = msg.replace("⏸️ ", " ")
        print(TAG+"stop glyph found and replaced")
    else:
        clean_msg = msg
    return clean_msg

# Keep track of the active log lines globally
log_history = []
MAX_LOG_LINES = 10 # Adjust this number depending on how many fit on your screen height

def log_to_screen(*args):
    """Gathers logs silently in the background buffer without forcing immediate display redraws."""
    global log_history
    
    msg_string = " ".join(str(arg) for arg in args)
    clean_msg = strip_glyph(msg_string)
    
    log_history.append(clean_msg)
    if len(log_history) > MAX_LOG_LINES:
        log_history.pop(0)

def flush_log_to_screen():
    """Flushes the entire gathered log history buffer to the screen in a single static frame update."""
    # Permanently remove the startup text from the scaled root group so it stops bleeding through
    if "startup_splash_txt" in globals() and startup_splash_txt in list(scaled_group):
        scaled_group.remove(startup_splash_txt)

    if len(msgs_group) > 1:
        # 1. Populate the inner text box container
        msgs_group[1].text = "\n".join(log_history)
        
        # 2. FIX: Explicitly unhide the text box child layer!
        msgs_group[1].hidden = False
        
        # 3. Bring the parent page view online
        msgs_group.hidden = False
        _unhide_msgs_group()


def wifi_connect():
    TAG = "wifi_connect(): "
    #t = "Connecting to AP..."
    #log_to_screen(t)
    #t = TAG + t
    #print(t)
    
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

    if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
        print(TAG + "ESP32 found and in idle mode")
    elif esp.status == adafruit_esp32spi.WL_STOPPED:
        t = f"esp.status= WL_STOPPED ({esp.status})"
        log_to_screen(t)
        t = TAG + t
        print(t)
    
    t = "ESP Firmware version: " + esp.firmware_version
    log_to_screen(t)
    t = TAG + t
    print(t)
    
    t = "MAC addr:" + ":".join("%02X" % byte for byte in esp.MAC_address)
    log_to_screen(t)
    t = TAG + t
    print(t)

    t = f"Connecting to: {ssid}"
    log_to_screen(t)
    t = TAG + t
    print(t)
    
    while not esp.is_connected:
        try:
            esp.connect_AP(ssid, password)
        except Exception as e:
            t = f"Failed to connect, retrying: {e}"
            log_to_screen(t)
            t = TAG + t
            print(t)
            try:
                display.root_group = msgs_group
            except ValueError:
                pass
            time.sleep(1)
    ap_name = esp.ap_info.ssid
    rssi_val = esp.ap_info.rssi
    t1a = "Connected to:"
    t1b = "RSSI:"
    log_to_screen(t1a, ap_name, t1b, rssi_val)

    t3 = f"My IP address is: {esp.ipv4_address}"
    log_to_screen(t3)
    
    t1a = TAG + t1a
    t2 = TAG + f"{t1a} {ap_name}, {t1b} {rssi_val}"
    t3 = TAG + t3
    t4 = t2 + "\n" + t3
    print(t4)
    
    try:
        display.root_group = msgs_group
    except ValueError:
        pass

def blink_neopixels(LED_NR: int, COLOR: tuple):
    """Blinks NeoPixel LED green using the library pixel array wrapper."""
    if LED_NR != BLINK_ALL_NEOPIXELS:
        if LED_NR < 0: LED_NR = 0
        elif LED_NR > 5: LED_NR = 5

    if not COLOR in [GREEN, RED, OFF]:
        print(f"Undefined color tuple: {COLOR}")
        return

    if fruitjam is None or fruitjam.neopixels is None:
        return

    for _ in range(2):
        if LED_NR == BLINK_ALL_NEOPIXELS:
            fruitjam.neopixels.fill(COLOR)
        else:
            fruitjam.neopixels[LED_NR] = COLOR
        fruitjam.neopixels.show()
        time.sleep(0.15)
        
        if LED_NR == BLINK_ALL_NEOPIXELS:
            fruitjam.neopixels.fill(OFF)
        else:
            fruitjam.neopixels[LED_NR] = OFF
        fruitjam.neopixels.show()
        time.sleep(0.15)
        
        
# --- 2. Fix the TextBox Coordinates (Remove overlapping anchor layouts) ---
def setup_msgs_group():
    HPos = 10 
    VPos = 10
    VPos_inc = 30
    
    msgs_group_title_txt = Label(font, text="MESSAGES PAGE", color=launcher_config.palette_fg)
    msgs_group_title_txt.anchor_point = (0.5, 0.5)
    msgs_group_title_txt.anchored_position = (display.width // (2 * scale), VPos)
    msgs_group.append(msgs_group_title_txt)

    VPos = VPos + VPos_inc
    
    msgs_txt = TextBox(
        terminalio.FONT,
        text="",
        width=WIDTH-10,
        height=HEIGHT-50,
        align=TextBox.ALIGN_LEFT,
    )
    # Patched: Removed .anchor_point and .anchored_position to prevent AttributeError crashes
    msgs_txt.x = HPos
    msgs_txt.y = VPos
    msgs_txt.hidden = True
    msgs_group.append(msgs_txt)
    

def setup_hex_grid_group():
    HPos = 5 
    VPos = 10
    
    # 0. Title Header Element (Centered perfectly)
    hex_grid_title_txt = Label(font, text="PACKET HEX INSPECTOR", color=launcher_config.palette_fg)    
    hex_grid_title_txt.anchor_point = (0.5, 0.5)
    hex_grid_title_txt.anchored_position = (display.width // (2 * scale), VPos)
    hex_grid_group.append(hex_grid_title_txt)
    
    # 1. MAIN UNIFIED CANVAS TEXT BOX (Holds headers, dividers, and data rows together)
    # FIX: One box means completely uniform vertical spacing line-by-line!
    hex_grid_txt = TextBox(
        terminalio.FONT, 
        text="", 
        width=WIDTH-10, 
        height=HEIGHT-25, 
        align=TextBox.ALIGN_LEFT
    )
    hex_grid_txt.x = HPos
    hex_grid_txt.y = VPos + 25  # Drops it cleanly below the title
    hex_grid_txt.hidden = True
    hex_grid_group.append(hex_grid_txt)
    

def setup_telemetry_group():
    HPos = 10 
    VPos = 10
    VPos_inc = 25  # Tighter vertical layout step so all X-Plane text fits on screen
    
    # 0. Title
    telemetry_group_title_txt = Label(font, text="COCKPIT FLIGHT TELEMETRY SNAPSHOT", color=launcher_config.palette_fg)
    telemetry_group_title_txt.anchor_point = (0.5, 0.5)
    telemetry_group_title_txt.anchored_position = (display.width // (2 * scale), VPos)
    telemetry_group.append(telemetry_group_title_txt)

    VPos = VPos + VPos_inc
    
    # 1. LINE1
    LINE1_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    LINE1_txt.x = HPos
    LINE1_txt.y = VPos
    LINE1_txt.hidden = True
    telemetry_group.append(LINE1_txt)

    VPos = VPos + VPos_inc
    
    # 2. SPEEDS
    speeds_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    speeds_txt.x = HPos
    speeds_txt.y = VPos
    speeds_txt.hidden = True
    telemetry_group.append(speeds_txt)
    
    VPos = VPos + VPos_inc
    
    # 3. PRH
    PRH_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    PRH_txt.x = HPos
    PRH_txt.y = VPos
    PRH_txt.hidden = True
    telemetry_group.append(PRH_txt)
    
    VPos = VPos + VPos_inc
    
    # 4. POS_ALT
    POS_ALT_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    POS_ALT_txt.x = HPos
    POS_ALT_txt.y = VPos
    POS_ALT_txt.hidden = True
    telemetry_group.append(POS_ALT_txt)
    
    VPos = VPos + VPos_inc
    
    # 5. COMS
    COMS_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    COMS_txt.x = HPos
    COMS_txt.y = VPos
    COMS_txt.hidden = True
    telemetry_group.append(COMS_txt)
    
    VPos = VPos + VPos_inc
    
    # 6. NAVS
    NAVS_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    NAVS_txt.x = HPos
    NAVS_txt.y = VPos
    NAVS_txt.hidden = True
    telemetry_group.append(NAVS_txt)

    VPos = VPos + VPos_inc
    
    # 7. DME
    DME_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    DME_txt.x = HPos
    DME_txt.y = VPos
    DME_txt.hidden = True
    telemetry_group.append(DME_txt)
    
    VPos = VPos + VPos_inc
    
    # 8. LINE2
    LINE2_txt = TextBox(terminalio.FONT, text="", width=WIDTH-10, height=22, align=TextBox.ALIGN_LEFT)
    LINE2_txt.x = HPos
    LINE2_txt.y = VPos
    LINE2_txt.hidden = True
    telemetry_group.append(LINE2_txt)

# --- 3. Clean up the initial appending visibility states ---
# Hide all sub-panels during setup generation
msgs_group.hidden = True
telemetry_group.hidden = True
hex_grid_group.hidden = True

def fill_hex_grid(data_rcvd: bytes = b""):
    """Accepts raw packet bytes and displays them in beautifully aligned 64-byte pages."""
    if not isinstance(data_rcvd, (bytes, bytearray)) or len(data_rcvd) == 0:
        return
    
    # 1. Define layout headers locally to be bundled inside the single TextBox
    hdg_h = " ADDR | 00 01 02 03 04 05 06 07 | ID"
    divider = "------+-------------------------+------------"
    le = len(data_rcvd)
    
    # 2. Page loop: Slice the incoming payload into 64-byte chunks
    for page_offset in range(0, le, 64):
        # Always start each page with the fresh headers at the top
        grid_lines = [
            hdg_h,
            divider
        ]
        
        # Calculate the boundaries of our current page viewport matrix
        page_end = min(page_offset + 64, le)
        
        # 3. Row loop: Process the 64-byte page slice into 8-byte chunks
        for i in range(page_offset, page_end, 8):
            row_addr = f" 0x{i:02X} "
            row_bytes = data_rcvd[i:i+8]
            
            # Format chunk bytes into hex string tokens
            hex_tokens = [f"{b:02X}" for b in row_bytes]
            
            # FIX: Use .ljust(23) to pad the text string to a fixed grid width of 23 characters.
            # This handles short rows (like 5 bytes) and keeps the right margin perfectly straight.
            raw_str = " ".join(hex_tokens)
            data_str = "%-23s" % raw_str
            
            # Determine the shorthand telemetry Group ID tag depending on index offsets
            id_tag = "    "
            if i == 0x00 and data_rcvd[:4] == b"DATA":
                id_tag = " HEAD&Speeds"
            elif 0x05 <= i < 0x28:
                id_tag = " #03 Speeds"
            elif 0x28 <= i < 0x48:
                id_tag = " #17 PiRoHdg" # 11 hex
            elif 0x48 <= i < 0x70:
                id_tag = " #20 PosAlt"  # 14 hex
            elif 0x70 <= i < 0x90:
                id_tag = " #96 COMs"    # 60 hex
            elif 0x90 <= i < 0xB8:
                id_tag = " #97 NAVs"    # 61 hex
            elif 0xB8 <= i < 0xDF:
                id_tag = " #102 DME"    # 66 hex
                
            # Stitch row together perfectly bounded
            grid_lines.append(f"{row_addr}| {data_str} |{id_tag}")
            
        # 4. Append a clean footer to show page progress
        grid_lines.append(divider)
        grid_lines.append(f" BYTES: {page_offset}-{page_end} of {le}".center(37))
        
        # 5. FIX: Target index 1 directly (the unified TextBox) and make it visible
        hex_grid_group[1].text = "\n".join(grid_lines)
        hex_grid_group[1].hidden = False
        
        # 6. Render onto the hardware panel
        _unhide_hex_grid_group()
        
        # 7. Pause execution for 5 seconds per page so you can read the data blocks
        # Only sleep if there are more pages left to show in this payload stream
        if page_offset + 64 < le:
            time.sleep(5.0)



def fill_telemetry(data_rcvd):
    """Parses and formats modern X-Plane 11 uniform datagram groups to the REPL console."""
    TAG = "fill_telemetry(): "
    
    if len(data_rcvd) < 5 or data_rcvd[:4] != b"DATA":
        return

    for offset in range(5, len(data_rcvd), 36):
        if offset + 36 > len(data_rcvd):
            break

        group_id = struct.unpack("<I", data_rcvd[offset:offset+4])
        floats = struct.unpack("<ffffffff", data_rcvd[offset+4:offset+36])

        active_id = group_id[0]
        if not my_debug:
            if active_id in telemetry_dict.keys():
                aid_txt = telemetry_dict[active_id]
            else:
                aid_txt = ""
            print(TAG+f"active_id= {active_id:>3d} {aid_txt}")

        if active_id in [17, 20]:
            degs_ch = "*" # instead of '°'
        else:
            degs_ch = ""

        if active_id == 3:      # Speeds
           telemetry_group[TLM_SPEEDS].text = f"  IAS: {floats[0]:.1f} | TAS: {floats[2]:.1f} | GS: {floats[3]:.1f} Kt"    
           telemetry_group[TLM_SPEEDS].hidden = False        
        elif active_id == 17:   # Attitude
            telemetry_group[TLM_PRH].text = f"  Pitch: {floats[0]:.1f}{degs_ch} | Roll: {floats[1]:.1f}{degs_ch} | Hdg: {floats[3]:.1f}{degs_ch}"
            telemetry_group[TLM_PRH].hidden = False
        elif active_id == 20:   # Position & Altitude
            if floats[0] >= 0:
                NS = "N"
            else:
                NS = "S"
            if floats[1] >= 0:
                EW = "E"
            else:
                EW = "W"
            telemetry_group[TLM_POSALT].text = f"  Pos: {floats[0]:.3f}{degs_ch} {NS}, {floats[1]:.3f}{degs_ch} {EW} | Alt: {floats[2]:.0f} FT"
            telemetry_group[TLM_POSALT].hidden = False
        elif active_id == 96:   # COM Frequencies
            telemetry_group[TLM_COMS].text = f"  COM1: {floats[0]/100.0:.2f} | COM2: {floats[3]/100.0:.2f} MHz"
            telemetry_group[TLM_COMS].hidden = False
        elif active_id == 97:   # NAV Frequencies
            nav1_act  = floats[0] / 100.0
            nav1_stby = floats[1] / 100.0
            nav2_act  = floats[4] / 100.0 if floats[4] > 0 else 114.20
            nav2_stby = floats[3] / 100.0 if floats[3] > 0 else 113.90
            
            nav2_act_str  = "N/A" if nav2_act < 0 else f"{nav2_act:.2f}"
            nav2_stby_str = "N/A" if nav2_stby < 0 else f"{nav2_stby:.2f}"
            
            # Fixed target index here (was accidentally targeting COMS_txt)
            telemetry_group[TLM_NAVS].text = f"  NAV1: {nav1_act:.2f} | NAV2: {nav2_act_str} MHz"
            telemetry_group[TLM_NAVS].hidden = False
        elif active_id == 102:  # DME Status
            # Fixed target index here (was accidentally targeting COMS_txt)
            telemetry_group[TLM_DME].text = f"  NAV1 DME Dist: {floats[3]:.1f} NM | GS: {floats[4]:.0f} Kt"
            telemetry_group[TLM_DME].hidden = False

    if scale == 1:
        telemetry_group[TLM_LINE2].text = "-" * 44 + "\n"  # was: 64
        telemetry_group[TLM_LINE2].hidden = False
    
    _unhide_telemetry_group()

def setup():
    global sock, DEST_PORT, Stop, esp
    TAG = "setup(): "
  
    # NOTE: These setup_... must be before log_to_screen(), wifi_connect() etcetera.  
    setup_msgs_group()    
    setup_hex_grid_group()    
    setup_telemetry_group()
    
    t = "Connecting to WiFi..."
    log_to_screen(t)
    t = TAG + t
    print(t)
    
    wifi_connect()
    
    if esp and esp.is_connected:
        try:
            socket_num = esp.get_socket()
            if socket_num == 255:
                print(TAG + "Error: No free hardware socket slots on the ESP32!")
                Stop = True
                return
            
            esp.start_server(DEST_PORT, socket_num, conn_mode=esp.UDP_MODE)
            sock = socket_num 
            if my_debug:
                print(TAG + f"Direct hardware UDP socket #{sock} firmly bound via esp.UDP_MODE.")
        except Exception as e:
            print(TAG + f"Error allocating hardware socket: {e}")
            Stop = True
    else:
        print(TAG + "WiFi connection missing.")
        Stop = True




def main():
    global Stop, DEST_PORT, esp, sock, show_hex_grid
    TAG = "main(): "
    numbytes_avail = 0
    data_rcvd = []
    pause_duration = 0
    start_time = 0
    flush_bytes = 0
    
    loopnr = 0
    start_t = time.monotonic()
    current_t = 0
    elapsed_t = 0
    interval_t = 100
    
    setup()
    
    if not Stop and sock is not None:
        # Flush queue to clear menu-selection residue out of the chip's input cache
        while supervisor.runtime.serial_bytes_available:
            sys.stdin.read(1)
            time.sleep(0.01)

        t = f"Listening for UDP packets on port {DEST_PORT}..."
        log_to_screen(t)
        t = TAG + t
        print(t)
        
        t = "Press ANY KEY or MOUSE to exit app!"
        log_to_screen(t)
        print("👉 " + t)
        
        # NEW: Flush everything to the display at once and pause so you can read it!
        flush_log_to_screen()
        time.sleep(5.0)
        
        # Clear the terminal history buffer so it's fresh for actual error/messages later
        log_history = [] 

        while not Stop:
            print(TAG+f"loopnr= {loopnr}")
            try:
                display.root_group = scaled_group
                
                if supervisor.runtime.serial_bytes_available:
                    sys.stdin.read(1)
                    print("\n🛑 Stop signal detected via keyboard input!")
                    break
                
                # 1. Evaluate your loop interval checkpoint 
                current_t = time.monotonic()
                elapsed_t = int(float(current_t - start_t))
                if elapsed_t >= interval_t:
                    start_t = current_t
                    show_hex_grid = True

                # 2. Wait for packet to arrive
                while numbytes_avail == 0:
                    try:
                        numbytes_avail = esp.socket_available(sock)
                        time.sleep(0.02)
                    except OSError as e:
                            print(TAG+ f"Error: {e}")
                            if getattr(e, "errno", None) in (11, 116):  # EAGAIN / ETIMEDOUT
                                pass
                
                if numbytes_avail > 0:
                    data_rcvd = esp.socket_read(sock, numbytes_avail)
                    if data_rcvd:
                        if use_neopixels:
                            blink_neopixels(0, GREEN)
                            
                            if not my_debug:
                                print(TAG+f"elapsed_t = {elapsed_t}, interval_t = {interval_t}")
                                print(TAG+f"show_hex_grid = {"True" if show_hex_grid else "False"}")
                            
                            # 3. OPTION A: Run the diagnostic Hex Grid loop block
                            if show_hex_grid:
                                print(TAG + "Displaying HEX Snapshot... Pausing for 5 seconds.")
                                fill_hex_grid(data_rcvd)
                                show_hex_grid = False  # Reset flag immediately
                                time.sleep(5.0)        # Freeze frame time for inspection
                            else:
                                # 4. OPTION B: Run the standard telemetry layout updates instead
                                fill_telemetry(data_rcvd)
                                pause_duration = 10.0
                                print(TAG + f"⏸️  Display paused for {int(pause_duration)} seconds... (Background SPI active)")
                                time.sleep(pause_duration) # Actually execute your 20-second pause constraint
                                
                                start_time = time.monotonic()
                                while time.monotonic() - start_time < pause_duration:
                                    if supervisor.runtime.serial_bytes_available:
                                        break
                                    flush_bytes = esp.socket_available(sock)
                                    if flush_bytes > 0:
                                        try:
                                            esp.socket_read(sock, flush_bytes)
                                        except OSError as e:
                                            print(TAG+ f"Error: {e}")
                                            if getattr(e, "errno", None) in (11, 116):  # EAGAIN / ETIMEDOUT
                                                pass
                                    time.sleep(0.005)
                                    
                            if supervisor.runtime.serial_bytes_available:
                                sys.stdin.read(1)
                                print("\n🛑 Stop signal detected during pause window!")
                                break
                                
                            print(TAG + "▶️  Resuming live packet capture...")
                            
                if supervisor.runtime.serial_bytes_available:
                    sys.stdin.read(1)
                    print("\n🛑 Stop signal detected during pause window!")
                    break
            
                time.sleep(0.002)  
                loopnr += 1
                if loopnr > 999:
                    loopNr = 0
            except KeyboardInterrupt:
                break
                
        print(TAG + "Shutting down network pipelines cleanly...")
        if sock is not None:
            try:
                esp.socket_close(sock)
                print(TAG + f"Direct hardware UDP socket #{sock} closed successfully.")
            except Exception as e:
                print(TAG + f"Error closing socket: {e}")
        Stop = True


def atexit_callback():
    print("inside atexit callback")
    try:
        from adafruit_argv_file import write_argv  # type: ignore
        write_argv(__file__, [])
    except Exception: pass
    supervisor.set_next_code_file("/code.py", sticky_on_reload=False, reload_on_error=True, working_directory="/")


atexit.register(atexit_callback)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        import traceback
        traceback.print_exception(err)
        time.sleep(5)
    finally:
        if Stop:
            Stop = False 
            supervisor.reload()
        else:
            while True: time.sleep(1)
