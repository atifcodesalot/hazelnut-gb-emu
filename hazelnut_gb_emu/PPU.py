

from .memory import GBMemoryController
from .sm83 import ByteOperator as BO
import pygame
import time


GB_LCD_RES = (160, 144)

GB_LCD_PALETTE = ("#9a9e3f", "#496b22",  "#0e450b", "#1b2a09")


class GbPPU:
    def __init__(self, mem_ctl: GBMemoryController):
        self.mem_ctl = mem_ctl
        self.vram = self.mem_ctl.vram
        self.pgdisplay = pygame.Surface(size=GB_LCD_RES)
        self.palette = GB_LCD_PALETTE
        self.dots = 0

        self.mode = None

    def get_shade(self, palette_reg, shade_bits):
        ti = shade_bits * 2
        mask = pow(2, ti) * 3
        return self.palette[(palette_reg & mask) >> ti]

    def get_tile_row_BG(self, lcdc, px, py):
        lcdc_3 = BO.get_nth_bit(lcdc, 3)
        map_start = 0x1C00 if lcdc_3 else 0x1800
        lcdc_4 = BO.get_nth_bit(lcdc, 4)
        index = self.vram.get_byte_at(map_start + (py >> 3) * 32 + (px >> 3))
        offset = 0x0000 if lcdc_4 else 0x1000
        tile_offset = offset + index * 16 if lcdc_4 else offset + \
            BO.byte_twos_complement(index) * 16
        final_offset = tile_offset + (py % 8) * 2
        return self.vram.get_block_at(final_offset, 2)

    def get_tile_row_WINDOW(self, lcdc, px, py):
        pass

    def get_context(self):
        # palette register
        palette_reg = self.mem_ctl.io_registers[0xff47].value
        scx, scy = self.mem_ctl.io_registers[0xFF43].value, self.mem_ctl.io_registers[0xFF42].value
        ly, lyc = self.mem_ctl.io_registers[0xFF44].value, self.mem_ctl.io_registers[0xFF45].value
        lcd_control = self.mem_ctl.io_registers[0xFF40].value
        return palette_reg, (scx, scy), (ly, lyc), lcd_control

    def scanline_BG(self, preg, lcdc, ly, scy, scx):
        for x in range(GB_LCD_RES[0]):
            global_x = (x + scx) % (0xff + 1)
            global_y = (scy + ly) % (0xff + 1)
            pixel_i = global_x % 8
            tile_row = self.get_tile_row_BG(lcdc, global_x, global_y)
            shade_i = BO.get_pixel_2bpp(tile_row[0], tile_row[1], pixel_i)
            pixel = self.get_shade(preg, shade_i)
            self.pgdisplay.set_at((x, ly), pixel)

    def scanline_WINDOW(self, preg, lcdc, ly, scy, scx):
        pass

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

    def drawing_mode(self, ctx):
        self.enter_drawing_mode()
        palette_reg, (scx, scy), (ly, _), lcdc = ctx
        # scanline background
        self.scanline_BG(palette_reg, lcdc, ly, scy, scx)
        # scanline window
        self.scanline_WINDOW(palette_reg, lcdc, ly, scy, scx)
        self.dots += 172

    def OAM_scan(self, ctx):
        palette_reg, (scx, scy), (ly, _), lcdc = ctx
        self.enter_OAM()
        lcdc_1 = BO.get_nth_bit(lcdc, 1)
        if not lcdc_1:
            return
        self.mode = 2
        sprites = [self.mem_ctl.OAM[i: i + 4] for i in range(40)]
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