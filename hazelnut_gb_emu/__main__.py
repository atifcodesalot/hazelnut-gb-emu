

from .gameboy import Gameboy, SessionController
from .cartridge import *
from . import logger
import sys
import cProfile
import threading
import time
from tkinter import filedialog, colorchooser


IMPLEMENTED = [0x00, 0x01, 0x02, 0x3, 0x11, 0x12, 0x13]


def get_file():
    filetypes = [("Gameboy files", "*.gb .GB"), ("ROM files", "*.rom"),
                 ("Binary files,", "*.bin")]
    title = "Choose a ROM file"
    dir_ = "."
    
    return filedialog.askopenfile(
        mode="rb",
        filetypes=filetypes,
        title=title,
        initialdir=dir_)


def init():
    gb = Gameboy()
    file = get_file()
    if file is None:
        sys.exit("Bye bye!")
    reader = CartridgeReader(file)
    cartridge = reader.get_cartridge()
    return gb, cartridge


def run_profiled(target, filename):
    profiler = cProfile.Profile()

    try:
        profiler.enable()
        target()
    finally:
        profiler.disable()
        profiler.dump_stats(filename)


def main():
    gb, cart = init()
    controller = SessionController(gameboy=gb, cartridge=cart)
    controller.check_implementations(
        cartridge_types=CARTRIDGE_TYPES, implemented=IMPLEMENTED)
    try:
        if sys.argv[1] in ["--benchmark", "-b", "--profile", "-p"]:
            logger.info("Running in benchmark mode... Will run much slower than normal,\
                    but will generate a profile_stats file.")

            def emu_target(): return run_profiled(
                controller.emulate,
                "profile_stats"
            )

            threading.Thread(target=controller.display).start()
            time.sleep(2)
            threading.Thread(target=emu_target).start()

    except IndexError:
        controller.main()


if __name__ == "__main__":
    main()
