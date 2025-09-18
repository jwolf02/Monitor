from termcolor import colored
import re
import subprocess


def __print_backtrace(x: str, elf_name: str):
    print(colored("Backtrace (most recent call last):", "red"))
    
    tokens = re.split(' |:', x)

    # token #2 always comes in like 0x123456780xabcdef01
    # so we have to split it manually
    tmp = tokens[2]
    tokens[2] = tmp[0:10]
    tokens.insert(3, tmp[10:20])

    addr2line = "xtensa-esp32-elf-addr2line"

    # tokens will look like ['Backtrace', '0x...', ... '0x...', '\r\n']
    # only the first address is one we can decode, so we skip the others
    for i in range(1, len(tokens) - 1):
        if i % 2 == 0:
            continue
        out = subprocess.check_output([addr2line, '-pfiaC', '-e', elf_name, tokens[i]])
        print(colored(out.decode("utf-8"), "red"), end='')


def monitor_plugin_filter(line: str, extra_args: dict) -> bool:
    if line.startswith("Guru Meditation Error"):
        print(colored(line, "red"))
        return True
    elif line.startswith("Backtrace"):
        elf_name = extra_args["elf"]

        if elf_name is not None:
            __print_backtrace(line, elf_name)
        else:
            print(colored(line, "red"))

        return True

    return False