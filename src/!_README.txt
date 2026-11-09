2026-11-08 17h05 PT

This is a modified version ot the FruitJam OS,
in this sense that various files like: /boot.py, launcher_config.py /code.py are changed.
File /code.py now supports the use of a SNES type gamepad.
Also /apps/FruitJam_Breakout/code.py has received many changes, to make use of a SNES type gamepad.

In this update the following changes have been made:

to /boot_amimation.py changes to have the script read (better) the file /launcher_config.json,
so that it "knows" to what peripheral the audio must go: speaker or headphone. 
I set the /launcher_config.json "audio_output" to "speaker".

In file: /apps/Fruit_jan_Audio_Test/code.py I made several changes:
  new functions: ck_stop_button(), to read if button1 is pressed;
                 blink_neopixels(LED_NR: int), that will be called from the main loop when the gamepad START button or the board's button1 
				 is pressed. 
				 
				 flush_gamepad_events(timeout=0.2) to flush the gamepad events at the start of the script,
				 to not act on gamepad button presses when in the FruitJam OS main menu.
				 
				 ck_keys()  pass. A dummy function in case for future use.
				 
	Note that Google AI helped me to make more perfect the audio tones created. They were too "harsh" before.
	
	
	In the top of the script, commented-out "import neopixel"
	because we use the neopixels function in adafruit_fruitjam.peripherals.Peripherals module.
	This has the following implications:
	- creation of a "pixels" object no longer needed
	- instead I started to use: fruitjam = Peripherals()
	     and for example:
   	     fruitjam.neopixels.brightness = 0.1
   	     and for the neopixel commands, for example:
	     fruitjam.neopixels[LED_NR] = GREEN  where GRFEEN = (0, 255, 0) " in case we want to control only one neopixel 
	     or: fruitjam.neopixels.fill(GREEN) # in case we want to control all five neopixels at once
	  
	     In the main loop (while True: ) added a call to the new function blink_neopixels:
		 - in case to blink led nr 4: blink_neopixels(4) 
		 - in case to blink all five leds: blink_neopixels[BLINK_ALL_NEOPIXELS] where BLINK_ALL_NEOPIXELS is defined as 100 (just a large value
		   to distinct from 0...4)
		   
		   

	  