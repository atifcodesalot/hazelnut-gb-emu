

from .memory import GBMemoryController
from .aux import ByteOperator as BO, string_to_rgb as s2rgb
import pygame
from . import logger


GB_LCD_RES = (160, 144)

GB_LCD_PALETTE = ("#e0f8d0", "#88c070",  "#346856", "#081820")
GB_LCD_OFF = "#1D0118"
GB_LCD_PALETTE_rgb = [s2rgb(c) for c in GB_LCD_PALETTE]


class GbPPU:
    def __init__(self, memctl: GBMemoryController):
        self.memctl = memctl
        self.vram = self.memctl.vram
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

        self.window_internal_counter = 0

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
        wsr = None
        best_x = 9999

        lcdc_2 = lcdc >> 2 & 1

        sprite_h = 16 if lcdc_2 else 8

        for sr in self.sprites:
            sy = sr[0] - 16
            sx = sr[1] - 8
            ti = sr[2]
            info = sr[3]

            rpx = px - sx
            rpy = py - sy

            # Sprite does not cover this screen pixel
            if not (0 <= rpx < 8 and 0 <= rpy < sprite_h):
                continue

            # Apply flips
            xflip = (info >> 5) & 1
            yflip = (info >> 6) & 1

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
                wsr = sr
                best_x = x

        return winner, wsr

    def get_context(self):
        # palette register
        palette_reg = self.memctl.io_registers[0xff47].value
        scx = self.memctl.io_registers[0xFF43].value
        scy = self.memctl.io_registers[0xFF42].value
        ly = self.memctl.io_registers[0xFF44].value
        lyc = self.memctl.io_registers[0xFF45].value
        lcd_control = self.memctl.io_registers[0xFF40].value
        return palette_reg, (scx, scy), (ly, lyc), lcd_control

    def get_tile_pixel(self, row, offset):
        pixel = BO.get_pixel_2bpp(row[0], row[1], offset)
        return pixel

    def enter_VBLANK(self):
        self.window_internal_counter = 0
        self.mode = 1
        # edit the STAT register's 2 bits to be mode 1
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.set_nth_bit(STAT.value, 0)
        new_STAT = BO.res_nth_bit(new_STAT, 1)
        STAT.value = new_STAT
        # request VBlank interrupt
        if_ = self.memctl.read_at(0xFF0F)
        if_ |= 1
        self.memctl.write_to(0xFF0F, if_)
        # # #

    def is_VBLANK_scan(self, ly):
        return 144 <= ly <= 153

    def handle_LY_compare(self):
        ly = self.memctl.io_registers[0xFF44].value
        lyc = self.memctl.io_registers[0xFF45].value
        STAT = self.memctl.io_registers[0xFF41]
        if ly == lyc:
            if BO.get_nth_bit(STAT.value, 6):
                # request STAT int
                IF = self.memctl.io_registers[0xFF0F].value
                new_IF = BO.set_nth_bit(IF, 1)
                self.memctl.io_registers[0xFF0F].value = new_IF

            new_STAT = BO.set_nth_bit(STAT.value, 2)
            STAT.value = new_STAT
        else:
            if BO.set_nth_bit(STAT.value, 2):
                new_STAT = BO.res_nth_bit(STAT.value, 2)
                STAT.value = new_STAT

    def enter_OAM(self):
        self.mode = 2
        # edit the STAT register's 2 bits to be mode 2
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.res_nth_bit(STAT.value, 0)
        new_STAT = BO.set_nth_bit(new_STAT, 1)
        STAT.value = new_STAT

        # clear sprites from previous scanline
        self.sprites.clear()

    def enter_HBLANK(self):
        self.mode = 0
        # edit the STAT register's 2 bits to be mode 0
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.res_nth_bit(STAT.value, 0)
        new_STAT = BO.res_nth_bit(new_STAT, 1)
        STAT.value = new_STAT

    def enter_drawing_mode(self):
        self.mode = 3
        # edit the STAT register's 2 bits to be mode 3
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.set_nth_bit(STAT.value, 0)
        new_STAT = BO.set_nth_bit(new_STAT, 1)
        STAT.value = new_STAT

    def pixel_mixer(self, preg, BG_Window, sprite, sprite_obj):
        # if no winning pixel or sprite is transparent, return bg or window
        if sprite is None or sprite == 0:
            if BG_Window:
                return self.get_shade(preg, BG_Window)
            # if bg is also none, meaning bg and window is disabled (lcdc bit 0 is False)
            return 0
        else:
            priority = sprite_obj[3] >> 7 & 1
            objpreg = self.memctl.io_registers[0xFF48 +
                                               (sprite_obj[3] >> 4 & 1)].value
            # if priority bit is 0, then obj has priority over bg or window pxels
            if not priority:
                return self.get_shade(objpreg, sprite)
            else:
                if BG_Window:
                    return self.get_shade(preg, BG_Window)
                return self.get_shade(
                    objpreg, sprite)

    def drawing_mode(self, ctx):
        self.enter_drawing_mode()
        st_palette_reg, (scx, scy), (ly, _), lcdc = ctx
        wy, wx = self.memctl.io_registers[0xFF4A].value, self.memctl.io_registers[0xFF4B].value
        window_was_visible = False
        for x in range(GB_LCD_RES[0]):
            # compute local background and window pixel coordinates
            lwx = x - wx + 7
            lwy = ly - wy
            bgx = (scx + x) & 0xff
            bgy = (ly + scy) & 0xff
            bg_offset = bgx % 8
            w_offset = lwx % 8
            #

            # if new bg row needs to be fetched
            if x == 0 or bg_offset == 0:
                BG_row = self.get_tile_row_BG(
                    lcdc, bgx, bgy)

            # get background pixel from offset
            BG_pixel = self.get_tile_pixel(BG_row, bg_offset)

            window_active = ((lcdc >> 5 & 1) and lwy >= 0 and lwx >= 0)
            if window_active:
                window_was_visible = True
                # if new window row needs to be fetched
                if w_offset == 0 or 7 >= lwx:
                    W_row = self.get_tile_row_WINDOW(
                        lcdc, lwx, self.window_internal_counter)
                W_pixel = self.get_tile_pixel(W_row, w_offset)

            # either BG or Window pixel
            if lcdc & 1:
                static_pixel = BG_pixel if not window_active else W_pixel
            else:
                static_pixel = None
            sprite_pixel, sprite = self.get_winning_pixel_SPRITE(lcdc, x, ly)

            final_shade = self.pixel_mixer(st_palette_reg,
                                           static_pixel, sprite_pixel, sprite)
            self.buffer[GB_LCD_RES[0] * ly +
                        x] = final_shade

        if window_was_visible:
            self.window_internal_counter += 1
        self.dots += 172

    def OAM_scan(self, ctx):
        _, (_, _), (ly, _), lcdc = ctx
        self.enter_OAM()
        lcdc_1 = lcdc >> 1 & 1
        if not lcdc_1:
            return
        lcdc_2 = lcdc >> 2 & 1
        self.mode = 2
        for i in range(0, 160, 4):
            sr = self.memctl.OAM[i: i + 4]
            sprite_height = 16 if lcdc_2 else 8
            # this sprite's lines intersect with current scanline
            if sr[0] - 16 <= ly < sr[0] - 16 + sprite_height:
                self.sprites.append(sr)

        # only 10 sprites max for each scanline
        self.sprites = self.sprites[:10]

        self.dots += 80

    def HBLANK_mode(self):
        self.enter_HBLANK()
        self.dots += 204

    def handle_VBLANK(self):
        # do other stuff ?
        self.handle_LY_compare()
        self.inc_ly()

    def inc_ly(self):
        ly = self.memctl.io_registers[0xFF44]
        ly.value = (ly.value + 1) % 154

    def disable(self):
        self.pgdisplay.fill(GB_LCD_OFF)
        # reset ly
        self.memctl.io_registers[0xFF44].value = 0
        # set mode to 0
        self.enter_HBLANK()
        self.dots = 0
