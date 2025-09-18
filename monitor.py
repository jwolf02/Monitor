#!/usr/bin/python3

import argparse
import serial
import sys
from queue import Queue
from time import sleep
from termcolor import colored
import tty
import threading
import termios
import fcntl
import os
import importlib.util
import sys
from pathlib import Path


BACKSPACE = 127
ENTER = ord('\n')
TABULATOR = ord('\t')
ESC = 27

PLUGIN_FILTER_NAME = "monitor_plugin_filter"


def load_function_if_exists(filepath: str, funcname: str):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Plugin file '{filepath}' does not exist")

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)

    return getattr(module, funcname, None)


def load_all_plugin_filters(plugins: list[str]) -> list:
    filters = []

    for plugin in plugins:
        func = load_function_if_exists(plugin, PLUGIN_FILTER_NAME)

        if not func:
            raise Exception(f"Plugin '{plugin}' dones not contain '{PLUGIN_FILTER_NAME}'")
        
        filters.append(func)

    return filters


def parse_unknown_args(unknown: list[str]) -> dict:
    extra_args = {}

    for arg in unknown:
        if arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            extra_args[key] = value

    return extra_args


def read_serial(ser: serial.Serial, queue: Queue):
    data = ""
    while True:
        data = data + ser.read_all().decode("utf-8", errors="replace")

        nl = data.find('\n')
        if nl >= 0:
            line = data[:nl]

            line = line.replace("\r\n", "\n")
            line = line.replace("\r", "\n")

            queue.put(line)

            data = data[nl + 1:]

        sleep(0.01)


def run_interactive(ser: serial.Serial, dumpfile, plugin_filters, extra_args) -> int:
    queue = Queue()

    thread = threading.Thread(target=read_serial, args=(ser, queue))
    thread.daemon = True
    thread.start()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

    try:
        tty.setcbreak(sys.stdin)

        buf = []
        esc = False
        while True:
            c = sys.stdin.buffer.read(1)
            if c:
                if ord(c) == BACKSPACE and len(buf) >= 1:
                    buf.pop(-1)
                    print("\b \b", end='', flush=True)
                elif ord(c) == ENTER:
                    buf.append(b'\n')
                    ser.write(bytes(b''.join(buf)))
                    buf = []
                elif str(b''.join([c]), "utf-8").isprintable():
                    buf.append(c)

            # delete prompt
            print("\r\033[2K", end="", flush=True)

            if  queue.empty() == False:
                line = queue.get_nowait()

                if dumpfile is not None:
                    dumpfile.write(line)

                accepted = False
                for pf in plugin_filters:
                    accepted = pf(line, extra_args)
                    if accepted:
                        break

                if accepted == False:
                    print(line)

            # reprint command
            print("\r\033[2K>", str(b''.join(buf), "utf-8"), end='', flush=True)
            sleep(0.01)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return 0


def run_noninteractive(ser: serial.Serial, dumpfile, plugin_filters, extra_args) -> int:
    data = ""
    while True:
        data = data + ser.read_all().decode("utf-8", errors="replace")

        nl = data.find('\n')
        if nl >= 0:
            line = data[:nl]

            line = line.replace("\r\n", "\n")
            line = line.replace("\r", "\n")

            if dumpfile is not None:
                dumpfile.write(line)

            accepted = False
            for pf in plugin_filters:
                accepted = pf(line, extra_args)
                if accepted:
                    break

            if accepted == False:
                print(line)

            data = data[nl + 1:]

        sleep(0.01)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactive Serial Monitor"
    )
    parser.add_argument(
        "--port", "-p",
        help="Serial Port, e.g. COM3 or /dev/ttyUSB0",
        required=True
    )
    parser.add_argument(
        "--baudrate", "-b",
        type=int,
        default=115200,
        help="Baudrate (Default: 115200)"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="Dumpfile Name"
    )
    parser.add_argument(
        "--elf", "-e",
        type=str,
        help="ELF Filename"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Activate Interactive Mode"
    )
    parser.add_argument(
        "--plugins",
        nargs="+",
        help="Additionaly Filter Plugins (Python Files that contain a plugin_filter_* Function)"
    )

    args, unknown = parser.parse_known_args()

    port = args.port
    baudrate = args.baudrate
    dumpfilename = args.file
    interactive = args.interactive
    elf_name = args.elf
    plugin_filters = load_all_plugin_filters(args.plugins) if args.plugins is not None else []
    extra_args = parse_unknown_args(unknown)

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baudrate
    ser.timeout = 1
    ser.dtr = 0
    ser.rts = 0
    try:
        ser.open()
    except:
        print(f"Failed to open serial port '{port}'")
        return -1

    dumpfile = None
    try:
        if dumpfilename is not None:
            dumpfile = open(dumpfilename, "w")
            dumpfile.truncate(0)
    except:
        print(f"Failed to open dumpfile '{dumpfilename}'")
        return -1

    try:
        if interactive:
            return run_interactive(ser, dumpfile, plugin_filters, extra_args)
        else:
            return run_noninteractive(ser, dumpfile, plugin_filters, extra_args)
    except Exception as ex:
        print(f"Terminated: {ex}")
        return -1


if __name__ == "__main__":
    ret = main()
    exit(ret)
