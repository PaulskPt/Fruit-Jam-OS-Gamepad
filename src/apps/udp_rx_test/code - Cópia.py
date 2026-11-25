# _*_ coding: utf-8 _*_
# SPDX-FileCopyrightText: 2026 Paulus Schulinck
#
# SPDX-License-Identifier: MIT
##############################
# udp rx test
##############################
import os
import time
import atexit 
import gc 
import supervisor  # type: ignore

my_debug = True
use_fruitjam = True

if use_fruitjam:
    #import socketpool

    from os import getenv
    import adafruit_connection_manager # type: ignore
    import adafruit_requests # type: ignore
    import board # type: ignore
    from digitalio import DigitalInOut # type: ignore
    from adafruit_esp32spi import adafruit_esp32spi


Stop = False
use_wifi = True
use_ping = False
wifi_is_connected = False
esp_ipv4_address = None
ip = 0
s_ip = ""
esp = None
pool = None
sock = None

ssid = None
password = None

SERVER_IP = "192.168.1.77"
DEST_IP = "192.168.1.80"
SERVER_PORT = 49001
DEST_PORT = 49000

def wifi_is_connected():
    global ip, s_ip
    TAG= "code.py/wifi_is_connected(): "
    ret = False

    if use_fruitjam:
        ip = esp.ipv4_address
    else:
        ip = wifi.radio.ipv4_address

    if ip:
        s_ip = str(ip)
        le_s_ip = len(s_ip)

    if s_ip is not None and len(s_ip) > 0 and s_ip != '0.0.0.0':
        if not my_debug:
            print(TAG+f"s_ip = {s_ip}")
        myVars.write("client_IP", s_ip) # Save the client IP
        ret = True
    return ret

def wifi_connect():
    global ip, s_ip, pool, ssid, password, wifi_is_connected, esp_ipv4_address, esp
    TAG = "wifi_connect(): "
    if my_debug:
        print(TAG+"Entering...")
    
    scan_networks = False
    adafruit_lookup = False
    google_ping = False
    
    try:
        #import adafruit_connection_manager  # type: ignore
        #import adafruit_requests  # type: ignore
        #from digitalio import DigitalInOut  # type: ignore
        #from adafruit_esp32spi import adafruit_esp32spi

        # Get wifi details and more from a settings.toml file
        # tokens used by this Demo: CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD
        ssid = os.getenv("CIRCUITPY_WIFI_SSID")
        password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

        # print("ESP32 SPI webclient test")

        TEXT_URL = "http://wifitest.adafruit.com/testwifi/index.html"
        JSON_URL = "http://wifitest.adafruit.com/testwifi/sample.json"

        # If you are using a board with pre-defined ESP32 Pins:
        esp32_cs = DigitalInOut(board.ESP_CS)
        esp32_ready = DigitalInOut(board.ESP_BUSY)
        esp32_reset = DigitalInOut(board.ESP_RESET)

        spi = board.SPI()
        esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

        pool = adafruit_connection_manager.get_radio_socketpool(esp)
        ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
        requests = adafruit_requests.Session(pool, ssl_context)

        if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
            print(TAG+"ESP32 found and in idle mode")
        elif esp.status == adafruit_esp32spi.WL_STOPPED: # Value = 254
            print(TAG+f"esp.status= WL_STOPPED ({esp.status})")
        else:
            print(TAG+f"esp.status= {esp.status}")
        print(TAG+"ESP Firmware version: ", esp.firmware_version)
        print(TAG+"MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))

        if scan_networks:
            for ap in esp.scan_networks():
                print("\t%-23s RSSI: %d" % (ap.ssid, ap.rssi))

        print(TAG+f"Connecting to AP: {ssid}")
        while not esp.is_connected:
            try:
                esp.connect_AP(ssid, password)
            except OSError as e:
                print("could not connect to AP, retrying: ", e)
                continue
        wifi_is_connected = esp.is_connected
        # myVars.write("wifi_is_connected", wifi_is_connected)
        print(TAG+f"Connected to: {esp.ap_info.ssid}, RSSI: {esp.ap_info.rssi}")
        print(TAG+f"My IP address is: {esp.ipv4_address}")
        esp_ipv4_address = esp.ipv4_address
        # myVars.write("esp_ipv4_address", esp.ipv4_address)
        if adafruit_lookup:
            print(TAG+"IP lookup adafruit.com: %s" % esp.pretty_ip(esp.get_host_by_name("adafruit.com")))
        if google_ping:
            print(TAG+"Ping google.com: %d ms" % esp.ping("google.com"))
                        
    except NameError as e: # this error occurrs when 'wifi' is not defined
        # was: print(TAG+"  'type(wifi)= {}'.format(type(wifi)))
        print(TAG+f"Error: {e}")    
    

    print(TAG+"IP: {} connected to: \'{}\'".format(esp_ipv4_address, ssid))


def setup():
    global esp, pool, sock, SERVER_IP, SERVER_PORT, DEST_IP, DEST_PORT, wifi_is_connected, Stop
    TAG = "setup(): "
    print(TAG + "Connecting to WiFi...")
    wifi_connect()
    
    # Explicitly check if the helper tracking flag or esp indicates connection
    if esp and esp.is_connected:
        try:
            # 👇 FIX: Get an absolute raw hardware socket directly from the ESP32 SPI handle
            # 1 = UDP (Socket type 1 in ESP32SPI firmware), 0 = TCP
            socket_num = esp.get_socket()
            if socket_num == 255:  # 255 means no available sockets left on hardware
                print(TAG + "Error: No available hardware sockets!")
                return
            
            # Use the low-level firmware command to start listening on UDP port 49000
            # This locks down the hardware port explicitly!
            if esp.start_server(DEST_PORT, socket_num, 1): # 1 specifies UDP protocol
                sock = socket_num
                if my_debug:
                    print(TAG + f"Direct hardware UDP socket #{sock} listening on port {DEST_PORT}")
            else:
                print(TAG + "Failed to open direct server socket.")
                Stop = True
                
        except Exception as e:
            print(TAG + f"Error allocating hardware socket: {e}")
            Stop = True

def main():
    global Stop, SERVER_IP, DEST_PORT, esp, sock
    TAG = "main(): "
    address = "192.168.1.77"  # X-Plane PC
    setup()
    
    if not Stop:
        try:
            if esp and esp.is_connected and sock is not None:
                print(TAG + f"Listening for direct UDP packets on port {DEST_PORT}...")
                
                while True:
                    # 👇 FIX: Read directly from the hardware socket stream bypassing connection managers
                    if esp.socket_status(sock) == 4: # Status 4 means data is waiting / active socket
                        # Read available bytes from the specific hardware socket buffer index
                        data_rcvd = esp.socket_read(sock, 512)
                        if data_rcvd:
                            if my_debug:
                                print(TAG + f"Received {len(data_rcvd)} bytes from {address}:")
                                print(data_rcvd)
                    
                    # A micro-sleep keeps the SPI lines stable without freezing the processor
                    time.sleep(0.001)
            else:
                if not esp:
                    print(TAG+f"type(esp)= {type(esp)}. Exiting...")
                    raise KeyboardInterrupt
                if not sock: 
                    print(TAG+f"type(sock)= {type(sock)}. Exiting...")
                    raise KeyboardInterrupt
                if not esp.isconected:
                    print(TAG+f"esp.isconnected= {esp.isconnected}. Exiting...")
                    raise KeyboardInterrupt
                
        except KeyboardInterrupt:
            print(TAG + "KeyboardInterrupt. Exiting...")
            if sock is not None:
                esp.socket_close(sock)
            Stop = True

        except OSError as e:
            print(TAG+f"OSError: {e}")
            if sock:
                sock.close()
            Stop = True
        finally:
            pass


def atexit_callback():
    print("inside atexit callback")
    #if pad is not None:
    #    pad.release()
    try:
        from adafruit_argv_file import write_argv  # type: ignore
        write_argv(__file__, [])
    except Exception:
        pass
    supervisor.set_next_code_file(
        "/code.py",
        sticky_on_reload=False,
        reload_on_error=True,
        working_directory="/",
    )


atexit.register(atexit_callback)

if __name__ == "__main__":
    gc.collect()
    try:
        main()
    except Exception as err:
        import traceback
        traceback.print_exception(err)
        time.sleep(5)
    finally:
        if Stop:
            Stop = False # Reset the global Stop flag
            supervisor.reload()
        else:
            while True:
                time.sleep(1)

### END OF THIS PYTHON SCRIPT ###