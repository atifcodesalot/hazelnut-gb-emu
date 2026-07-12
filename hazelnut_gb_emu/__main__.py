

from .gameboy import Gameboy
from .cartridge import *
from . import logger
import sys
import cProfile
import os

IMPLEMENTED = [0x00, 0x01, 0x02, 0x3, 0x11, 0x12, 0x13]


class SessionController:
    def __init__(self, gameboy, cartridge):
        self.gameboy = gameboy
        self.cartridge = cartridge
        self.game_name = cartridge.title
        self.gameboy.memctl.configure_bank_switching(cartridge)
        logger.debug("Extended ROM size: %d bytes" %
                     self.gameboy.memctl.rom.size)
        logger.debug("External RAM size: %d bytes" %
                     len(self.gameboy.memctl.ext_ram.array))
        
        self.cart_has_battery = "BATTERY" in self.cartridge.type_name

    def check_implementations(self):
        if self.cartridge.type not in IMPLEMENTED:
            logger.info(
                f"\n\nThis game ({self.game_name}) uses {self.cartridge.type_name}, which isn't implemented in the emulator yet.")
            logger.info("The emulator currently supports cartridges that are: " + ', '.join(
                [CARTRIDGE_TYPES[impl] for impl in IMPLEMENTED]) + "\n")

            input("IF you want to continue nevertheless, press any button.")

    def play(self):
        self.gameboy.insert_cartridge(self.cartridge)
        self.gameboy.powerup()

    def save(self):
        ext = self.gameboy.memctl.ext_ram
        if  ext is not None \
                and ext > 0 and self.cart_has_battery:

            f = open(self.cartridge.title+'.save', "wb")
            f.write(self.gameboy.memctl.ext_ram.array)
            f.close()
            logger.info(f"Save file generated for {self.game_name} at {os.getcwd()}.")

    def try_loading_save(self):
        ext = self.gameboy.memctl.ext_ram
        if ext is not None \
                and ext.size > 0 and self.cart_has_battery:
            try:
                f = open(str(self.cartridge.title)+'.save', "rb")
            except FileNotFoundError:
                logger.info(f"No save file found for {self.game_name}")
                return
            data = f.read(ext.size)
            ext.array[:len(data)] = bytearray(data)
            logger.info(f"Save file {f.name} loaded for {self.game_name}")


def init():
    gb = Gameboy()
    reader = CartridgeReader(sys.argv[1])
    cartridge = reader.get_cartridge()
    return gb, cartridge


def main():
    gb, cart = init()
    controller = SessionController(gameboy=gb, cartridge=cart)
    controller.check_implementations()
    controller.try_loading_save()
    try:
        if sys.argv[2] in ["--benchmark", "-b", "--profile", "-p"]:
            logger.info("Running in benchmark mode... Will run much slower than normal,\
                    but will generate a profile_stats file.")
            cProfile.run('controller.play()', sort='time',
                         filename='profile_stats')

        else:
            controller.play()
    except IndexError:
        controller.play()
    controller.save()


if __name__ == "__main__":
    main()
