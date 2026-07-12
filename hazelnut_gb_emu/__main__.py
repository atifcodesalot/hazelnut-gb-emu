

from . import logging

from .gameboy import Gameboy
from .cartridge import *
from . import logger
import sys
import cProfile


def main():
    gb = Gameboy()
    reader = CartridgeReader(sys.argv[1])
    cartridge = reader.get_cartridge()
    implemented = [0x00, 0x01, 0x02]
    if cartridge.type not in implemented:
        logger.info(
            f"\n\nThis game ({cartridge.title}) uses {cartridge.type_name}, which isn't implemented in the emulator yet.")
        logger.info("The emulator currently supports cartridges that are: " + ', '.join(
            [CARTRIDGE_TYPES[impl] for impl in implemented]) + "\n")

        input("IF you want to continue nevertheless, press any button.")
    gb.memctl.configure_bank_switching(cartridge)
    logger.debug("Extended rom size: %d bytes" % gb.memctl.rom.size)
    logger.debug("Extended ram size: %d bytes" % gb.memctl.ram.size)
    load(gb=gb, cartridge=cartridge)
    gb.insert_cartridge(cartridge=cartridge)
    gb.powerup()
    save(gb=gb, cartridge=cartridge)


def save(gb: Gameboy, cartridge: Cartridge):
    if gb.memctl.ext_ram is not None and gb.memctl.ext_ram.size > 0:
        f = open(cartridge.title+'.save', "wb")
        f.write(gb.memctl.ext_ram.array)
        f.close()

def load(gb: Gameboy, cartridge: Cartridge):
    if gb.memctl.ext_ram is not None and gb.memctl.ext_ram.size > 0:
        try:
            f = open(str(cartridge.title)+'.save', "rb")
        except FileNotFoundError:
            return
        data = f.read(gb.memctl.ram.size)
        gb.memctl.ext_ram.array = bytearray(data)
        print(gb.memctl.ext_ram.array)


def benchmark():
    cProfile.run('main()', sort='time', filename='profile_stats')


if __name__ == "__main__":
    try:
        if sys.argv[2] in ["--benchmark", "-b", "--profile", "-p"]:
            logging.info("Running in benchmark mode... Will run much slower than normal,\
                but will generate a profile_stats file for analysis.")
            benchmark()
    except IndexError:
        main()
