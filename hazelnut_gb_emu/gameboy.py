

from .sm83 import *
from .PPU import *
from .memory import *
import cProfile
import time
import colorama
from .cartridge import Cartridge, CartridgeReader
from .aux import BO


pyclock = pygame.time.Clock()


class Gameboy:
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
        self.memctl = GBMemoryController(
            self, ext_ram=False)
        self.SM83_processor = SM83(self.loader, self.memctl, [])
        self.PPU = GbPPU(self.memctl)
        self.cycles = 0
        self.TIMA_hertz = [256*4, 16, 64, 256]
        self.DMA = False

        self.debug = False

    def turn_on_LCD(self):
        self.memctl[0xFF40] = 0x91

    def set_display(self):
        gw, gh = GB_LCD_RES
        self.screen = pygame.display.set_mode(size=(gw + 20, gh + 200))

    def awake(self):
        self.SM83_processor.HALT = False

    def handle_cpu_halt(self):
        if self.interrupt_pending():
            self.awake()
            return True

    def tick_timers(self, clock_cycles):
        TAC = self.memctl.io_registers[0xFF07].value
        TIMA_en = (TAC >> 2) & 1
        if TIMA_en:
            for _ in range(clock_cycles):
                self.cycles += 1
                self.handle_TIMA()
        else:
            self.cycles += clock_cycles
        self.add_DIV(clock_cycles)

    def CPU_burst(self, clock_cycles):
        if self.SM83_processor.HALT:
            if not self.handle_cpu_halt():
                self.tick_timers(clock_cycles)
                return
        cycles_passed = 0
        while cycles_passed < clock_cycles:
            ins, ins_cycles = self.SM83_processor.tick_one_ins()
            self.tick_timers(ins_cycles)
            # if self.debug:
            #     self.debug_state(ins, colorama=colorama)
            #     if self.memctl.io_registers[0xFF0F].value != 0:
            #         print(self.memctl.io_registers[0xFF0F])
            #     print(self.memctl.io_registers[0xFF05].value)
            if self.SM83_processor.HALT:
                self.tick_timers(clock_cycles - cycles_passed)
                break

            cycles_passed += ins_cycles

    def add_DIV(self, elapsed):
        elapsed >>= 8
        div = self.memctl.io_registers[0xFF04].value  # div register location
        self.memctl.io_registers[0xFF04].value = (div + elapsed) & 0xff

    def handle_TIMA(self):
        TAC = self.memctl.io_registers[0xFF07].value
        mc = self.TIMA_hertz[TAC & 0b11]
        if not (self.cycles) % mc:
            TIMA = self.memctl.io_registers[0xFF05].value
            if BO.add_full_carry(TIMA, 1):
                TMA = self.memctl.io_registers[0xFF06].value
                # wrap to TMA
                self.memctl.io_registers[0xFF05].value = TMA
                IF = self.memctl.io_registers[0xFF0F].value
                new_IF = BO.set_nth_bit(IF, 2)
                # request a timer interupt
                self.memctl.io_registers[0xFF0F].value = new_IF
            else:
                self.memctl.inc_byte_at(0xFF05)

    def start_DMA(self):
        # logger.debug("starting DMA...")
        m = self.memctl
        self.DMA = True
        source = (m.io_registers[0xFF46].value) * 0x100
        # copy 160 bytes to OAM
        for i in range(0xA0):
            m.OAM[i] = m.read_at(source + i)
        # logger.debug("ending DMA...")
        # logger.debug(f"OAM:{self.memctl.OAM}")

    def scanline_PPU_modes(self):
        self.PPU.OAM_scan(self.PPU.get_context())
        self.CPU_burst(80)
        # recall because CPU burst may change the context
        self.PPU.drawing_mode(self.PPU.get_context())
        self.CPU_burst(172)
        self.PPU.HBLANK_mode()
        self.CPU_burst(204)

    def tick_PPU_modes_basis(self):
        lcdc = self.memctl.io_registers[0xFF40].value

        # clear the lcd if PPU is disabled
        if not BO.get_nth_bit(lcdc, 7):
            self.PPU.disable()
            self.CPU_burst(456)
            pygame.display.flip()
            return

        ly = self.memctl.io_registers[0xFF44].value

        if self.PPU.is_VBLANK_scan(ly):
            # cpu burst then inc ly and handle lyc compare
            self.CPU_burst(456)
            self.PPU.handle_VBLANK()
            return

        self.PPU.handle_LY_compare()

        self.scanline_PPU_modes()

        # if just finished the last visible scanline
        if ly == GB_LCD_RES[1] - 1:
            # update real display at the end of scanline
            pygame.display.flip()
            # ensure framerate is 60
            pyclock.tick(60)
            self.PPU.enter_VBLANK()

        self.PPU.inc_ly()
        # handle keyboard inputs from the user
        self.handle_inputs()

    def handle_inputs(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit()
            elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                is_pressed = event.type == pygame.KEYDOWN
                if event.key == pygame.K_q:
                    self.debug = True
                if event.key not in self.keys_inputs:
                    continue
                if is_pressed:
                    self.input_state = BO.res_nth_bit(
                        self.input_state,  self.keys_inputs[event.key])
                else:
                    self.input_state = BO.set_nth_bit(
                        self.input_state,  self.keys_inputs[event.key])
        self.memctl.input_state = self.input_state

    def powerup(self):
        self.set_display()
        self.SM83_processor.set_register('PC', 0x0)
        self.memctl.boot_enabled = True
        while True:
            self.tick_PPU_modes_basis()
            self.screen.blit(self.PPU.pgdisplay, (10, 10))

    def insert_cartridge(self, cartridge: Cartridge):
        self.memctl.rom.burn_from(cartridge=cartridge)

    def interrupt_pending(self):
        _if = self.memctl.read_at(0xFF0F)
        _ie = self.memctl.read_at(0xFFFF)
        return _if & _ie

    def debug_state(self, ins, colorama):
        print(
            f"\nExecuted instruction: \
                {colorama.Fore.YELLOW}{ins}{colorama.Style.RESET_ALL}")
        print(self.SM83_processor.dump_state_colorama(colorama=colorama))

    # for doctor gameboy
    def log_pc_state(self, logfile):
        AA = self.memctl.read_at(
            self.SM83_processor.get_register('PC'))
        BB = self.memctl.read_at(
            self.SM83_processor.get_register('PC') + 1)
        CC = self.memctl.read_at(
            self.SM83_processor.get_register('PC') + 2)
        DD = self.memctl.read_at(
            self.SM83_processor.get_register('PC') + 3)
        with open(logfile, 'a') as f:
            f.write(f"A:{self.SM83_processor.get_register('A'):02X} F:{self.SM83_processor.flags_register():02X} B:{self.SM83_processor.get_register('B'):02X} C:{self.SM83_processor.get_register('C'):02X} D:{self.SM83_processor.get_register('D'):02X} E:{self.SM83_processor.get_register('E'):02X} H:{self.SM83_processor.get_register('H'):02X} L:{self.SM83_processor.get_register('L'):02X} SP:{self.SM83_processor.get_register('SP'):04X} PC:{self.SM83_processor.get_register('PC'):04X} PCMEM:{AA:02X},{BB:02X},{CC:02X},{DD:02X}\n")
