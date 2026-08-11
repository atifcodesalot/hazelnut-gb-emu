

from .emu_core.gameboy import Gameboy, SessionController
from .emu_core.cartridge import *
from .emu_core import logger
import sys
import cProfile
import threading
import time
import gc
from pypy_setup import *


from tkinter import filedialog, Tk



INTERPRETER = sys.implementation.name

IMPLEMENTED_MODES = [0x00, 0x01, 0x02, 0x3, 0x5, 0x6, 0x11, 0x12, 0x13]


def get_file():
    filetypes = [("Gameboy files", "*.gb .GB"), ("ROM files", "*.rom"),
                 ("Binary files,", "*.bin")]
    title = "Choose a ROM file"
    dir_ = "."

    root = Tk()
    root.withdraw()

    try:
        return filedialog.askopenfile(
            mode="rb",
            filetypes=filetypes,
            title=title,
            initialdir=dir_)
    finally:
        # make sure to destroy and kill,
        # the tk object in this thread
        root.destroy()
        del root
        gc.collect()


def init_gb_objects():
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
    if INTERPRETER != "pypy":
        try_pypy()
    gb, cart = init_gb_objects()
    controller = SessionController(gameboy=gb, cartridge=cart)
    controller.check_implementations(
        cartridge_types=CARTRIDGE_TYPES, implemented=IMPLEMENTED_MODES)
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
