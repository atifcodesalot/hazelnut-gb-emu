

from .memory import GBMemoryController
from .auxiliary import ByteOperator as BO, string_to_rgb as s2rgb
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
        self.sprite_rows = []
        #

        self.mode = None
        self.buffer = bytearray([0, ] * GB_LCD_RES[0] * GB_LCD_RES[1])
        self.pgdisplay = pygame.image.frombuffer(
            self.buffer, GB_LCD_RES, "P")

        for i in range(4):
            self.pgdisplay.set_palette_at(i, GB_LCD_PALETTE_rgb[i])

        self.window_internal_counter = 0

        self.bg_palette = []
        self.obj0_palette = []
        self.obj1_palette = []

        self.sp_winner_cache = []

    def get_color_palette(self, palette_reg):
        return [(palette_reg >> s) & 0b11 for s in range(0, 8, 2)]

    def get_shade(self, palette_reg, shade_bits):
        ti = shade_bits * 2
        mask = (1 << ti) * 3
        return (palette_reg & mask) >> ti

    def get_static_tile(self, lcdc, px, py, map_start):
        lcdc_4 = lcdc >> 4 & 1
        index = self.vram.array[map_start + (py >> 3) * 32 + (px >> 3)]
        offset = 0x0000 if lcdc_4 else 0x1000
        tile_offset = offset + index * 16 if lcdc_4 else offset + \
            BO.byte_twos_complement(index) * 16
        final_offset = tile_offset + (py % 8) * 2
        return self.vram.get_block_at(final_offset, 2)

    def get_tile_row_BG(self, lcdc, px, py, bgm_start):
        return self.get_static_tile(lcdc, px, py, bgm_start)

    def get_tile_row_WINDOW(self, lcdc, px, py, wm_start):
        return self.get_static_tile(lcdc, px, py, wm_start)

    # takes relative pixels pos
    def get_pixel_row(self, ti, rpy):
        row = self.vram.get_block_at(ti * 16 + 2 * rpy, 2)
        return row

    def get_context(self):
        # palette register
        palette_reg = self.memctl.io_registers[0xFF47]
        scx = self.memctl.io_registers[0xFF43]
        scy = self.memctl.io_registers[0xFF42]
        ly = self.memctl.io_registers[0xFF44]
        lyc = self.memctl.io_registers[0xFF45]
        lcd_control = self.memctl.io_registers[0xFF40]
        return palette_reg, (scx, scy), (ly, lyc), lcd_control

    def enter_VBLANK(self):
        self.window_internal_counter = 0
        self.mode = 1
        # edit the STAT register's 2 bits to be mode 1
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.set_nth_bit(STAT, 0)
        new_STAT = BO.res_nth_bit(new_STAT, 1)
        self.memctl.io_registers[0xFF41] = new_STAT
        # request VBlank interrupt
        new_if = self.memctl.io_registers[0xFF0F]
        new_if |= 1
        self.memctl.io_registers[0xFF0F] = new_if
        # # #
        # request VBlank stat int, different from the above interrupt line
        if (STAT >> 4) & 1:
            self.request_STAT_int()

    def is_VBLANK_scan(self, ly):
        return 144 <= ly <= 153

    def request_STAT_int(self):
        IF = self.memctl.io_registers[0xFF0F]
        new_IF = BO.set_nth_bit(IF, 1)
        self.memctl.io_registers[0xFF0F] = new_IF

    def handle_LY_compare(self):
        ly = self.memctl.io_registers[0xFF44]
        lyc = self.memctl.io_registers[0xFF45]
        STAT = self.memctl.io_registers[0xFF41]
        if ly == lyc and not STAT >> 2 & 1:
            if STAT >> 6 & 1:
                self.request_STAT_int()
            new_STAT = BO.set_nth_bit(STAT, 2)
            self.memctl.io_registers[0xFF41] = new_STAT
        elif ly != lyc:
            # clear if STAT's lyc == ly bit was true
            if STAT >> 2 & 1:
                new_STAT = BO.res_nth_bit(STAT, 2)
                self.memctl.io_registers[0xFF41] = new_STAT

    def enter_OAM(self):
        self.mode = 2
        # edit the STAT register's 2 bits to be mode 2
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.res_nth_bit(STAT, 0)
        new_STAT = BO.set_nth_bit(new_STAT, 1)
        if (STAT >> 5) & 1:
            # oam mode stat int
            self.request_STAT_int()
        self.memctl.io_registers[0xFF41] = new_STAT

        # clear sprites from previous scanline
        self.sprites.clear()
        self.sprite_rows.clear()

    def enter_HBLANK(self):
        self.mode = 0
        # edit the STAT register's 2 bits to be mode 0
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.res_nth_bit(STAT, 0)
        new_STAT = BO.res_nth_bit(new_STAT, 1)
        if (STAT >> 3) & 1:
            # hblank stat int
            self.request_STAT_int()
        self.memctl.io_registers[0xFF41] = new_STAT

    def enter_drawing_mode(self):
        self.mode = 3
        # edit the STAT register's 2 bits to be mode 3
        STAT = self.memctl.io_registers[0xFF41]
        new_STAT = BO.set_nth_bit(STAT, 0)
        new_STAT = BO.set_nth_bit(new_STAT, 1)
        self.memctl.io_registers[0xFF41] = new_STAT

        lcdc = self.memctl.io_registers[0xFF40]
        ly = self.memctl.io_registers[0xFF44]
        sprite_height = 16 if lcdc >> 2 & 1 else 8
        self.cache_sprite_rows(sprite_height, ly)
        self.cache_sprite_winners()

    def mix(self, st_px, sp_px, sp_obj):
        if sp_obj is None or sp_px == 0:
            if st_px:
                final_shade = self.bg_palette[st_px]
            else:
                # if bg is also none, meaning bg and window is disabled (lcdc bit 0 is False)
                final_shade = self.bg_palette[0]
            return final_shade
        # if there is a sprite pixel
        sp_plt = self.obj1_palette if (
            sp_obj[3] >> 4 & 1) else self.obj0_palette
        obj_priority = sp_obj[3] >> 7 & 1
        # if priority bit is 0, then obj has priority over bg or window pxels
        if not obj_priority:
            final_shade = sp_plt[sp_px]
        else:
            if st_px:
                final_shade = self.bg_palette[st_px]
            else:
                final_shade = sp_plt[sp_px]
        return final_shade

    def get_BG_pixels(self, lcdc, bgx, bgy, map_start_bg):
        BG_row = self.get_tile_row_BG(
            lcdc, bgx, bgy, map_start_bg)
        return [
            (((BG_row[1] >> bit) & 1) << 1) | ((BG_row[0] >> bit) & 1)
            for bit in range(7, -1, -1)
        ]

    def get_W_pixels(self, lcdc, lwx, map_start_window):
        W_row = self.get_tile_row_WINDOW(
            lcdc, lwx, self.window_internal_counter, map_start_window)
        return [
            (((W_row[1] >> bit) & 1) << 1) | (
                (W_row[0] >> bit) & 1)
            for bit in range(7, -1, -1)
        ]

    def drawing_mode(self, ctx):
        # todo: please refactor this function
        self.enter_drawing_mode()
        st_palette_reg, (scx, scy), (ly, _), lcdc = ctx
        self.bg_palette = self.get_color_palette(st_palette_reg)
        self.obj0_palette = self.get_color_palette(
            self.memctl.io_registers[0xFF48])
        self.obj1_palette = self.get_color_palette(
            self.memctl.io_registers[0xFF49])
        wy, wx = self.memctl.io_registers[0xFF4A], self.memctl.io_registers[0xFF4B]

        bgy = (ly + scy) & 0xff
        lwy = ly - wy
        map_start_bg = 0x1C00 if lcdc >> 3 & 1 else 0x1800
        map_start_window = 0x1C00 if lcdc >> 6 & 1 else 0x1800

        window_was_visible = False
        row_n = GB_LCD_RES[0] * ly
        static_enable = lcdc & 1

        for x in range(GB_LCD_RES[0]):
            # compute local background and window pixel coordinates
            lwx = x - wx + 7
            bgx = (scx + x) & 0xff
            bg_offset = bgx % 8
            w_offset = lwx % 8
            #

            # if new bg row needs to be fetched
            if x == 0 or bg_offset == 0:
                BG_pixels = self.get_BG_pixels(
                    lcdc, bgx, bgy, map_start_bg)

            # get background pixel from offset
            BG_pixel = BG_pixels[bg_offset]

            window_active = ((lcdc >> 5 & 1) and lwy >=
                             0 and lwx >= 0 and static_enable)
            if window_active:
                first_window_pixel = not window_was_visible
                window_was_visible = True
                # if new window row needs to be fetched
                if w_offset == 0 or first_window_pixel:
                    W_pixels = self.get_W_pixels(lcdc, lwx, map_start_window)

                W_pixel = W_pixels[w_offset]

            # either BG or Window pixel
            if static_enable:
                st_pixel = BG_pixel if not window_active else W_pixel
            else:
                st_pixel = None

            # call sprite pixel function only if there are sprites
            # and if lcdc NOW enables objects
            if self.sp_winner_cache[x] and (lcdc >> 1) & 1:
                sp_px, sr = self.sp_winner_cache[x]
            else:
                sp_px = sr = None

            shade = self.mix(st_pixel, sp_px, sr)

            # set final shade on buffer
            self.buffer[row_n + x] = shade

        if window_was_visible:
            self.window_internal_counter += 1

        self.dots += 172

    def OAM_scan(self, ctx):
        _, (_, _), (ly, _), lcdc = ctx
        self.enter_OAM()
        lcdc_2 = lcdc >> 2 & 1
        self.mode = 2
        for i in range(0, 160, 4):
            sr = self.memctl.OAM[i: i + 4]
            sprite_height = 16 if lcdc_2 else 8
            # this sprite's lines intersect with current scanline
            if sr[0] - 16 <= ly < sr[0] - 16 + sprite_height:
                self.sprites.append(sr)

        # only 10 sprites max for each scanline
        # sort based on x coordinates
        self.sprites = sorted(self.sprites[:10], key=lambda sr: sr[1])

        self.dots += 80

    def cache_sprite_rows(self, sprite_height, py):
        for sr in self.sprites:
            sy = sr[0] - 16
            ti = sr[2]
            info = sr[3]

            rpy = py - sy

            # handle Y flip
            if info & 0x40:
                rpy = sprite_height - 1 - rpy

            if sprite_height == 16:
                ti &= 0xFE

                if rpy >= 8:
                    ti += 1
                    rpy -= 8

            row = self.get_pixel_row(ti, rpy)

            self.sprite_rows.append(
                [BO.get_pixel_2bpp(row[0], row[1], i) for i in range(8)])

    def cache_sprite_winners(self):
        self.sp_winner_cache = [None,] * 160
        for i, sr in enumerate(self.sprites):
            xflip = (sr[3] >> 5) & 1
            sx = sr[1] - 8
            row = self.sprite_rows[i]
            for j in range(8):
                scan = sx + j
                if not (GB_LCD_RES[0] > scan > 0):
                    continue
                old = self.sp_winner_cache[scan]
                # if no sprite that has higher priority,
                # occupied this pixel before
                if old is None:
                    # account for x flip
                    px = row[7 - j] if xflip else row[j]
                    # if pixel is not transparent
                    if px != 0:
                        self.sp_winner_cache[scan] = (px, sr)

    def HBLANK_mode(self):
        self.enter_HBLANK()
        self.dots += 204

    def handle_VBLANK(self):
        # do other stuff ?
        self.dots += 456
        self.inc_ly()
        self.handle_LY_compare()

    def inc_ly(self):
        ly = self.memctl.io_registers[0xFF44]
        self.memctl.io_registers[0xFF44] = (ly + 1) % 154

    def disable(self):
        self.pgdisplay.fill(GB_LCD_OFF)
        # reset ly
        self.memctl.io_registers[0xFF44] = 0
        # set mode to 0
        self.enter_HBLANK()
        self.dots = 0
