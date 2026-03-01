

from .sm83 import *
from .PPU import *
from .memory import *


# wowzers
class Gameboy:
    def __init__(self):
        self.loader = GBRomLoader("")
        self.memory_controller = GBMemoryController(ext_ram=False)
        self.SM83_processor = SM83(self.loader, self.memory_controller, [])
        self.PPU = GbPPU(self.memory_controller)

    def set_display(self):
        self.screen = pygame.display.set_mode(size=GB_LCD_RES)

    def execute_boot_ROM_test(self, breakpoints=[], delay=0.01):
        import colorama
        import time

        nintendo_logo = bytes.fromhex(
            "CE ED 66 66 CC 0D 00 0B 03 73 00 83 00 0C 00 0D "
            "00 08 11 1F 88 89 00 0E DC CC 6E E6 DD DD D9 99 "
            "BB BB 67 63 6E 0E EC CC DD DC 99 9F BB B9 33 3E"
        )

        # The boot ROM test expects the Nintendo logo to be present in the boot ROM
        self.memory_controller.rom.array[0x0104:0x0134] = nintendo_logo
        #
        
        self.set_display()
        self.SM83_processor.enable_boot_rom()
        self.SM83_processor.set_register('PC', 0x0000)
        all_cycles = 0
        while True:
            ccycles = 0
            
            while ccycles < 114:
                if (pc := self.SM83_processor.get_register("PC")) in breakpoints:
                    breakpoints.remove(pc)
                    print(f"Hit breakpoint at {hex(pc)}. Pausing execution.")
                    delay = float(
                        input("Enter delay between steps (in seconds, default 0.01): "))
                ins, cycles = self.SM83_processor.tick_one_ins()
                ccycles += cycles
                all_cycles += cycles
                # print(
                #      f"\nExecuted instruction: {colorama.Fore.YELLOW}{ins}{colorama.Style.RESET_ALL}")
                self.SM83_processor.handle_interrupts()
                # print(self.SM83_processor.dump_state_colorama(colorama=colorama))
                print("CLOCK CYCLES:", all_cycles)
                print(self.memory_controller.get_register('SCY'))
                #time.sleep(delay)
            self.PPU.scanline()
            #time.sleep(delay)
            self.screen.blit(self.PPU.pgdisplay, (0, 0))
            pygame.display.flip()

    def read_ROM(self, path):
        self.loader = GBRomLoader(path)
        self.loader.read()
        self.memory_controller.rom.burn_from(self.loader)


def boot_rom_test():
    gb = Gameboy()
    gb.execute_boot_ROM_test(delay=0, breakpoints=[0x95])


if __name__ == "__main__":
    boot_rom_test()
