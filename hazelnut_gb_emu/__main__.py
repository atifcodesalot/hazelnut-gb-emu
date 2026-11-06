from .emu_core.gameboy import Gameboy
from .emu_core.cartridge import *
from .emu_core import logger, IMPLEMENTED_MODES
import sys
from .session import SessionController
from pypy_setup import *

RUNTIME = sys.implementation.name


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
    if RUNTIME != "pypy":
        try:
            try_pypy()
        except subprocess.CalledProcessError:
            sys.exit("Bye bye!")


    if len(sys.argv) > 2:
        if sys.argv[1] in ["--benchmark", "-b", "--profile", "-p"]:
            logger.info("Running in benchmark mode... Will run much slower than normal,\
                    but will generate a profile_stats file.")

            import threading
            import time

            def emu_target():
                return run_profiled(session.emulate, "profile_stats")

            threading.Thread(target=session.display).start()
            time.sleep(2)
            threading.Thread(target=emu_target).start()

    else:
        while True:
            session = SessionController(gbscaler=2, color=True)
            session.start()


if __name__ == "__main__":
    main()
