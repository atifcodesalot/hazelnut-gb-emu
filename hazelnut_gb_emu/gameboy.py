

from .sm83 import *
from .PPU import *
from .memory import *
import cProfile
import time
import colorama

# wowzers
class Gameboy:
    CPU_DELAY = 0
    
    def __init__(self):
        self.loader = GBRomLoader("")
        self.memory_controller = GBMemoryController(ext_ram=False)
        self.SM83_processor = SM83(self.loader, self.memory_controller, [])
        self.PPU = GbPPU(self.memory_controller)
        self.cycles = 0
        self.TIMA_hertz = [256*4, 16, 64, 256]
        
    @classmethod
    def set_delay(cls, delay):
        cls.CPU_DELAY = delay

    def set_display(self):
        self.screen = pygame.display.set_mode(size=GB_LCD_RES)

    def CPU_burst(self, clock_cycles, breakpoints=[]):
        cycles_passed = 0
        while cycles_passed <= clock_cycles:
            if (pc := self.SM83_processor.get_register('PC')) in breakpoints:
                self.set_delay(float(input(f"Breakpoint reached at {pc}! Input delay in seconds: ")))
            ins, cycles = self.SM83_processor.tick_one_ins()
            
            cycles_passed += cycles

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

    def tick_PPU_modes_basis(self):
        lcdc = self.memory_controller.io_registers[0xFF40].value

        # clear the lcd if PPU is disabled
        if not BO.get_nth_bit(lcdc, 7):
            self.PPU.disable()
            self.CPU_burst(456)
            return
        
        ly = self.memory_controller.io_registers[0xFF44].value

        if self.PPU.is_VBLANK_scan(ly):
            # cpu burst then inc ly
            self.CPU_burst(456)
            self.PPU.handle_VBLANK()
            return
        
        self.PPU.OAM_scan(self.PPU.get_context())
        self.CPU_burst(80)
        self.PPU.drawing_mode(self.PPU.get_context())
        self.CPU_burst(172)
        self.PPU.HBLANK_mode()
        self.CPU_burst(204)

        if ly == GB_LCD_RES[1] - 1:  # if just finished the last visible scanline
            self.PPU.enter_VBLANK()
        
        self.PPU.inc_ly()
        self.PPU.handle_LY_compare()
        
    def load_nintendo_logo(self):
        nintendo_logo = bytes.fromhex(
            "CE ED 66 66 CC 0D 00 0B 03 73 00 83 00 0C 00 0D "
            "00 08 11 1F 88 89 00 0E DC CC 6E E6 DD DD D9 99 "
            "BB BB 67 63 6E 0E EC CC DD DC 99 9F BB B9 33 3E"
        )

        # The boot ROM test expects the Nintendo logo to be present in the boot ROM
        self.memory_controller.rom.array[0x0104:0x0134] = nintendo_logo
        #

    def execute_boot_ROM_test(self, breakpoints=[], delay=0.01):
        self.load_nintendo_logo()
        self.set_display()
        self.SM83_processor.enable_boot_rom()
        self.SM83_processor.set_register('PC', 0x0000)
        while True:
            self.tick_PPU_modes_basis()
            #ime.sleep(delay)
            self.screen.blit(self.PPU.pgdisplay, (0, 0))
            pygame.display.flip()

    def read_ROM(self, path):
        self.loader = GBRomLoader(path)
        self.loader.read()
        self.memory_controller.rom.burn_from(self.loader)

    def run_test_ROM(self, path, pc_start, debug=False, breakpoints=[]):
        with open("hazelnutlog.txt", 'w') as f:
            f.write("")
        self.read_ROM(path)
        self.memory_controller.disable_boot_rom()
        self.set_display()
        self.SM83_processor.set_register('PC', pc_start)
        self.load_nintendo_logo()
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
            self.tick_PPU_modes_basis()
            self.screen.blit(self.PPU.pgdisplay, (0, 0))
            pygame.display.flip()

    def debug_state(self, ins, colorama):
        print(
            f"\nExecuted instruction: {colorama.Fore.YELLOW}{ins}{colorama.Style.RESET_ALL}")
        print(self.SM83_processor.dump_state_colorama(colorama=colorama))

    # for doctor gameboy
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
        gb.set_delay(0.00001)
        gb.run_test_ROM(sys.argv[1], pc_start=0x0)
    except KeyboardInterrupt:
        exit("Program terminated")


if __name__ == "__main__":
    benchmark()
    # cProfile.run("benchmark()", "benchmark_profile.prof")
