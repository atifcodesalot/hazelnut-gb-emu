
from .loader import *
from .sm83 import *
import sys

import time


def test():
    loader = GBRomLoader(sys.argv[1])
    loader.read()
    loader.get_instructions()
    virtual_GB_CPU = SM83(peripherals=[])
    virtual_GB_CPU.set_register("SP", 0xFFFE)
    virtual_GB_CPU.set_register("PC", 0x0100)
    virtual_GB_CPU.execute_prog_debug(loader.instructions, delay=0.05)
        
if __name__ == "__main__":
    test()

