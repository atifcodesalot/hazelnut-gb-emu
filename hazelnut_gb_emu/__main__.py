

from .gameboy import Gameboy
from .cartridge import CartridgeReader, CARTRIDGE_TYPES
from . import logger
import sys


def main():
    gb = Gameboy()
    reader = CartridgeReader(sys.argv[1])
    cartridge = reader.get_cartridge()
    implemented = [0x00, 0x01]
    if cartridge.type not in implemented:
        print(
            f"\n\nThis game ({cartridge.title}) uses {cartridge.type_name}, which isn't implemented in the emulator yet.")
        print("It currently supports:", ' and '.join([CARTRIDGE_TYPES[impl] for impl in implemented]), "\n")
            

        input("IF you want to continue nevertheless, press any button.")
    gb.memory_controller.configure_bank_switching(cartridge)
    logger.debug("Extended rom size: %d bytes" % gb.memory_controller.rom.size)
    gb.insert_cartridge(cartridge=cartridge)
    gb.powerup()


if __name__ == "__main__":
    main()
