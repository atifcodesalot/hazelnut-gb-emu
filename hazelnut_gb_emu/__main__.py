

from .gameboy import Gameboy, SessionController
from .cartridge import *
from . import logger
import sys
import cProfile
import threading
import os


IMPLEMENTED = [0x00, 0x01, 0x02, 0x3, 0x11, 0x12, 0x13]




def init():
    gb = Gameboy()
    reader = CartridgeReader(sys.argv[1])
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
    controller.check_implementations(cartridge_types=CARTRIDGE_TYPES, implemented=IMPLEMENTED)
    controller.try_loading_save()
    try:
        if sys.argv[2] in ["--benchmark", "-b", "--profile", "-p"]:
            logger.info("Running in benchmark mode... Will run much slower than normal,\
                    but will generate a profile_stats file.")
            
            emu_target = lambda: run_profiled(
            controller.emulate,
            "profile_stats"
            )

            threading.Thread(target=emu_target).start()
            threading.Thread(target=controller.display).start()

        else:
            controller.play()
    except IndexError:
        controller.main()
        


if __name__ == "__main__":
    main()
