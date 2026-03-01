

from .memory import GBMemoryController
from .sm83 import ByteOperator as BO
import pygame


GB_LCD_RES = (160, 144)

GB_LCD_PALETTE = ("#9a9e3f", "#496b22",  "#0e450b", "#1b2a09")


class GbPPU:
    def __init__(self, mem_ctl: GBMemoryController):
        self.mem_ctl = mem_ctl
        self.vram = self.mem_ctl.vram
        self.pgdisplay = pygame.Surface(size=GB_LCD_RES)
        self.palette = GB_LCD_PALETTE
        self.dots = 0
        
        self.vblank = False

    def get_shade(self, palette_reg, shade_bits):
        if shade_bits != 0:
            print(shade_bits, "shade bits" + "-"*50)
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
        palette_reg = self.mem_ctl.read_at(0xff47)  # palette register
        scx, scy = self.mem_ctl.read_at(0xFF43), self.mem_ctl.read_at(0xFF42)
        ly, lcy = self.mem_ctl.read_at(0xFF44), self.mem_ctl.read_at(0xFF45)
        lcd_control = self.mem_ctl.read_at(0xFF40)
        return palette_reg, (scx, scy), (ly, lcy), lcd_control

    def scanline_BG(self, preg, lcdc, ly, scy, scx):
        for x in range(GB_LCD_RES[0]):
            global_x = (x + scx) % (0xff + 1)
            global_y = (scy + ly) % (0xff + 1)
            pixel_i = global_x % 8
            tile_row =  self.get_tile_row_BG(lcdc, global_x, global_y)
            shade_i = BO.get_pixel_2bpp(tile_row[0], tile_row[1], pixel_i)
            pixel = self.get_shade(preg, shade_i)
            if pixel != self.palette[0]:    
                print(pixel, "pixel", x, ly)
            self.pgdisplay.set_at((x, ly), pixel)
    
    def scanline_WINDOW(self, preg, lcdc, ly, scy, scx):
        pass

    def OAM_scan(self):
        pass

    def scanline(self):
        # update per scanline
        palette_reg, (scx, scy), (ly, lcy), lcdc = self.get_context()
        
        lcdc_7 = BO.get_nth_bit(lcdc, 7)
        if not lcdc_7:  # if LCD is off, skip to next scanline
            self.mem_ctl.write_to(0xFF44, ly + 1)
            return
        
        if self.vblank:
            if ly < 153:
                self.mem_ctl.write_to(0xFF44, ly + 1)
                return
            else: 
                self.vblank = False
                self.mem_ctl.write_to(0xFF44, 0)
                return
        
        # scanline background
        self.scanline_BG(palette_reg, lcdc, ly, scy, scx)
        # scanline window
        #self.scanline_WINDOW(palette_reg, lcdc, ly, scy, scx)
        # scanline object attr memory
        self.OAM_scan()
        self.mem_ctl.write_to(0xFF44, ly + 1)  # update LY register

        if ly + 1 == GB_LCD_RES[1]:  # if we just finished the last visible scanline
            # request VBlank interrupt
            self.vblank = True
            ie = self.mem_ctl.read_at(0xFF0F)
            ie |= 1
            self.mem_ctl.write_to(0xFF0F, ie)
            self.mem_ctl.write_to(0xFF44, ly + 1)
            
        
