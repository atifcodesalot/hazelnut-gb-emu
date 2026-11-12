from .emu_core.gameboy import Gameboy
from .emu_core.cartridge import *
from .emu_core import logger, IMPLEMENTED_MODES
import sys
from .session import SessionController
from pypy_setup import *

RUNTIME = sys.implementation.name


COLOR_FLAGS = {"--color", "-c", "--gbc", "--cgb"}
PROFILE_FLAGS = {"--benchmark", "-b", "--profile", "-p"}


def run_profiled(target, filename):
    import cProfile

    profiler = cProfile.Profile()

    try:
        profiler.enable()
        target()
    finally:
        profiler.disable()
        profiler.dump_stats(filename)


def mainloop(color):
    while True:
        session = SessionController(gbscaler=2, color=color)
        session.start()


def mainloop_profile(color):
    logger.info("Running in benchmark mode... Will run much slower than normal,\
                        but will generate a profile_stats file.")

    session = SessionController(gbscaler=2, color=color)

    import threading
    import time

    def emu_target():
        session = SessionController(gbscaler=2, color=False)
        return run_profiled(session.emulate, "profile_stats")

    threading.Thread(target=session.display).start()
    time.sleep(2)
    threading.Thread(target=emu_target).start()


def main():
    if RUNTIME != "pypy":
        try:
            try_pypy(*sys.argv[1:])
        except subprocess.CalledProcessError:
            sys.exit("Bye bye!")

    argset = set(sys.argv)
    color_flag = any(argset.intersection(COLOR_FLAGS))
    profile_flag = any(argset.intersection(PROFILE_FLAGS))

    logger.info("Welcome to Hazelnut GB Emulator vAlpha 0.1.0")
    logger.info("Running on %s" % RUNTIME)
    logger.info(
        "Emulator mode: CGB" if color_flag else "Emulator mode: DMG"
    )
    logger.info(
        "Benchmark mode: Enabled" if profile_flag else "Benchmark mode: Disabled"
    )

    if len(sys.argv) >= 2:
        if profile_flag:
            mainloop_profile(color_flag)

        else:
            mainloop(color_flag)

    else:
        mainloop(color=False)


if __name__ == "__main__":
    main()
