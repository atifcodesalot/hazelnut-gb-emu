

from .memory import GBMemoryController
from .aux import ByteOperator as BO, string_to_rgb as s2rgb
import pygame
import time


GB_LCD_RES = (160, 144)

GB_LCD_PALETTE = ("#EEB3D0", "#eb51e3",  "#971F69", "#220014")
GB_LCD_PALETTE_rgb = [s2rgb(c) for c in GB_LCD_PALETTE]


class GbPPU:
    def __init__(self, mem_ctl: GBMemoryController):
        self.mem_ctl = mem_ctl
        self.vram = self.mem_ctl.vram
        self.dots = 0

        # sprites that are obtained from previous OAM scan
        self.sprites = []
        #

        self.mode = None
        self.buffer = bytearray([0, ] * GB_LCD_RES[0] * GB_LCD_RES[1])
        self.pgdisplay = pygame.image.frombuffer(
            self.buffer, GB_LCD_RES, "P")

        for i in range(4):
            self.pgdisplay.set_palette_at(i, GB_LCD_PALETTE_rgb[i])

    def get_shade(self, palette_reg, shade_bits):
        ti = shade_bits * 2
        mask = (1 << ti) * 3
        return (palette_reg & mask) >> ti

    def get_static_tile(self, lcdc, px, py, map_control_bit):
        lcdc_Q = lcdc >> map_control_bit & 1
        map_start = 0x1C00 if lcdc_Q else 0x1800
        lcdc_4 = lcdc >> 4 & 1
        index = self.vram.get_byte_at(map_start + (py >> 3) * 32 + (px >> 3))
        offset = 0x0000 if lcdc_4 else 0x1000
        tile_offset = offset + index * 16 if lcdc_4 else offset + \
            BO.byte_twos_complement(index) * 16
        final_offset = tile_offset + (py % 8) * 2
        return self.vram.get_block_at(final_offset, 2)

    def get_tile_row_BG(self, lcdc, px, py):
        return self.get_static_tile(lcdc, px, py, map_control_bit=3)

    def get_tile_row_WINDOW(self, lcdc, px, py):
        return self.get_static_tile(lcdc, px, py, map_control_bit=6)

    # takes relative pixels pos
    def get_pixel_SPRITE(self, ti, rpx, rpy):
        row = self.vram.get_block_at(ti * 16 + 2 * rpy, 2)
        pixel = BO.get_pixel_2bpp(row[0], row[1], rpx)
        return pixel

    def get_winning_pixel_SPRITE(self, lcdc, px, py):
        winner = None
        winner_sprite = None
        best_x = 9999

        lcdc_2 = lcdc >> 2 & 1

        sprite_h = 16 if lcdc_2 else 8

        for sr in self.sprites:
            sy = sr[0] - 16
            sx = sr[1] - 8
            ti = sr[2]
            attr = sr[3]

            rpx = px - sx
            rpy = py - sy

            # Sprite does not cover this screen pixel
            if not (0 <= rpx < 8 and 0 <= rpy < sprite_h):
                continue

            # Apply flips
            xflip = (attr >> 5) & 1
            yflip = (attr >> 6) & 1

            if xflip:
                rpx = 7 - rpx

            if yflip:
                rpy = sprite_h - 1 - rpy

            # Handle 8x16 sprite tile selection
            if sprite_h == 16:
                ti &= 0xFE

                if rpy >= 8:
                    ti += 1
                    rpy -= 8

            pixel = self.get_pixel_SPRITE(ti, rpx, rpy)

            # OBJ color 0 is transparent
            if pixel == 0:
                continue

            x = sr[1]

            # DMG priority rule:
            # smaller X coordinate wins.
            if winner is None or x < best_x:
                winner = pixel
                winner_sprite = sr
                best_x = x

        if winner:
            return winner, winner_sprite[3] >> 7 & 1
        else:
            return None, -1

    def get_context(self):
        # palette register
        palette_reg = self.mem_ctl.io_registers[0xff47].value
        scx, scy = self.mem_ctl.io_registers[0xFF43].value, self.mem_ctl.io_registers[0xFF42].value
        ly, lyc = self.mem_ctl.io_registers[0xFF44].value, self.mem_ctl.io_registers[0xFF45].value
        lcd_control = self.mem_ctl.io_registers[0xFF40].value
        return palette_reg, (scx, scy), (ly, lyc), lcd_control

    def scanline_BG_pixel(self, lcdc, ly, scy, scx, X):
        global_x = (X + scx) % (0xff + 1)
        global_y = (ly + scy) % (0xff + 1)
        pixel_i = global_x % 8
        tile_row = self.get_tile_row_BG(lcdc, global_x, global_y)
        pixel = BO.get_pixel_2bpp(tile_row[0], tile_row[1], pixel_i)
        return pixel

    def scanline_WINDOW_pixel(self, lcdc, ly, X):
        lcdc_5 = lcdc >> 5 & 1
        if not lcdc_5:
            # return None if window is disabled
            return
        Wy, Wx = self.mem_ctl.io_registers[0xFF4A].value, self.mem_ctl.io_registers[0xFF4B].value
        if X < Wx - 7 or ly < Wy:
            return None
        # no scroll...
        window_x = X - Wx + 7
        window_y = ly - Wy
        #
        pixel_i = window_x % 8
        tile_row = self.get_tile_row_WINDOW(lcdc, window_x, window_y)
        pixel = BO.get_pixel_2bpp(tile_row[0], tile_row[1], pixel_i)
        return pixel

    def enter_VBLANK(self):
        self.mode = 1
        # edit the STAT register's 2 bits to be mode 1
        STAT = self.mem_ctl.io_registers[0xFF41]
        new_STAT = BO.set_nth_bit(STAT.value, 0)
        new_STAT = BO.res_nth_bit(new_STAT, 1)
        STAT.value = new_STAT
        # request VBlank interrupt
        if_ = self.mem_ctl.read_at(0xFF0F)
        if_ |= 1
        self.mem_ctl.write_to(0xFF0F, if_)
        # # #

    def is_VBLANK_scan(self, ly):
        return 144 <= ly <= 153

    def handle_LY_compare(self):
        ly = self.mem_ctl.io_registers[0xFF44].value
        lyc = self.mem_ctl.io_registers[0xFF45].value
        STAT = self.mem_ctl.io_registers[0xFF41]
        if ly == lyc:
            new_STAT = BO.set_nth_bit(STAT.value, 2)
            STAT.value = new_STAT
        else:
            if BO.set_nth_bit(STAT.value, 2):
                new_STAT = BO.res_nth_bit(STAT.value, 2)
                STAT.value = new_STAT

    def enter_OAM(self):
        self.mode = 2
        # edit the STAT register's 2 bits to be mode 2
        STAT = self.mem_ctl.io_registers[0xFF41]
        new_STAT = BO.res_nth_bit(STAT.value, 0)
        new_STAT = BO.set_nth_bit(new_STAT, 1)
        STAT.value = new_STAT

        # clear sprites from previous scanline
        self.sprites.clear()

    def enter_HBLANK(self):
        self.mode = 0
        # edit the STAT register's 2 bits to be mode 0
        STAT = self.mem_ctl.io_registers[0xFF41]
        new_STAT = BO.res_nth_bit(STAT.value, 0)
        new_STAT = BO.res_nth_bit(new_STAT, 1)
        STAT.value = new_STAT

    def enter_drawing_mode(self):
        self.mode = 3
        # edit the STAT register's 2 bits to be mode 3
        STAT = self.mem_ctl.io_registers[0xFF41]
        new_STAT = BO.set_nth_bit(STAT.value, 0)
        new_STAT = BO.set_nth_bit(new_STAT, 1)
        STAT.value = new_STAT

    def pixel_mixer(self, preg, BG_Window, sprite, priority):
        # if no winning pixel or sprite is transparent, return bg or window
        if sprite is None or sprite == 0:
            return BG_Window
        else:
            if not priority:
                return sprite
            else:
                return BG_Window if BG_Window else sprite

    def drawing_mode(self, ctx):
        self.enter_drawing_mode()
        palette_reg, (scx, scy), (ly, _), lcdc = ctx
        wy, wx = self.mem_ctl.io_registers[0xFF4A].value, self.mem_ctl.io_registers[0xFF4B].value
        for x in range(GB_LCD_RES[0]):
            # scanline background
            BG_pixel = self.scanline_BG_pixel(lcdc, ly, scy, scx, X=x)
            # window pixel: does not implement scroll
            W_pixel = self.scanline_WINDOW_pixel(lcdc, ly, X=x)

            prefer_window = W_pixel is not None
            # either BG or Window pixel
            static_pixel = BG_pixel if not prefer_window else W_pixel

            sprite_pixel, pbit = self.get_winning_pixel_SPRITE(lcdc, x, ly)

            # placeholder
            final_pixel = self.pixel_mixer(palette_reg,
                                           static_pixel, sprite_pixel, pbit)

            self.buffer[GB_LCD_RES[0] * ly + x] = self.get_shade(palette_reg, final_pixel)
        self.dots += 172

    def OAM_scan(self, ctx):
        palette_reg, (scx, scy), (ly, _), lcdc = ctx
        lcdc_2 = lcdc >> 2 & 1
        self.enter_OAM()
        lcdc_1 = lcdc >> 1 & 1
        if not lcdc_1:
            return
        self.mode = 2
        for i in range(0, 160, 4):
            sr = self.mem_ctl.OAM[i: i + 4]
            sprite_height = 16 if lcdc_2 else 8
            # this sprite's lines intersect with current scanline
            if sr[0]-16 < ly < sr[0] - 16 + sprite_height:
                self.sprites.append(sr)

        # only 10 sprites max for each scanline
        self.sprites = self.sprites[:10]

        self.dots += 80

    def HBLANK_mode(self):
        self.enter_HBLANK()
        self.dots += 204

    def handle_VBLANK(self):
        self.inc_ly()

    def inc_ly(self):
        ly = self.mem_ctl.io_registers[0xFF44]
        ly.value = (ly.value + 1) % 154

    def disable(self):
        # reset ly
        self.mem_ctl.io_registers[0xFF44].value = 0
        # set mode to 0
        self.enter_HBLANK()
        self.dots = 0
