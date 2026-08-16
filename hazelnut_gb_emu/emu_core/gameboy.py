from .sm83 import *
from .PPU import *
from .memory import *
from .cartridge import Cartridge
from .auxiliary import BO


pyclock = pygame.time.Clock()


# The gameboy class
# manages master functionalities such as timer ticks;
# Halt handling, DMA, internal divider register ticking
# CPU ticking with scanline modes basis
# Real input to Joypad handling, pygame display etc.
#

class Gameboy:
    def __init__(self):
        self.screen = None
        self.input_state = 255
        self.TIMA_hertz = [256*4, 16, 64, 256]
        self.memctl = GBMemoryController(
            self, ext_ram=False)
        self.SM83_processor = SM83(self.memctl)
        self.PPU = GbPPU(self.memctl)
        # 16 bit internal divider register value
        self.cycles = 0
        #
        self.DMA = False

        self.debug = False
        self.running = True

        self.cpu_debt = 0
        self.serial_timer = 0

        self.pyclock = pygame.time.Clock()

    def turn_on_LCD(self):
        self.memctl[0xFF40] = 0x91

    def awake(self):
        self.SM83_processor.HALT = False

    def handle_cpu_halt(self):
        if self.interrupt_pending():
            self.awake()
            return True

    def tick_timers(self, dots):
        TAC = self.memctl.io_registers[0xFF07]
        TIMA_en = (TAC >> 2) & 1
        if TIMA_en:
            self.handle_TIMA(old_cycles=self.cycles, elapsed=dots)
        self.cycles = (self.cycles + dots)
        self.handle_DIV()

    def CPU_APU_burst(self, clock_cycles):
        if self.SM83_processor.HALT:
            if not self.handle_cpu_halt():
                self.tick_timers(clock_cycles)
                self.handle_serial(clock_cycles)
                self.cpu_debt = 0
                return
        cycles_passed = 0
        while cycles_passed < clock_cycles:
            ins, ins_cycles = self.SM83_processor.tick_one_ins(self)
            self.tick_timers(ins_cycles)
            self.handle_serial(ins_cycles)
            cycles_passed += ins_cycles

            if self.SM83_processor.HALT:
                remaining = clock_cycles - cycles_passed
                self.tick_timers(remaining)
                self.handle_serial(remaining)
                self.cpu_debt = 0
                return

        # get debt
        self.cpu_debt = cycles_passed - clock_cycles

    def handle_DIV(self):
        self.memctl.io_registers[0xFF04] = (self.cycles >> 8) & 0xff

    def handle_TIMA(self, old_cycles, elapsed):
        TAC = self.memctl.io_registers[0xFF07]
        mc = self.TIMA_hertz[TAC & 0b11]
        old = old_cycles // mc
        new = (old_cycles + elapsed) // mc
        falls = new - old
        for _ in range(falls):
            self.memctl.inc_TIMA()

    def handle_serial(self, elapsed):
        SC = self.memctl.io_registers[0xFF02]
        if (SC & 0x81) != 0x81:
            return
        old = self.cycles // 0x200
        new = (self.cycles + elapsed) // 0x200
        falls = new - old
        for _ in range(falls):
            self.shift_SB()

    def shift_SB(self):
        SB = self.memctl.io_registers[0xFF01]
        send_bit = SB >> 7 & 1
        self.send_serial_bit(send_bit)
        SB = (SB << 1) & 0x7f
        recvd = self.get_serial_bit()
        SB = ((SB << 1) & 0xFF) | recvd
        self.memctl.io_registers[0xFF01] = SB
        if self.serial_timer + 1 == 8:
            # request serial interrupt
            IF = self.memctl.io_registers[0xFF0F]
            new_IF = BO.set_nth_bit(IF, 3)
            self.memctl.io_registers[0xFF0F] = new_IF
            # clear transmission active bit
            SC = self.memctl.io_registers[0xFF02]
            SC = BO.res_nth_bit(SC, 7)

        self.serial_timer = (self.serial_timer + 1) % 8

    def send_serial_bit(self, bit):
        # stub
        pass

    def get_serial_bit(self):
        return 1

    def start_DMA(self):
        # logger.debug("starting DMA...")
        m = self.memctl
        self.DMA = True
        source = (m.io_registers[0xFF46]) * 0x100
        # copy 160 bytes to OAM
        for i in range(0xA0):
            m.OAM[i] = m.read_at(source + i)
        # takes 640 dots
        self.tick_timers(640)
        # logger.debug("ending DMA...")
        # logger.debug(f"OAM:{self.memctl.OAM}")

    def scanline_PPU_modes(self):
        # timer tick are inside cpu burst calls
        self.PPU.OAM_scan(self.PPU.get_context())
        self.CPU_APU_burst(80 - self.cpu_debt)
        # recall because CPU burst may change the context
        self.PPU.drawing_mode(self.PPU.get_context())
        self.CPU_APU_burst(172 - self.cpu_debt)
        self.PPU.HBLANK_mode()
        self.CPU_APU_burst(204 - self.cpu_debt)

    def tick_PPU_modes_basis(self):
        lcdc = self.memctl.io_registers[0xFF40]

        # clear the lcd if PPU is disabled
        if not lcdc >> 7 & 1:
            self.PPU.disable()
            self.CPU_APU_burst(456)
            return

        ly = self.memctl.io_registers[0xFF44]

        if self.PPU.is_VBLANK_scan(ly):
            # cpu burst then inc ly and handle lyc compare
            self.CPU_APU_burst(456)
            self.PPU.handle_VBLANK()
            return

        self.scanline_PPU_modes()

        self.PPU.inc_ly()
        self.PPU.handle_LY_compare()

        # if just finished the last visible scanline
        if ly == GB_LCD_RES[1] - 1:
            # ensure framerate is 60
            self.pyclock.tick(59)
            #
            self.PPU.enter_VBLANK()

    def powerup(self):
        self.SM83_processor.set_register('PC', 0x0)
        self.memctl.boot_enabled = True
        self.running = True

    def scanline_step(self):
        self.tick_PPU_modes_basis()

    def insert_cartridge(self, cartridge: Cartridge):
        self.memctl.rom.burn_from(cartridge=cartridge)

    def interrupt_pending(self):
        _if = self.memctl.io_registers[0xFF0F]
        ie = self.memctl.io_registers[0xFFFF]
        return _if & ie
