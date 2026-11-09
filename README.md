# FruitJam-OS-Gamepad

A refactored (not a cloned) version of **Fruit Jam OS** ("A mini credit card sized computer!") and its bundled applications for the **Adafruit Fruit Jam (RP2350B)** running **CircuitPython 10.2.1**.

* **Board:** [Adafruit Fruit Jam Mini RP2350 Computer](https://www.adafruit.com/product/6200)
* **Controller:** [Adafruit USB Game Controller with SNES-like Layout (PID 6285)](https://www.adafruit.com/product/6285) / DragonRise (`081f:e401`) USB SNES-style gamepad connected via the on-board CH334F USB host hub.


This repository centralizes USB HID gamepad handling into a shared library (`/lib/fj_gamepad.py`), resolves USB host contention and hard-reset issues during app transitions, and adds full SNES-style controller support across the desktop launcher and apps—including mouse-emulated cursor control for **Larsio Paint Music**.

---

## Hardware & Firmware Requirements

* **Board:** Adafruit Fruit Jam (RP2350B)
* **Firmware:** CircuitPython `10.2.1` (`2026-05-13; Adafruit Fruit Jam with rp2350b`)
  > **Note:** Tested specifically on CircuitPython `10.2.1` to prevent memory and display framebuffer allocation errors during display resolution transitions (`720x400` ↔ `320x240`). See: CircuitPython version of: 2026-05-13T00:04:55.000Z, 1.7 MB, [adafruit-circuitpython-adafruit_fruit_jam-en_US-10.2.1.uf2](https://adafruit-circuit-python.s3.amazonaws.com/index.html?prefix=bin/adafruit_fruit_jam/en_US/)
* **Controller:** USB SNES-style gamepad (tested with DragonRise / `081f:e401` USB SNES clone controllers via the on-board CH334F USB hub)

---

## Key Improvements & Architecture

### 1. Centralized Gamepad Driver ([/lib/fj_gamepad.py](https://github.com/PaulskPt/FruitJam-OS-Gamepad/blob/main/src/lib/fj_gamepad.py))
Instead of duplicating raw HID polling loops and button maps in every script, all applications import `GamepadManager` and standardized button tuples from `/lib/fj_gamepad.py`:
* **Hardware Clone Alignment:** Maps both standard `relic_usb_host_gamepad` constants and physical clone HID button indexes (`HW_UP = 4`, `HW_DOWN = 5`, `HW_LEFT = 6`, `HW_RIGHT = 7`, `HW_START = 8`, `HW_SELECT = 9`, `HW_L1 = 11`, `HW_R1 = 12`).
* **Clean Button Separation:** Isolates directional D-Pad controls, face buttons (`A`, `B`, `X`, `Y`), shoulder buttons (`L1`, `R1`), `SELECT`, and `START` so face buttons never collide with directional movement.
* **Input Drain & Debounce:** `wait_for_release()` drains lingering USB HID packets after launcher/app transitions so pressing **A** in the menu never accidentally triggers **SELECT** inside a newly launched app.
* **Startup REPL Cheat Sheet:** `print_controls()` automatically prints a formatted button guide to the serial REPL whenever a gamepad is detected.

### 2. Clean Soft-Reload Transitions (`supervisor.reload()`)
* Replaces abrupt `microcontroller.reset()` calls with clean USB device release (`pad.release()`), `supervisor.set_next_code_file(...)`, and `supervisor.reload()`.
* Keeps the `CIRCUITPY` USB mass-storage drive and serial REPL connection mounted continuously across app launches and exits—eliminating serial disconnects in VS Code / Mu Editor and preventing host OS drive-repair popups.

### 3. Unified Audio & Config Routing (`LauncherConfig`)
* Reads `audio_output` (`"speaker"` or `"headphone"`), `use_gamepad`, `use_mouse`, `use_keyboard`, and `my_debug` consistently from `launcher_conf.json`.

---

## Repository Structure

```text
CIRCUITPY/
├── boot.py
├── boot_animation.py
├── code.py                         # Fruit Jam OS Launcher (main menu)
├── launcher_conf.json              # System & peripheral configuration
|── launcher.config.py
├── settings.toml                   # Wi-Fi credentials and other settings
├── lib/
│   ├── fj_gamepad.py               # Shared GamepadManager & SNES button definitions
│   └── gamepad_bridge.py           # Launcher-to-app gamepad presence handoff
|   |__ more (adafruit) libraries
└── apps/
    ├── FruitJam_Breakout/
    │   └── code.py                 # Breakout arcade game
    ├── Fruit_Jam_Audio_Test/
    │   └── code.py                 # TLV320 DAC sine-wave & arpeggio test utility
    └── Larsio_Paint_Music/
        ├── code.py                 # App entry point & soft-reload teardown
        ├── input_handler.py        # SNES gamepad cursor emulation, debounce & shortcuts
        ├── ui_manager.py           # UI loop, undo last note & BPM adjustment hooks
        └── sound_manager.py        # Resilient WAV sample loader & speaker routing
```

---

## SNES Gamepad Controls Reference

### Fruit Jam OS Launcher (`/code.py`)

| Button | Action |
| :--- | :--- |
| **D-Pad** | Navigate app grid and page arrows |
| **L1 / R1** | Switch to previous / next page |
| **A** | Launch selected application |
| **X** | Open selected application in code editor |

### FruitJam Breakout (`/apps/FruitJam_Breakout/code.py`)

| Button | Action |
| :--- | :--- |
| **D-Pad Left / Right** | Move paddle |
| **L1 / R1** | Move paddle |
| **SELECT** | Start game / Launch ball |
| **START** | Exit game and return to launcher |

### Fruit Jam Audio Test (`/apps/Fruit_Jam_Audio_Test/code.py`)

| Button | Action |
| :--- | :--- |
| **START** | Fade out audio and return to launcher |

### Larsio Paint Music (`/apps/Larsio_Paint_Music/`)
Features full SNES gamepad cursor emulation with **220 ms click debouncing**, **1-pixel precision movement**, **vertical screen wrap-around** (top menu ↔ bottom transport bar), and **graceful missing-WAV fallback**:

| Button | Action |
| :--- | :--- |
| **D-Pad** | Move cursor (wraps vertically between top and bottom rows) |
| **L1 / R1** | Decrease / Increase tempo by **5 BPM** |
| **A / SELECT** | Place note on staff or click top/bottom menu button |
| **B** | Erase note directly under cursor |
| **X** | Undo / Delete the most recently placed note |
| **Y** | Cycle through all 6 instruments (Lars, Heart, Drum, Meatball, Star, Bot) |
| **START** | Exit application and return to launcher |

---

## Installation

1. Flash **CircuitPython 10.2.1** onto your **Adafruit Fruit Jam (RP2350B)**.
2. Copy `/lib/fj_gamepad.py` and `/lib/gamepad_bridge.py` (along with the required Adafruit Fruit Jam libraries) into `CIRCUITPY/lib/`.
3. Copy `/code.py` and the refactored `/apps/` folders onto `CIRCUITPY/`.
4. Ensure `launcher_conf.json` has `"use_gamepad": true` and `"use_mouse": false` when using a USB SNES gamepad (prevents `adafruit_usb_host_mouse` from claiming the gamepad's HID report interface). Set "audio_output" to "speaker" if you want audio output to an external speaker. In that case don't forget to connect a jumper wire between the pins A1 and GND on the 20-pin connector.

---

## Credits & License

* Original **Fruit Jam OS** and **Larsio Paint Music** by Tim Cocks, John Park, and Adafruit Industries.
* Gamepad architecture refactoring, hardware clone alignment, soft-reload transitions, and Larsio Paint Music gamepad integration by **Paulus Schulinck ([@PaulskPt](https://github.com))** with assistance from **Gemini** (Google AI).
* Licensed under the **MIT License**.
