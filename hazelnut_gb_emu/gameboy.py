

from .sm83 import *
from .PPU import *
from .memory import *
import cProfile
import time
import colorama
from .cartridge import Cartridge, CartridgeReader
from .aux import BO


BOOT_SEQ = open("dmg_boot.bin")


class Gameboy:
    CPU_DELAY = 0

    keys_inputs = {
        pygame.K_RIGHT: 0,
        pygame.K_LEFT: 1,
        pygame.K_UP: 2,
        pygame.K_DOWN: 3,

        pygame.K_a: 4,       # A
        pygame.K_b: 5,       # B
        pygame.K_s: 6,       # Select
        pygame.K_RETURN: 7,  # Start
    }

    def __init__(self):
        self.loader = GBRomLoader
        self.input_state = 255
        self.memory_controller = GBMemoryController(
            self, ext_ram=False)
        self.SM83_processor = SM83(self.loader, self.memory_controller, [])
        self.PPU = GbPPU(self.memory_controller)
        self.cycles = 0
        self.TIMA_hertz = [256*4, 16, 64, 256]
        self.DMA = False

    @classmethod
    def set_delay(cls, delay):
        cls.CPU_DELAY = delay

    def turn_on_LCD(self):
        self.memory_controller[0xFF40] = 0x91

    def set_display(self):
        gw, gh = GB_LCD_RES
        self.screen = pygame.display.set_mode(size=(gw + 20, gh + 200))

    def CPU_burst(self, clock_cycles):
        cycles_passed = 0
        while cycles_passed <= clock_cycles:
            ins, cycles = self.SM83_processor.tick_one_ins()
            self.cycles += cycles
            self.handle_TIMA()
            self.inc_DIV()

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

    def start_DMA(self):
        # logger.debug("starting DMA...")
        m = self.memory_controller
        self.DMA = True
        source = (m.io_registers[0xFF46].value) * 0x100
        # copy 160 bytes to OAM
        for i in range(0xA0):
            m.OAM[i] = m.read_at(source + i)
        # logger.debug("ending DMA...")
        # logger.debug(f"OAM:{self.memory_controller.OAM}")

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
        # recall because CPU burst may change the context
        self.PPU.drawing_mode(self.PPU.get_context())
        self.CPU_burst(172)
        self.PPU.HBLANK_mode()
        self.CPU_burst(204)

        if ly == GB_LCD_RES[1] - 1:  # if just finished the last visible scanline
            pygame.display.flip() # update real display
            self.PPU.enter_VBLANK()

        self.PPU.inc_ly()
        self.PPU.handle_LY_compare()
        self.handle_inputs()

    def execute_boot_ROM_test(self, breakpoints=[]):
        self.load_nintendo_logo()
        self.set_display()
        self.SM83_processor.enable_boot_rom()
        self.SM83_processor.set_register('PC', 0x0000)
        while True:
            self.tick_PPU_modes_basis()
            self.screen.blit(self.PPU.pgdisplay, (0, 0))
            pygame.display.flip()

    def handle_inputs(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit()
            elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                is_pressed = event.type == pygame.KEYDOWN
                if event.key not in self.keys_inputs:
                    continue
                if is_pressed:
                    self.input_state = BO.res_nth_bit(
                        self.input_state,  self.keys_inputs[event.key])
                else:
                    self.input_state = BO.set_nth_bit(
                        self.input_state,  self.keys_inputs[event.key])
        self.memory_controller.input_state = self.input_state

    def powerup(self):
        self.set_display()
        self.SM83_processor.set_register('PC', 0x0)
        self.memory_controller.boot_enabled = True
        while True:
            self.tick_PPU_modes_basis()
            self.screen.blit(self.PPU.pgdisplay, (10, 10))

    def insert_cartridge(self, cartridge: Cartridge):
        self.memory_controller.rom.burn_from(cartridge=cartridge)

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



def test():
    gb = Gameboy()
    reader = CartridgeReader(sys.argv[1])
    cartridge = reader.get_cartridge()
    gb.insert_cartridge(cartridge=cartridge)
    gb.powerup()


if __name__ == "__main__":
    import sys
    # test()
    cProfile.run("test()", "benchmark_profile.prof")
