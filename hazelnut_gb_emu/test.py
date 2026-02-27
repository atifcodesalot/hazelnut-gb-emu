
from .loader import *
from .sm83 import *
import sys

import time


def test():
    loader = GBRomLoader(sys.argv[1])
    loader.read()
    mem_ctl = GBMemoryController()
    virtual_GB_CPU = SM83(ROMloader=loader, memory=mem_ctl, peripherals=[])
    mem_ctl.rom.burn_from(loader)
    virtual_GB_CPU.set_register("SP", 0xFFFE)
    virtual_GB_CPU.set_register("PC", 0x0)
    virtual_GB_CPU.start_debug_mode(delay=0.0001, breakpoints=[0x30])
        
if __name__ == "__main__":
    test()

