
from .emu_core.cartridge import *
from .emu_core import logger
import sys
from .session import SessionController
from pypy_setup import *
from .emu_core import __version__

RUNTIME = sys.implementation.name


COLOR_FLAGS = {"--color", "-c", "--gbc", "--cgb"}
PROFILE_FLAGS = {"--benchmark", "-b", "--profile", "-p"}
SCALE_FLAGS = {"--scale", "-s", "--size"}


SCALE = 2


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
        session = SessionController(gbscaler=SCALE, color=color)
        session.start()


def mainloop_profile(color):
    logger.info("Running in benchmark mode... Will run much slower than normal,\
                        but will generate a profile_stats file.")

    session = SessionController(gbscaler=SCALE, color=color)

    import threading
    import time

    def emu_target():
        session = SessionController(gbscaler=SCALE, color=False)
        return run_profiled(session.emulate, "profile_stats")

    threading.Thread(target=session.display).start()
    time.sleep(2)
    threading.Thread(target=emu_target).start()


def main():
    if RUNTIME != "pypy":
        try:
            try_pypy(*sys.argv[1:])
        except subprocess.CalledProcessError:
            logger.info("Shutting down.")
            sys.exit("Bye bye!")

    argset = set(sys.argv)
    color_flag = any(argset.intersection(COLOR_FLAGS))
    profile_flag = any(argset.intersection(PROFILE_FLAGS))
    scale_flag = any(argset.intersection(SCALE_FLAGS))
    
    if scale_flag:
        flag = argset.intersection(SCALE_FLAGS).pop()
        flagpos = sys.argv.index(flag)
        try:
            scalenum = sys.argv[flagpos + 1].strip()
        except IndexError:
            logger.error(f"a scale number is needed after {flag}")
            sys.exit()
            
        if not scalenum.isnumeric():
            raise ValueError("Scale must be a number and an integer")
        global SCALE
        SCALE = int(scalenum)
        if SCALE > 8:
            logger.error(f"scale number {SCALE} is too big!")
            sys.exit()

    logger.info(f"Welcome to Hazelnut GB Emulator Version {__version__}")
    logger.info("Running on %s" % RUNTIME)
    logger.info(
        "Emulator mode: CGB" if color_flag else "Emulator mode: DMG"
    )
    logger.info(
        f"Scale relative to the original: x{SCALE} {'(DEFAULT)' if SCALE == 2 else ''}"
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
