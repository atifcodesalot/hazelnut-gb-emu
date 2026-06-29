

from .gameboy import Gameboy
from .cartridge import CartridgeReader, CARTRIDGE_TYPES
import sys



def main():
    gb = Gameboy()
    reader = CartridgeReader(sys.argv[1])
    cartridge = reader.get_cartridge()
    implemented = [0x00]
    if cartridge.type not in implemented:
        print(f"\n\nThis game ({cartridge.title}) uses {cartridge.type_name}, which isn't implemented in the emulator yet.")
        for impl in implemented:
            print("It currently only supports:", CARTRIDGE_TYPES[impl], "\n")
        
        input("IF you want to continue nevertheless, press any button.")
    gb.insert_cartridge(cartridge=cartridge)
    gb.powerup()
    
if __name__ == "__main__":
    main()