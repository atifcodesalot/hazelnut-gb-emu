

from .emu_core.gameboy import Gameboy
from .emu_core.cartridge import *
from .emu_core import logger, IMPLEMENTED_MODES
import sys
import gc

from .session import SessionController
from pypy_setup import *


from tkinter import filedialog, Tk



INTERPRETER = sys.implementation.name


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
    import cProfile
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
    session = SessionController(gameboy=gb, cartridge=cart)
    session.check_implementations(
        cartridge_types=CARTRIDGE_TYPES, implemented=IMPLEMENTED_MODES)
    
    if len(sys.argv) > 2:
        if sys.argv[1] in ["--benchmark", "-b", "--profile", "-p"]:
            logger.info("Running in benchmark mode... Will run much slower than normal,\
                    but will generate a profile_stats file.")
            
            import threading
            import time
            

            def emu_target(): return run_profiled(
                session.emulate,
                "profile_stats"
            )

            threading.Thread(target=session.display).start()
            time.sleep(2)
            threading.Thread(target=emu_target).start()

    else:
        session.start()
        session.consume_events()


if __name__ == "__main__":
    main()
