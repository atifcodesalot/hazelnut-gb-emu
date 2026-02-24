
""
from .memory import GBMemoryController
from .sm83 import ByteOperator as BO
import pygame


GB_LCD_RES = (160, 144)

GB_LCD_PALETTE = ("#1b2a09", "#0e450b", "#496b22", "#9a9e3f")


class GbPPU:
    def __init__(self, mem_ctl: GBMemoryController):
        self.mem_ctl = mem_ctl
        self.vram = self.mem_ctl.vram
        self.pgdisplay = pygame.Surface(size=(256, 256))
        self.palette = GB_LCD_PALETTE
        
    def scanline(self ):
        pass
    
    def oam_scan(self):
        pass
    
    