import pygame

from .sm83 import *
from .PPU import *
from .memory import *


def build_tile_row(lo_bits: int, hi_bits: int):
    """Return 2 bytes for one row (lo, hi)."""
    return lo_bits & 0xFF, hi_bits & 0xFF


def write_tile(vram: VRAM, tile_id: int, rows):
    """
    rows: list of 8 tuples (lo, hi) for each row.
    Writes into VRAM tile-data base (0x8000) which is offset 0x0000 in your VRAM object.
    """
    base = tile_id * 16
    for y in range(8):
        lo, hi = rows[y]
        vram.write_to(base + y * 2 + 0, lo)
        vram.write_to(base + y * 2 + 1, hi)


def make_checker_tile():
    """
    Checkerboard: alternates 0 and 3 each pixel. This is extremely sensitive to:
      - bit order (MSB leftmost)
      - any pixel-doubling (mosaic)
    We make shade=3 everywhere checker bits are 1 by setting both planes equal.
    """
    rows = []
    for y in range(8):
        # pattern 10101010 and 01010101 alternating by row
        bits = 0b10101010 if (y % 2 == 0) else 0b01010101
        rows.append(build_tile_row(bits, bits))  # lo=bits, hi=bits => shade 3 on bits=1
    return rows


def make_vertical_stripes_tile():
    """Vertical stripes: 11110000 / 00001111 alternating by row, easier to spot mirroring."""
    rows = []
    for y in range(8):
        bits = 0b11110000 if (y % 2 == 0) else 0b00001111
        rows.append(build_tile_row(bits, bits))
    return rows


def make_diagonal_tile():
    """A single pixel diagonal (shade 3) from left->right, very sensitive to bit order."""
    rows = []
    for y in range(8):
        # leftmost is bit7, so diagonal pixel at x=y => bit = 7-y
        bits = 1 << (7 - y)
        rows.append(build_tile_row(bits, bits))
    return rows


def clear_bg_map_to(vram: VRAM, tile_id: int):
    """Clear 32x32 BG map at 0x9800 (offset 0x1800) to a tile_id."""
    base = 0x1800
    for i in range(32 * 32):
        vram.write_to(base + i, tile_id & 0xFF)


def put_tiles_top_row(vram: VRAM, tile_ids):
    """Write given tile_ids across the first BG map row."""
    base = 0x1800  # 0x9800 map
    for x, tid in enumerate(tile_ids):
        vram.write_to(base + x, tid & 0xFF)


def main():
    pygame.init()

    mem = GBMemoryController(ext_ram=False)
    ppu = GbPPU(mem)

    screen = pygame.display.set_mode(GB_LCD_RES)
    pygame.display.set_caption("PPU-only Synthetic Tile Test")

    # --- Build 3 diagnostic tiles
    # tile 0: blank
    blank = [build_tile_row(0x00, 0x00) for _ in range(8)]
    write_tile(mem.vram, 0, blank)

    # tile 1: checkerboard
    write_tile(mem.vram, 1, make_checker_tile())

    # tile 2: vertical stripe blocks
    write_tile(mem.vram, 2, make_vertical_stripes_tile())

    # tile 3: diagonal single-pixel
    write_tile(mem.vram, 3, make_diagonal_tile())

    # --- BG map: clear to blank, then place pattern on the first row
    clear_bg_map_to(mem.vram, 0)
    # repeat [1,2,3] across the top row
    put_tiles_top_row(mem.vram, [1, 2, 3] * 10 + [1, 2])

    # --- Configure LCDC/scroll/palette
    # LCDC: LCD on, BG map 0x9800 (bit3=0), tile data 0x8000 (bit4=1), BG enable (bit0=1)
    mem.write_to(0xFF40, 0x91)
    mem.write_to(0xFF42, 0x00)  # SCY
    mem.write_to(0xFF43, 0x00)  # SCX
    mem.write_to(0xFF44, 0x00)  # LY
    mem.write_to(0xFF47, 0xE4)  # BGP identity mapping

    # --- Render one frame
    for _ in range(144):
        ppu.scanline()

    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.blit(ppu.pgdisplay, (0, 0))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()