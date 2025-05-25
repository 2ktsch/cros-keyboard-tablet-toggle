#!/usr/bin/python

import struct
import time
import sys
import os
from subprocess import check_output

max_attempts = 10

def detect_tablet_mode_switch():
    libinput_devices_output = check_output(["libinput", "list-devices"])
    lines = libinput_devices_output.split(b'\n')
    found = False
    for l in lines:
        if l.startswith(b'Device:') and b'Tablet Mode Switch' in l:
            found = True
        if found and l.startswith(b'Kernel:'):
            return '/dev/' + l.split(b' /dev/')[1].decode('utf-8')
    else:
        return None


def find_normal_keymaps():
    # choosing to run this every time instead of caching the list just in case the user adds or removes keymaps
    return list(filter(lambda x: (x.endswith('.nope') or x.endswith('.conf')) and x not in ['off.nope', 'off.conf'], os.listdir("/etc/keyd")))


def batch_extension_switch(path, files, current, desired):
    for f in files:
        if f.endswith(current):
            os.rename(path+f, path+f.replace(current,desired))


# disable the keyboard-blocking map; this script usually runs at startup so this ensures we have a working keyboard
if 'off.conf' in os.listdir("/etc/keyd"):
    os.rename('/etc/keyd/off.conf', '/etc/keyd/off.nope')
    batch_extension_switch('/etc/keyd/', find_normal_keymaps(), '.nope', '.conf')
    os.system("keyd reload")

event_format = 'llHHI'
event_size = struct.calcsize(event_format)

def safe_toggle(enabled):
    # This is a somewhat naïve attempt at preventing conflicting actions happening too fast
    attempts = 0
    while True:
        if attempts > max_attempts:
            # Lazily assuming the lock file is left over from a crash and not a previous event firing because it shouldn't take that long...
            os.remove("/etc/keyd/gimmeasec.lock")
        if "gimmeasec.lock" not in os.listdir("/etc/keyd"):
            os.mknod("/etc/keyd/gimmeasec.lock")
            (kbd_on if enabled else kbd_off)()
            os.remove("/etc/keyd/gimmeasec.lock")
            break
        else:
            attempts += 1
            time.sleep(1)


def kbd_on():
    os.rename("/etc/keyd/off.conf", "/etc/keyd/off.nope")
    batch_extension_switch('/etc/keyd/', find_normal_keymaps(), '.nope', '.conf')
    os.system("keyd reload")


def kbd_off():
    os.rename("/etc/keyd/off.nope", "/etc/keyd/off.conf")
    batch_extension_switch('/etc/keyd/', find_normal_keymaps(), '.conf', '.nope')
    os.system("keyd reload")


def run():
    kernel_device_path = detect_tablet_mode_switch()
    if kernel_device_path is None:
        print("Tablet Mode Switch not found :(")
        return -1
        
    print("Found Tablet Mode Switch at", kernel_device_path)

    event_stream = open(kernel_device_path, "rb")
    event = event_stream.read(event_size)
    while event:
        (s, us, type, code, value) = struct.unpack(event_format, event)
        if type == 5 and code == 1:
            if value == 1:
                print("Tablet mode, disabling keyboard")
                safe_toggle(False)
            else:
                print("Laptop mode, enabling keyboard")
                safe_toggle(True)
        event = event_stream.read(event_size)

    event_stream.close()


if __name__ == '__main__':
    run()
