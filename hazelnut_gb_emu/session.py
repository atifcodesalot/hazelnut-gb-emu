from .emu_core.gameboy import Gameboy, GameboyColor
from .emu_core.cartridge import CartridgeReader, CARTRIDGE_TYPES
from .emu_core.PPU import GB_LCD_RES
from .emu_core.auxiliary import BO
from .emu_core import logger
from .emu_core import IMPLEMENTED_MODES

from tkinter import filedialog, Tk
import pygame
import threading
import time
import sys
import gc
import os


# GUI drawer class for drawing buttons, and more stuff in the future
# TODO: refactor the button init
class GUIDrawer:
    def __init__(self, screen, gbres, gboff, scaler):
        self.screen = screen
        self.gbres = gbres
        self.gboff = gboff
        self.scaler = scaler
        self.gui_start = (
            gboff[0] * 2 * scaler,
            gboff[1] + gbres[1] + gboff[0] * 2 * scaler,
        )
        self.dpad_center = (
            self.gui_start[0] + 30 * scaler,
            self.gui_start[1] + 30 * scaler,
        )
        dc = self.dpad_center

        dpads = 10 * scaler
        dpadl = 20 * scaler

        self.dpad = (
            pygame.Rect(
                dc[0] + dpads * 0.5, dc[1] - dpads * 0.5, dpadl, dpads
            ),  # Right
            pygame.Rect(
                dc[0] - dpads * 0.5 - dpadl, dc[1] - dpads * 0.5, dpadl, dpads
            ),  # Left
            pygame.Rect(
                dc[0] - dpads * 0.5, dc[1] - dpadl - dpads * 0.5, dpads, dpadl
            ),  # Up
            pygame.Rect(dc[0] - dpads * 0.5, dc[1] + dpads * 0.5, dpads, dpadl),  # Down
        )

        sw, sh = screen.get_size()
        self.selectoff = sw // 2 - 27 * scaler, dc[1] + 50 * scaler
        self.startoff = sw // 2 + 2 * scaler, dc[1] + 50 * scaler
        self.select_start = (
            (6, pygame.Rect(*self.selectoff, 25 * scaler, 10 * scaler)),  # Select
            (7, pygame.Rect(*self.startoff, 25 * scaler, 10 * scaler)),  # Start
        )

        self.Aoff = (dc[0] + sw // 2 + 12 * scaler, dc[1] - 12 * scaler)
        self.Boff = (dc[0] + sw // 2 - 12 * scaler, dc[1] + 12 * scaler)

        self.Atxtoff = (self.Aoff[0] - 3 * self.scaler, self.Aoff[1] - 4 * self.scaler)
        self.Btxtoff = (self.Boff[0] - 3 * self.scaler, self.Boff[1] - 4 * self.scaler)

        self.Sttxtoff = (
            self.startoff[0] + 2 * self.scaler,
            self.startoff[1] + 2 * self.scaler,
        )
        self.Sltxtoff = (
            self.selectoff[0] + 2 * self.scaler,
            self.selectoff[1] + 2 * self.scaler,
        )

        self.pressed_color = "#1C77FF"

        pygame.font.init()
        btn_font = pygame.sysfont.SysFont("Arial", int(10 * scaler))
        self.A_text = btn_font.render("A", True, (255, 255, 255))
        self.B_text = btn_font.render("B", True, (255, 255, 255))
        ss_font = btn_font = pygame.sysfont.SysFont("Arial", int(10 * self.scaler))
        self.st_text = ss_font.render("START", True, (255, 255, 255))
        self.sl_text = ss_font.render("SELECT", True, (255, 255, 255))

        ins_font = btn_font = pygame.sysfont.SysFont("Arial", int(6 * self.scaler))
        self.control_ins1 = (
            "Controls: Arrow keys: D-Pad, X/Z: A/B, S: Select, Enter: Start"
        )
        self.control_ins2 = "R: reset emulation, ESC: exit and select new rom"
        self.insctl1_surf = ins_font.render(
            self.control_ins1, True, (0, 0, 0), (255, 255, 255)
        )
        self.insctl2_surf = ins_font.render(
            self.control_ins2, True, (0, 0, 0), (255, 255, 255)
        )
        w1 = self.insctl1_surf.get_width()
        h1 = self.insctl1_surf.get_height()
        self.insctl1_off = ((sw - w1) // 2, sh - h1 - 15 * self.scaler)
        w2 = self.insctl2_surf.get_width()
        h2 = self.insctl2_surf.get_height()
        self.insctl2_off = ((sw - w2) // 2, sh - h2 - 5 * self.scaler)

    def draw_A(self, gb_inp):
        s = self.screen
        A_press = not BO.get_nth_bit(gb_inp, 4)
        A_col = (255, 255, 255) if not A_press else self.pressed_color
        pygame.draw.circle(s, A_col, self.Aoff, 10 * self.scaler, 2)
        s.blit(self.A_text, self.Atxtoff)

    def draw_B(self, gb_inp):
        s = self.screen
        B_press = not BO.get_nth_bit(gb_inp, 5)
        B_col = (255, 255, 255) if not B_press else self.pressed_color
        pygame.draw.circle(s, B_col, self.Boff, 10 * self.scaler, 2)
        s.blit(self.B_text, self.Btxtoff)

    def draw_dpad(self, gb_inp):
        for bit, rect in enumerate(self.dpad):
            pressed = not BO.get_nth_bit(gb_inp, bit)
            color = self.pressed_color if pressed else (255, 255, 255)

            pygame.draw.rect(self.screen, color, rect, width=2)

    def draw_start_select(self, gb_inp):
        s = self.screen

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
        pygame.draw.circle(self.screen, (255, 255, 255), self.dpad_center, 3)
        self.draw_A(gb_input_state)
        self.draw_B(gb_input_state)
        self.draw_dpad(gb_input_state)
        self.draw_start_select(gb_input_state)
        # placeholder
        self.draw_cosmetic()

    def draw_cosmetic(self, *args):
        s = self.screen
        s.blit(self.insctl1_surf, self.insctl1_off)
        s.blit(self.insctl2_surf, self.insctl2_off)


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
    save_path = os.path.join(".", save_path_name)

    keys_gb_inputs = {
        pygame.K_RIGHT: 0,
        pygame.K_LEFT: 1,
        pygame.K_UP: 2,
        pygame.K_DOWN: 3,
        pygame.K_x: 4,  # A
        pygame.K_z: 5,  # B
        pygame.K_s: 6,  # Select
        pygame.K_RETURN: 7,  # Start
    }

    def __init__(self, gbscaler=1, color=False):
        self.init_gameboy(color=color)
        self.color = color
        self.init_cart()
        self.game_name = self.cartridge.title
        self.check_implementations(
                cartridge_types=CARTRIDGE_TYPES, implemented=IMPLEMENTED_MODES)
        
        self.gbscaler = gbscaler
        gbres = GB_LCD_RES
        self.gbres = [gbres[0] * gbscaler, gbres[1] * gbscaler]
        self.gboff = (5, 10)
        self.gameboy.insert_cartridge(self.cartridge)
        logger.debug("Extended ROM size: %d bytes" % self.gameboy.memctl.rom.size)
        logger.debug(
            "External RAM size: %d bytes" % len(self.gameboy.memctl.ext_ram.array)
        )
        self.cart_has_battery = self.determine_cart_battery()
        
        self.set_display()
        self.GUI = GUIDrawer(self.screen, self.gbres, self.gboff, self.gbscaler)
        
        
        ## emulation related flags
        self.gonna_reset_gb = False
        self.emulation_paused = False
        
    def init_gameboy(self, color=False):
        if color:
            self.gameboy = GameboyColor()
        else:
            self.gameboy = Gameboy()
    
    def init_cart(self):
        file = self.get_rom_file()
        if file is None:
            sys.exit("exiting dialog...")
        reader = CartridgeReader(file)
        self.cartridge = reader.get_cartridge()

    def determine_cart_battery(self):
        return "BATTERY" in self.cartridge.type_name

    def check_implementations(self, cartridge_types, implemented):
        if self.cartridge.type not in implemented:
            logger.info(f"\n\nThis game ({self.game_name}) uses\
            {self.cartridge.type_name},\ which isn't implemented in the emulator yet.")
            logger.info(
                "The emulator currently supports cartridges that are: "
                + ", ".join([cartridge_types[impl] for impl in implemented])
                + "\n"
            )

            input("IF you want to continue nevertheless, press any button.")

    def set_display(self):
        gw, gh = self.gbres
        self.screen = pygame.display.set_mode(size=(gw + 10, gh + 150 * self.gbscaler))
        pygame.display.set_caption(f"{__package__}: {self.game_name}")

    def emulate(self):
        self.try_loading_save()
        self.gameboy.powerup()
        while self.gameboy.running:
            if self.gonna_reset_gb:
                self.reset_gb()
                self.gonna_reset_gb = False
            self.gameboy.scanline_step()
        self.save()

    def reset_gb(self):
        self.gameboy.reset()
        self.gameboy.insert_cartridge(self.cartridge)
        self.gameboy.powerup()

    def try_loading_save(self):
        ext = self.gameboy.memctl.ext_ram
        if ext is not None and ext.size > 0 and self.cart_has_battery:
            try:
                name = os.path.join(self.save_path, str(self.cartridge.title) + ".save")
                f = open(name, "rb")
            except FileNotFoundError:
                logger.info(f"No save file found for {self.game_name}")
                return
            data = f.read(ext.size)
            ext.array[: len(data)] = bytearray(data)
            logger.info(f"Save file {f.name} loaded for {self.game_name}")

    def save(self):
        ext = self.gameboy.memctl.ext_ram
        if ext is not None and ext.size > 0 and self.cart_has_battery:
            if not os.path.isdir(self.save_path):
                os.mkdir(self.save_path)
            f = open(
                os.path.join(self.save_path, str(self.cartridge.title) + ".save"), "wb"
            )
            f.write(self.gameboy.memctl.ext_ram.array)
            f.close()
            logger.info(
                f"Save file generated for {self.game_name} at {os.path.join(os.getcwd(), self.save_path_name)}."
            )

    def display(self):
        while self.gameboy.running:
            input_state = self.gameboy.input_state
            self.GUI.draw_gb_inputs(input_state)
            self.GUI.draw_cosmetic()
            if self.gbscaler > 1:
                scaled = pygame.transform.scale_by(
                    self.gameboy.PPU.pgdisplay, self.gbscaler
                )
                self.screen.blit(scaled, self.gboff)
            else:
                self.screen.blit(self.gameboy.PPU.pgdisplay, self.gboff)
            pygame.display.flip()

    def handle_gb_input_event(self, event):
        gb = self.gameboy
        is_pressed = event.type == pygame.KEYDOWN
        if event.key not in self.keys_gb_inputs:
            if event.key == pygame.K_r:
                self.gonna_reset_gb = True
            elif event.key == pygame.K_ESCAPE:
                self.gameboy.running = False
            return
        if is_pressed:
            gb.input_state = BO.res_nth_bit(
                gb.input_state, self.keys_gb_inputs[event.key]
            )
        else:
            gb.input_state = BO.set_nth_bit(
                gb.input_state, self.keys_gb_inputs[event.key]
            )
        gb.memctl.input_state = gb.input_state

    def consume_events(self):
        gb = self.gameboy
        while gb.running:
            time.sleep(0.0001)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    gb.running = False
                elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                    self.handle_gb_input_event(event)
        self.end()

    def get_rom_file(self):
        filetypes = [
            ("Gameboy files", "*.gb .GB"),
            ("ROM files", "*.rom"),
            ("Binary files,", "*.bin"),
        ]
        if self.color:
            filetypes[0] = ("Gameboy (color) files", "*.gbc *.gb")
            
        title = "Choose a ROM file"
        dir_ = "."

        root = Tk()
        root.withdraw()

        try:
            return filedialog.askopenfile(
                mode="rb", filetypes=filetypes, title=title, initialdir=dir_
            )
        finally:
            # make sure to destroy and kill,
            # the tk object in this thread
            root.destroy()
            del root
            gc.collect()

    def start(self):
        self.disp_thread = threading.Thread(target=self.display)
        self.emu_thread = threading.Thread(target=self.emulate)
        self.disp_thread.start()
        self.emu_thread.start()
        self.consume_events()
        
    def end(self):
        while self.emu_thread.is_alive() or \
            self.disp_thread.is_alive():
                time.sleep(0.0001)
                continue
        pygame.display.quit()
        del self
