

from .gameboy import Gameboy
from .cartridge import CartridgeReader
import sys



def main():
    gb = Gameboy()
    reader = CartridgeReader(sys.argv[1])
    cartridge = reader.get_cartridge()
    gb.insert_cartridge(cartridge=cartridge)
    gb.powerup()
    
if __name__ == "__main__":
    main()