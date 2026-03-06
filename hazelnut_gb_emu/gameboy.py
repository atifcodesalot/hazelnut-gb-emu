

from .sm83 import *
from .PPU import *
from .memory import *
import cProfile
import time


# wowzers
class Gameboy:
    def __init__(self):
        self.loader = GBRomLoader("")
        self.memory_controller = GBMemoryController(ext_ram=False)
        self.SM83_processor = SM83(self.loader, self.memory_controller, [])
        self.PPU = GbPPU(self.memory_controller)
        self.cycles = 0
        self.TIMA_hertz = [256*4, 16, 64, 256]

    def set_display(self):
        self.screen = pygame.display.set_mode(size=GB_LCD_RES)

    def inc_DIV(self):
        if not self.cycles % 256:
            self.memory_controller.inc_byte_at(0xFF04)  # div register location

    def handle_TIMA(self):
        TAC = self.memory_controller.io_registers[0xFF07].value
        # TIMA increment disabled
        if not BO.get_nth_bit(TAC, 2):
            return
        mc = self.TIMA_hertz[TAC & 3]
        if not (self.cycles // 4) % mc:
            TIMA = self.memory_controller.io_registers[0xFF05].value
            if BO.add_full_carry(TIMA, 1):
                self.memory_controller.write_to(
                    0xFF05, self.memory_controller.io_registers[0xFF06].value)
                IF = self.memory_controller.io_registers[0xFF0F].value
                new_IF = BO.set_nth_bit(IF, 2)
                # request a timer interupt
                self.memory_controller.write_to(0xFF0F, new_IF)
            else:
                self.memory_controller.inc_byte_at(0xFF05)

    def tick_scanline_basis(self):
        inner_cycles = 0

        self.PPU.scanline()
        # cpu burst
        while inner_cycles < 456:
            ins, cycles = self.SM83_processor.tick_one_ins()
            inner_cycles += cycles
            self.cycles += cycles
        #

        for _ in range(456):
            self.inc_DIV()
            self.handle_TIMA()
            self.SM83_processor.handle_interrupts()

        self.cycles += 456

    def execute_boot_ROM_test(self, breakpoints=[], delay=0.01):
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
        while True:
            self.tick_scanline_basis()

            time.sleep(delay)
            self.screen.blit(self.PPU.pgdisplay, (0, 0))
            pygame.display.flip()

    def read_ROM(self, path):
        self.loader = GBRomLoader(path)
        self.loader.read()
        self.memory_controller.rom.burn_from(self.loader)

    def run_test_ROM(self, path, debug=False, breakpoints=[], delay=0.01):
        if debug:
            import colorama
        with open("hazelnutlog.txt", 'w') as f:
            f.write("")
        self.read_ROM(path)
        self.memory_controller.disable_boot_rom()
        self.set_display()
        self.SM83_processor.set_register('PC', 0x100)
        self.SM83_processor.set_register('SP', 0xFFFE)
        self.SM83_processor.set_register('A', 0x01)
        self.SM83_processor.set_flags(Z=1, N=0, H=1, C=1)
        self.SM83_processor.set_register('B', 0x00)
        self.SM83_processor.set_register('C', 0x13)
        self.SM83_processor.set_register('D', 0x00)
        self.SM83_processor.set_register('E', 0xD8)
        self.SM83_processor.set_register('E', 0xD8)
        self.SM83_processor.set_register('H', 0x01)
        self.SM83_processor.set_register('L', 0x4D)

        while True:
            inner_cycles = 0

            self.PPU.scanline()
            while inner_cycles < 456:
                # if (pc := self.SM83_processor.get_register('PC')) in breakpoints:
                #     import colorama
                #     debug = True
                #     delay = float(input(
                #         f"breakpoint reached at {hex(pc)}! Input delay: "))

                #self.log_pc_state("hazelnutlog.txt")
                ins, cycles = self.SM83_processor.tick_one_ins()
                inner_cycles += cycles
                self.cycles += cycles
                self.inc_DIV()
                self.handle_TIMA()
                # time.sleep(delay)
                # if debug:
                #     self.debug_state(ins, colorama)
                #     print("IE:", bin(self.memory_controller.io_registers[0xffff].value))

            
            self.cycles += 456
            self.screen.blit(self.PPU.pgdisplay, (0, 0))
            pygame.display.flip()

    def debug_state(self, ins, colorama):
        print(
            f"\nExecuted instruction: {colorama.Fore.YELLOW}{ins}{colorama.Style.RESET_ALL}")
        print(self.SM83_processor.dump_state_colorama(colorama=colorama))

    def log_pc_state(self, logfile):
        AA = self.memory_controller.read_at(
            self.SM83_processor.get_register('PC'))
        BB = self.memory_controller.read_at(
            self.SM83_processor.get_register('PC') + 1)
        CC = self.memory_controller.read_at(
            self.SM83_processor.get_register('PC') + 2)
        DD = self.memory_controller.read_at(
            self.SM83_processor.get_register('PC') + 3)
        with open(logfile, 'a') as f:
            f.write(f"A:{self.SM83_processor.get_register('A'):02X} F:{self.SM83_processor.flags_register():02X} B:{self.SM83_processor.get_register('B'):02X} C:{self.SM83_processor.get_register('C'):02X} D:{self.SM83_processor.get_register('D'):02X} E:{self.SM83_processor.get_register('E'):02X} H:{self.SM83_processor.get_register('H'):02X} L:{self.SM83_processor.get_register('L'):02X} SP:{self.SM83_processor.get_register('SP'):04X} PC:{self.SM83_processor.get_register('PC'):04X} PCMEM:{AA:02X},{BB:02X},{CC:02X},{DD:02X}\n")


def benchmark():
    import sys
    gb = Gameboy()
    try:
        gb.run_test_ROM(sys.argv[1], debug=False, delay=0.0000)
    except KeyboardInterrupt:
        exit("Program terminated")


if __name__ == "__main__":
    benchmark()
    # cProfile.run("benchmark()", "benchmark_profile.prof")
