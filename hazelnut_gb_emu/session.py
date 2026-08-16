

from .emu_core.gameboy import Gameboy
from .emu_core.cartridge import Cartridge
from .emu_core.PPU import GB_LCD_RES
from .emu_core.auxiliary import BO
from .emu_core import logger
import pygame
import os
import threading
import time



## GUI drawer class for drawing buttons, and more stuff in the future
# TODO: refactor the button init
class GUIDrawer:
    def __init__(self, screen):
        self.screen = screen
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
        self.pressed_color = "#1C77FF"
        
        pygame.font.init()
        btn_font = pygame.sysfont.SysFont("Arial", 18)
        self.A_text = btn_font.render('A', True, (255, 255, 255))
        self.B_text = btn_font.render('B', True, (255, 255, 255))
        ss_font = btn_font = pygame.sysfont.SysFont("Arial", 8)
        self.st_text = ss_font.render('START', True, (255, 255, 255))
        self.sl_text = ss_font.render('SELECT', True, (255, 255, 255))

    def draw_A(self, gb_inp):
        s = self.screen
        A_press = not BO.get_nth_bit(gb_inp, 4)
        A_col = (255, 255, 255) if not A_press else self.pressed_color
        pygame.draw.circle(s, A_col, (135, 210), 12, 2)
        s.blit(self.A_text, (129, 200))

    def draw_B(self, gb_inp):
        s = self.screen
        B_press = not BO.get_nth_bit(gb_inp, 5)
        B_col = (255, 255, 255) if not B_press else self.pressed_color
        pygame.draw.circle(s, B_col, (105, 230), 12, 2)
        s.blit(self.B_text, (99, 220))

    def draw_dpad(self, gb_inp):
        for bit, rect in enumerate(self.dpad):
            pressed = not BO.get_nth_bit(gb_inp, bit)
            color = self.pressed_color if pressed else (255, 255, 255)

            pygame.draw.rect(self.screen, color, rect, width=2)

    def draw_start_select(self, gb_inp):
        s = self.screen

        s.blit(self.st_text, (92, 275))
        s.blit(self.sl_text, (52, 275))

        for bit, rect in self.select_start:
            pressed = not BO.get_nth_bit(gb_inp, bit)
            color = self.pressed_color if pressed else (255, 255, 255)

            pygame.draw.rect(
                s,
                color,
                rect,
                width=2,
                border_radius=5,
            )

    def draw_gb_inputs(self, gb_input_state):
        self.draw_A(gb_input_state)
        self.draw_B(gb_input_state)
        self.draw_dpad(gb_input_state)
        self.draw_start_select(gb_input_state)
        # placeholder
        self.draw_cosmetic()

    def draw_cosmetic(self, *args):
        # stub
        pass


# A session controller for the gameboy class
# Takes the gb instance and spawns two threads:
# display and emulate
# Display thread manages the display and just reads emulator state; no data races
# Emulate thread runs the emulator
#

# Session controller checks the current implementations as well
# Manages saving and loading external ram data

class SessionController:
    save_path_name = "saves"
    save_path = os.path.join('.', save_path_name)

    keys_gb_inputs = {
        pygame.K_RIGHT: 0,
        pygame.K_LEFT: 1,
        pygame.K_UP: 2,
        pygame.K_DOWN: 3,

        pygame.K_a: 4,       # A
        pygame.K_b: 5,       # B
        pygame.K_s: 6,       # Select
        pygame.K_RETURN: 7,  # Start
    }

    def __init__(self, gameboy: Gameboy, cartridge: Cartridge):
        self.gameboy = gameboy
        self.cartridge = cartridge
        self.game_name = cartridge.title
        self.gameboy.memctl.configure_bank_switching(cartridge)
        logger.debug("Extended ROM size: %d bytes" %
                     self.gameboy.memctl.rom.size)
        logger.debug("External RAM size: %d bytes" %
                     len(self.gameboy.memctl.ext_ram.array))

        self.cart_has_battery = self.determine_cart_battery()
        
        self.set_display()
        self.GUI = GUIDrawer(self.screen)

    def determine_cart_battery(self):
        return "BATTERY" in self.cartridge.type_name

    def check_implementations(self, cartridge_types, implemented):
        if self.cartridge.type not in implemented:
            logger.info(
                f"\n\nThis game ({self.game_name}) uses\
            {self.cartridge.type_name},\ which isn't implemented in the emulator yet.")
            logger.info("The emulator currently supports cartridges that are: " + ', '.join(
                [cartridge_types[impl] for impl in implemented]) + "\n")

            input("IF you want to continue nevertheless, press any button.")

    def set_display(self):
        gw, gh = GB_LCD_RES
        self.screen = pygame.display.set_mode(size=(gw + 10, gh + 200))

    def emulate(self):
        self.gameboy.insert_cartridge(self.cartridge)
        self.try_loading_save()
        self.gameboy.powerup()
        while self.gameboy.running:
            self.gameboy.scanline_step()
        self.save()

    def try_loading_save(self):
        ext = self.gameboy.memctl.ext_ram
        if ext is not None \
                and ext.size > 0 and self.cart_has_battery:
            try:
                name = os.path.join(self.save_path, str(
                    self.cartridge.title)+'.save')
                f = open(name, "rb")
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
            if not os.path.isdir(self.save_path):
                os.mkdir(self.save_path)
            f = open(os.path.join(
                self.save_path, str(self.cartridge.title) + '.save'), "wb")
            f.write(self.gameboy.memctl.ext_ram.array)
            f.close()
            logger.info(
                f"Save file generated for {self.game_name} at {os.path.join(os.getcwd(), self.save_path_name)}.")

    def display(self):
        while self.gameboy.running:
            input_state = self.gameboy.input_state
            self.GUI.draw_gb_inputs(input_state)
            self.GUI.draw_cosmetic()
            self.screen.blit(self.gameboy.PPU.pgdisplay, (5, 10))
            pygame.display.flip()

    def handle_gb_input_event(self, event):
        gb = self.gameboy
        is_pressed = event.type == pygame.KEYDOWN
        if event.key not in self.keys_gb_inputs:
            return
        if is_pressed:
            gb.input_state = BO.res_nth_bit(
                gb.input_state, self.keys_gb_inputs[event.key])
        else:
            gb.input_state = BO.set_nth_bit(
                gb.input_state, self.keys_gb_inputs[event.key])
        gb.memctl.input_state = gb.input_state

    def consume_events(self):
        gb = self.gameboy
        while gb.running:
            time.sleep(0.000001)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    gb.running = False
                elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                    self.handle_gb_input_event(event)

    def start(self):
        self.disp_thread = threading.Thread(target=self.display)
        self.emu_thread = threading.Thread(target=self.emulate)
        self.disp_thread.start()
        self.emu_thread.start()
