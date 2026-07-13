

from .sm83 import *
from .PPU import *
from .memory import *

import colorama
from .cartridge import Cartridge
from .aux import BO
import os
import threading


pyclock = pygame.time.Clock()


# The gameboy class
# manages master functionalities such as timer ticks;
# Halt handling, DMA, internal divider register ticking
# CPU ticking with scanline modes basis
# Real input to Joypad handling, pygame display etc.
#

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
        self.set_display()
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

    def turn_on_LCD(self):
        self.memctl[0xFF40] = 0x91

    def set_display(self):
        gw, gh = GB_LCD_RES
        self.screen = pygame.display.set_mode(size=(gw + 10, gh + 200))

    def awake(self):
        self.SM83_processor.HALT = False

    def handle_cpu_halt(self):
        if self.interrupt_pending():
            self.awake()
            return True

    def tick_timers(self, dots):
        TAC = self.memctl.io_registers[0xFF07].value
        TIMA_en = (TAC >> 2) & 1
        if TIMA_en:
            self.handle_TIMA(old_cycles=self.cycles, elapsed=dots)
        self.cycles = (self.cycles + dots) & 0xffff
        self.handle_DIV()

    def CPU_burst(self, clock_cycles):
        if self.SM83_processor.HALT:
            if not self.handle_cpu_halt():
                self.tick_timers(clock_cycles)
                return
        cycles_passed = 0
        while cycles_passed < clock_cycles:
            ins, ins_cycles = self.SM83_processor.tick_one_ins(self)
            self.tick_timers(ins_cycles)
            # if self.debug:
            #     self.debug_state(ins, colorama=colorama)
            #     if self.memctl.io_registers[0xFF0F].value != 0:
            #         print(self.memctl.io_registers[0xFF0F])
            #     print(self.memctl.io_registers[0xFF05].value)
            cycles_passed += ins_cycles

            if self.SM83_processor.HALT:
                self.tick_timers(clock_cycles - cycles_passed)
                break

    def handle_DIV(self):
        self.memctl.io_registers[0xFF04].value = (self.cycles >> 8) & 0xff

    def handle_TIMA(self, old_cycles, elapsed):
        TAC = self.memctl.io_registers[0xFF07].value
        mc = self.TIMA_hertz[TAC & 0b11]
        old = old_cycles // mc
        new = (old_cycles + elapsed) // mc
        falls = new - old
        for _ in range(falls):
            self.memctl.inc_TIMA()

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
        # timer tick are inside cpu burst calls
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
        if not lcdc >> 7 & 1:
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
            #
            self.PPU.enter_VBLANK()

        self.PPU.inc_ly()
        # handle real keyboard inputs from the user
        self.handle_inputs()

    def handle_inputs(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
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
        self.SM83_processor.set_register('PC', 0x0)
        self.memctl.boot_enabled = True
        self.running = True
        while self.running:
            self.tick_PPU_modes_basis()
            self.screen.blit(self.PPU.pgdisplay, (5, 10))

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


# A session controller for the gameboy class
# Takes the gb instance and spawns two threads:
# display and emulate
# Display thread manages the display and just reads emulator state; no data races
# Emulate thread runs the emulator
#

# Session controller checks the current implementations as well
# Manages saving and loading external ram data


class SessionController:
    def __init__(self, gameboy: Gameboy, cartridge: Cartridge):
        self.gameboy = gameboy
        self.cartridge = cartridge
        self.game_name = cartridge.title
        self.gameboy.memctl.configure_bank_switching(cartridge)
        logger.debug("Extended ROM size: %d bytes" %
                     self.gameboy.memctl.rom.size)
        logger.debug("External RAM size: %d bytes" %
                     len(self.gameboy.memctl.ext_ram.array))

        self.cart_has_battery = "BATTERY" in self.cartridge.type_name

        self.dpad = (
            pygame.Rect(40+5, 250-30, 20, 10),  # Right
            pygame.Rect(10+5, 250-30, 20, 10),  # Left
            pygame.Rect(30+5, 230-30, 10, 20),  # Up
            pygame.Rect(30+5, 260-30, 10, 20),  # Down
        )

        self.select_start = (
            (6, pygame.Rect(45+5, 300-30, 35, 15)),  # Select
            (7, pygame.Rect(85+5, 300-30, 35, 15)),  # Start
        )
        self.pressed_color = "#FF991C"

        pygame.font.init()
        btn_font = pygame.sysfont.SysFont("Arial", 18)
        self.A_text = btn_font.render('A', True, (255, 255, 255))
        self.B_text = btn_font.render('B', True, (255, 255, 255))
        ss_font = btn_font = pygame.sysfont.SysFont("Arial", 8)
        self.st_text = ss_font.render('START', True, (255, 255, 255))
        self.sl_text = ss_font.render('SELECT', True, (255, 255, 255))

    def check_implementations(self, cartridge_types, implemented):
        if self.cartridge.type not in implemented:
            logger.info(
                f"\n\nThis game ({self.game_name}) uses\
            {self.cartridge.type_name},\ which isn't implemented in the emulator yet.")
            logger.info("The emulator currently supports cartridges that are: " + ', '.join(
                [cartridge_types[impl] for impl in implemented]) + "\n")

            input("IF you want to continue nevertheless, press any button.")

    def emulate(self):
        self.gameboy.insert_cartridge(self.cartridge)
        self.try_loading_save()
        self.gameboy.powerup()
        self.save()

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

    def save(self):
        ext = self.gameboy.memctl.ext_ram
        if ext is not None \
                and ext.size > 0 and self.cart_has_battery:

            f = open(self.cartridge.title+'.save', "wb")
            f.write(self.gameboy.memctl.ext_ram.array)
            f.close()
            logger.info(
                f"Save file generated for {self.game_name} at {os.getcwd()}.")

    def draw_A(self):
        s = self.gameboy.screen
        inp = self.gameboy.input_state
        A_press = not BO.get_nth_bit(inp, 4)
        A_col = (255, 255, 255) if not A_press else self.pressed_color
        pygame.draw.circle(s, A_col, (135, 210), 12, 2)
        s.blit(self.A_text, (129, 200))

    def draw_B(self):
        s = self.gameboy.screen
        inp = self.gameboy.input_state
        B_press = not BO.get_nth_bit(inp, 5)
        B_col = (255, 255, 255) if not B_press else self.pressed_color
        pygame.draw.circle(s, B_col, (105, 230), 12, 2)
        s.blit(self.B_text, (99, 220))

    def draw_dpad(self):
        inp = self.gameboy.input_state

        for bit, rect in enumerate(self.dpad):
            pressed = not BO.get_nth_bit(inp, bit)
            color = self.pressed_color if pressed else (255, 255, 255)

            pygame.draw.rect(self.gameboy.screen, color, rect, width=2)

    def draw_start_select(self):
        s = self.gameboy.screen
        inp = self.gameboy.input_state

        s.blit(self.st_text, (92, 275))
        s.blit(self.sl_text, (52, 275))

        for bit, rect in self.select_start:
            pressed = not BO.get_nth_bit(inp, bit)
            color = self.pressed_color if pressed else (255, 255, 255)

            pygame.draw.rect(
                s,
                color,
                rect,
                width=2,
                border_radius=5,
            )

    def draw_inputs(self):
        self.draw_A()
        self.draw_B()
        self.draw_dpad()
        self.draw_start_select()
        # placeholder

    def draw_cosmetic(self):
        pass

    def display(self):
        clock = pygame.time.Clock()
        while self.gameboy.running:
            self.draw_inputs()
            self.draw_cosmetic()
            clock.tick(20)

    def main(self):
        self.emu_thread = threading.Thread(target=self.emulate)
        self.disp_thread = threading.Thread(target=self.display)
        self.emu_thread.start()
        self.disp_thread.start()
