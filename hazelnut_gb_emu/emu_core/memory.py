from .auxiliary import BO
from .cartridge import Cartridge
from . import DMG_BOOTSEQ, CGB_BOOTSEQ
import math
from .MBCs import MBC1, MBC2, MBC3, MBC5


class RAM:
    def __init__(self, addressable_bits):
        self.size = pow(2, addressable_bits)
        self.initarr()

    def resize(self, new_addr_bits):
        self.size = pow(2, new_addr_bits)
        self.initarr()

    def initarr(self):
        self.array = bytearray(self.size)

    def address_range_guard(self, i):
        if i >= self.size or i < 0:
            raise IndexError(f"Address out of bounds: {hex(i)} for {self}.")

    # dont call it on hot paths
    def get_byte_at(self, i) -> int:
        self.address_range_guard(i)
        return self.array[i]

    def get_block_at(self, i, block_size) -> bytearray:
        # self.address_range_guard(i)
        return self.array[i : i + block_size]

    def write_to(self, i, byte):
        # self.address_range_guard(i)
        self.array[i] = byte

    def inc_byte_at(self, i):
        # self.address_range_guard(i)
        self.array[i] = (self.array[i] + 1) % 256

    def dec_byte_at(self, i):
        # self.address_range_guard(i)
        self.array[i] = (self.array[i] - 1) % 256

    def reset(self):
        self.initarr()


class ROM(RAM):
    def __init__(self, addressable_bits):
        super().__init__(addressable_bits=addressable_bits)

    def burn_from(self, cartridge: Cartridge):
        self.array[: len(cartridge.content)] = cartridge.content

    def write_to(self, i, byte, burning=False):
        if not burning:
            raise Exception("Cannot write to ROM.")
        super().write_to(i, byte)

    def inc_byte_at(self, i):
        raise Exception("Cannot write to ROM.")

    def dec_byte_at(self, i):
        raise Exception("Cannot write to ROM.")


class GBbootROM(ROM):
    def __init__(self):
        super().__init__(addressable_bits=8)
        self.array = DMG_BOOTSEQ.copy()


class CGBbootROM(ROM):
    def __init__(self):
        super().__init__(addressable_bits=11)
        self.array = CGB_BOOTSEQ.copy()


class VRAM(RAM):
    pass


class GBMemoryController:
    def __init__(self, gameboy, ext_ram=False, bank_switching=None, boot=GBbootROM):
        self.gameboy = gameboy
        self.TIMA_hertz_bit_index = [int(math.log(i)) for i in self.gameboy.TIMA_hertz]
        self.input_state = gameboy.input_state

        self.ext_ram_enabled = ext_ram
        self.bank_switching = bank_switching

        self.boot_enabled = True
        self.boot_rom = boot()
        self.bootmax = 0x00FF
        self.rom = ROM(addressable_bits=15)  # 32KB
        self.ram = RAM(addressable_bits=13)  # 8KB
        self.vram = VRAM(addressable_bits=13)  # 8KB
        self.ext_ram = RAM(addressable_bits=13)
        self.hram = RAM(addressable_bits=7)  # 127B
        self.OAM = bytearray(160)

        self.OAM_DMA_src = None
        self.OAM_DMA_counter = 0

        # Note: Audio, serial transfer registers are not implemented.
        self.io_registers = {
            # --- Joypad / Serial ---
            0xFF00: 0,
            0xFF01: 0,
            0xFF02: 0,
            # --- Timer ---
            0xFF04: 0,  # DIV
            0xFF05: 0,  # TIMA
            0xFF06: 0,  # TMA
            0xFF07: 0,  # TAC
            # --- Interrupt flag ---
            0xFF0F: 0,
            # --- Sound (stub for now) ---
            # FF10–FF3F
            **{addr: 0 for addr in range(0xFF10, 0xFF40)},
            # --- LCD / PPU ---
            0xFF40: 0,  # LCDC
            0xFF41: 0,  # STAT
            0xFF42: 0,  # SCY
            0xFF43: 0,  # SCX
            0xFF44: 0,  # LY
            0xFF45: 0,  # LYC
            0xFF46: 0,  # IMPORTANT: separate from BGP
            0xFF47: 0,  # BGP
            0xFF48: 0,  # OBP0
            0xFF49: 0,  # OBP1
            0xFF4A: 0,  # WY
            0xFF4B: 0,  # WX
            0xFF50: 0,  # Boot ROM disable register
            # --- Unused area FF4C–FF7F ---
            **{addr: 0 for addr in range(0xFF4C, 0xFF80)},
            # --- Interrupt Enable ---
            0xFFFF: 0,
        }

    def configure_bank_switching(self, cartridge: Cartridge):
        # ROM only
        if cartridge.type == 0:
            self.bank_switching = None

        # MBC1
        elif cartridge.type in [0x1, 0x2, 0x3]:
            self.bank_switching = True
            self.mbc = MBC1(self, cartridge)
        # MBC2
        elif cartridge.type in [0x5, 0x6]:
            self.bank_switching = True
            self.mbc = MBC2(self, cartridge)
        # MBC3 without RTC
        elif cartridge.type in [0x10, 0x11, 0x12, 0x13]:
            self.bank_switching = True
            self.mbc = MBC3(self, cartridge)

        # MBC5 without rumble motor
        elif cartridge.type in [0x19, 0x1A, 0x1B, 0x1E]:
            self.bank_switching = True
            self.mbc = MBC5(self, cartridge)

    def hex_dump(self, start, end):
        for i in range(start, end + 1):
            print(f"{hex(i)}: {hex(self.read_at(i))}")

    def handle_joypad_read(self):
        current_joyp = self.io_registers[0xFF00]

        # These must be active-low lower-nibble masks:
        # 1 = released, 0 = pressed
        buttons, dpad = BO.nibblesfrom_bytes(self.input_state)

        result = 0xC0 | (current_joyp & 0x30) | 0x0F

        # bit 4 == 0 means dpad selected
        if (current_joyp & 0x10) == 0:
            result = (result & 0xF0) | ((result & 0x0F) & dpad)

        # bit 5 == 0 means buttons selected
        if (current_joyp & 0x20) == 0:
            result = (result & 0xF0) | ((result & 0x0F) & buttons)

        return result

    def inc_TIMA(self):
        TIMA = self.io_registers[0xFF05]
        if BO.add_full_carry(TIMA, 1):
            TMA = self.io_registers[0xFF06]
            # wrap to TMA
            self.io_registers[0xFF05] = TMA
            IF = self.io_registers[0xFF0F]
            new_IF = BO.set_nth_bit(IF, 2)
            # request a timer interupt
            self.io_registers[0xFF0F] = new_IF
        else:
            self.inc_byte_at(0xFF05)

    def handle_DIV_write(self):
        TAC = self.io_registers[0xFF07]
        old_cycles = self.gameboy.cycles
        self.io_registers[0xFF04] = 0
        self.gameboy.cycles = 0
        mc = self.io_registers[0xFF07] & 0b11
        wbit = self.TIMA_hertz_bit_index[mc]  # watch bit
        old_bit = (old_cycles >> wbit) & 1
        if old_bit and (TAC & 0b100):
            self.inc_TIMA()

    def handle_TAC_write(self, v):
        old_TAC = self.io_registers[0xFF07]
        old_mc = old_TAC & 0b11
        self.io_registers[0xFF07] = v
        new_mc = v & 0b11
        neww = self.TIMA_hertz_bit_index[new_mc]  # new watch bit
        oldw = self.TIMA_hertz_bit_index[old_mc]  # old watch bit

        old_bit = (self.gameboy.cycles >> oldw) & 1
        new_bit = (self.gameboy.cycles >> neww) & 1
        # if the watched bit has fell
        if not (new_bit and v & 0b100) and (old_bit and old_TAC & 0b100):
            self.inc_TIMA()

    def read_at(self, loc) -> int:
        a = loc
        # --- ROM / Boot ROM overlay (hottest path: instruction fetch) ---
        if a < 0x8000:
            # Boot ROM overlays 0x0000-0x00FF while enabled
            if a <= self.bootmax and self.boot_enabled:
                # take the boot hole into account
                if 0x0100 < a < 0x0200:
                    return self.rom.array[a]
                # or boot_rom[a] if bytearray
                return self.boot_rom.array[a]
            if self.bank_switching is not None:
                # logger.debug(f"Bank switching read at address {hex(a)}")
                return self.mbc.read(a, rom=True)
            else:
                # logger.debug(f"Reading from ROM at address {hex(a)}")
                # simply get the byte from ROM
                return self.rom.array[a]

        # --- VRAM ---
        if a < 0xA000:
            return self.vram.array[a - 0x8000]

        # --- External RAM ---
        if a < 0xC000:
            if self.ext_ram_enabled:
                return self.mbc.read(a, rom=False)
            else:
                return 0xFF

        # --- WRAM (C000-DFFF) ---
        if a < 0xE000:
            return self.ram.array[a - 0xC000]

        # --- Echo RAM (E000-FDFF) mirror WRAM ---
        if a < 0xFE00:
            return self.ram.array[a - 0xE000]

        # --- OAM (FE00-FE9F)  ---
        if a < 0xFEA0:
            return self.OAM[a - 0xFE00]

        # --- Not usable (FEA0-FEFF) ---
        if a < 0xFF00:
            return 0xFF

        # --- IO / HRAM / IE ---
        if a < 0xFF80:
            if a == 0xFF00:
                return self.handle_joypad_read()

            if a == 0xFF01:
                # stub
                return 0xFF

            if a == 0xFF02:
                return 0

            return self.io_registers.get(a, 0xFF)

        # --- HRAM (FF80-FFFE) ---
        if a < 0xFFFF:
            return self.hram.array[a - 0xFF80]

        # --- IE (FFFF) ---
        return self.io_registers[0xFFFF]

    def write_to(self, loc: int, byte: int) -> None:
        a = loc
        v = byte & 0xFF  # always clamp to 8-bit

        # --- ROM / Boot ROM area ---
        # Normally ROM isn't writable (except MBC registers live in 0000-7FFF).
        if a < 0x8000:
            if self.bank_switching is None:
                # can't write to ROM if no bank switching is implemented
                return
            else:
                # write to MBC registers
                self.mbc.write(a, v)
                return

        # --- VRAM ---
        if a < 0xA000:
            self.vram.write_to(a - 0x8000, v)

        # --- External RAM ---
        if a < 0xC000:
            if self.ext_ram_enabled:
                self.mbc.write(a, v)
            return

        # --- WRAM (C000-DFFF) ---
        if a < 0xE000:
            self.ram.write_to(a - 0xC000, v)
            return

        # --- Echo RAM (E000-FDFF) ---
        if a < 0xFE00:  
            # mirror to C000-DDFF region
            self.ram.write_to(a - 0xE000, v)
            return

        # --- OAM (FE00-FE9F) ---
        # write to OAM (?)
        if a < 0xFEA0:
            self.OAM[a - 0xFE00] = v

        # --- Not usable (FEA0-FEFF) ---
        if a < 0xFF00:
            return

        # --- IO (FF00-FF7F) ---
        if a < 0xFF80:
            # Boot ROM disable register (FF50)
            if a == 0xFF50:
                # Any nonzero write disables boot ROM
                self.disable_boot_rom()
                return

            if a == 0xFF45:
                self.io_registers[0xFF45] = v
                self.gameboy.PPU.handle_LY_compare()
                return

            if a == 0xFF46:
                self.io_registers[a] = v
                self.gameboy.start_OAM_DMA()
                return

            if a == 0xFF00:
                # joyp write
                self.io_registers[0xFF00] = 0xC0 | (v & 0x30) | 0x0F
                return

            if a == 0xFF04:
                # div is always reset so no argument
                self.handle_DIV_write()
                return

            if a == 0xFF07:
                self.handle_TAC_write(v)
                return

            if a not in self.io_registers:
                # unimplemented/unused IO, ignore
                return

            self.io_registers[a] = v
            return

        # --- HRAM (FF80-FFFE) ---
        if a < 0xFFFF:
            self.hram.write_to(a - 0xFF80, v)
            return

        # --- IE (FFFF) ---
        self.io_registers[0xFFFF] = v

    def get_block_at(self, loc, byte_count):
        return [self.read_at(loc + i) for i in range(byte_count)]

    def dec_byte_at(self, loc):
        byte = self.read_at(loc)
        self.write_to(loc, (byte - 1) & 0xFF)

    def inc_byte_at(self, loc):
        byte = self.read_at(loc)
        self.write_to(loc, (byte + 1) & 0xFF)

    def disable_boot_rom(self):
        self.boot_enabled = False

    def __getitem__(self, key):
        return self.read_at(key)

    def __setitem__(self, key, value):
        self.write_to(key, value)

    def OAM_DMA_copy(self):
        addr = self.OAM_DMA_src + self.OAM_DMA_counter
        self.OAM[self.OAM_DMA_counter] = self.read_at(addr)
        self.OAM_DMA_counter += 1
        if self.OAM_DMA_counter == 160:
            self.gameboy.OAM_DMA_end()

    def reset(self):
        self.ext_ram_enabled = False
        self.bank_switching = None
        self.mbc = None
        self.disable_boot_rom()

        # reset memory units
        self.rom = ROM(addressable_bits=15)  # 32KB
        self.ram = RAM(addressable_bits=13)  # 8KB
        self.vram = VRAM(addressable_bits=13)  # 8KB
        self.ext_ram = RAM(addressable_bits=13)
        self.hram = RAM(addressable_bits=7)  # 127B
        self.OAM = bytearray(160)
        #

        # reset io registers
        for addr in self.io_registers:
            self.io_registers[addr] = 0


class CgbMemoryController(GBMemoryController):
    def __init__(self, gameboy, ext_ram=False, bank_switching=None, DMG_compat=False):
        super().__init__(gameboy, ext_ram, bank_switching, boot=CGBbootROM)
        # 128 byte palette ram
        self.obj_palette_ram = RAM(addressable_bits=6)
        self.bg_palette_ram = RAM(addressable_bits=6)

        self.bootmax = 0x08FF

        self.ram.resize(15)  # 32KB with additional 6 banks
        # can't be 0
        self.ram_bank = 1
        self.vram.resize(14)  # 16KB with additional bank
        self.vram_bank = 0

        self.init_gbc_regs()

        self.DMG_compat = DMG_compat

        self.hdma_src = 0
        self.hdma_dest = 0

    def init_gbc_regs(self):
        # CPU mode select
        self.io_registers[0xFF4C] = 0
        self.io_registers[0xFF4D] = 0

        # VRAM bank select register
        self.io_registers[0xFF4F] = 0

        # VRAM DMA SRC hi, low registers
        self.io_registers[0xFF51] = 0
        self.io_registers[0xFF52] = 0

        # VRAM DMA DEST hi, low registers
        self.io_registers[0xFF54] = 0
        self.io_registers[0xFF53] = 0

        # VRAM DMA control register
        self.io_registers[0xFF55] = 0

        # infrared comm port
        self.io_registers[0xFF56] = 0

        # palette access registers
        for i in range(4):
            self.io_registers[0xFF68 + i] = 0

        # Object priority mode
        self.io_registers[0xFF6C] = 0

        # WRAM bank select register
        self.io_registers[0xFF70] = 0

        # Undocumented, unknown registers
        for i in range(4):
            self.io_registers[0xFF72 + i] = 0

    def read_at(self, loc) -> int:
        if self.DMG_compat and not self.boot_enabled:
            return GBMemoryController.read_at(self, loc)
        a = loc
        # --- ROM / Boot ROM overlay (hottest path: instruction fetch) ---
        if a < 0x8000:
            # Boot ROM overlays 0x0000-0x00FF while enabled
            if a <= self.bootmax and self.boot_enabled:
                # take the boot hole into account
                if 0x0100 < a < 0x0200:
                    return self.rom.array[a]
                # or boot_rom[a] if bytearray
                return self.boot_rom.array[a]
            if self.bank_switching is not None:
                # logger.debug(f"Bank switching read at address {hex(a)}")
                return self.mbc.read(a, rom=True)
            else:
                # logger.debug(f"Reading from ROM at address {hex(a)}")
                # simply get the byte from ROM
                return self.rom.array[a]

        # --- VRAM ---
        if a < 0xA000:
            # take switching into account
            return self.vram.array[self.vram_bank << 13 | (a - 0x8000)]

        # --- External RAM ---
        if a < 0xC000:
            if self.ext_ram_enabled:
                return self.mbc.read(a, rom=False)
            else:
                return 0xFF

        # --- WRAM (C000-DFFF) ---
        if a < 0xE000:
            if a < 0xD000:
                return self.ram.array[a - 0xC000]
            # take switching into account
            # if the address is higher than D000
            return self.ram.array[a - 0xD000 + self.ram_bank * 0x1000]

        # --- Echo RAM (E000-FDFF) mirror WRAM ---
        if a < 0xFE00:
            if a < 0xF000:
                return self.ram.array[a - 0xE000]

            return self.ram.array[a - 0xF000 + self.ram_bank * 0x1000]

        # --- OAM (FE00-FE9F)  ---
        if a < 0xFEA0:
            return self.OAM[a - 0xFE00]

        # --- Not usable (FEA0-FEFF) ---
        if a < 0xFF00:
            return 0xFF

        # --- IO / HRAM / IE ---
        if a < 0xFF80:
            if a == 0xFF00:
                return self.handle_joypad_read()

            if a == 0xFF01:
                # stub
                return 0xFF

            if a == 0xFF02:
                return 0

            if a == 0xFF6B:
                # obj palette data read
                obpi = self.io_registers[0xFF6A]
                return self.obj_palette_ram.array[obpi & 0x3F]

            if a == 0xFF69:
                # bg palette data read
                bgpi = self.io_registers[0xFF68]
                return self.bg_palette_ram.array[bgpi & 0x3F]

            return self.io_registers.get(a, 0xFF)

        # --- HRAM (FF80-FFFE) ---
        if a < 0xFFFF:
            return self.hram.array[a - 0xFF80]

        # --- IE (FFFF) ---
        return self.io_registers[0xFFFF]

    def write_to(self, loc: int, byte: int) -> None:
        if self.DMG_compat and not self.boot_enabled:
            return GBMemoryController.write_to(self, loc, byte)
        a = loc
        v = byte & 0xFF  # always clamp to 8-bit

        # --- ROM / Boot ROM area ---
        # Normally ROM isn't writable (except MBC registers live in 0000-7FFF).
        if a < 0x8000:
            if self.bank_switching is None:
                # can't write to ROM if no bank switching is implemented
                return
            else:
                # write to MBC registers
                self.mbc.write(a, v)
                return

        # --- VRAM ---
        if a < 0xA000:
            self.vram.write_to(self.vram_bank << 13 | (a - 0x8000), v)
            return

        # --- External RAM ---
        if a < 0xC000:
            if self.ext_ram_enabled:
                self.mbc.write(a, v)
            return

        # --- WRAM (C000-DFFF) ---
        if a < 0xE000:
            if a < 0xD000:
                return self.ram.write_to(a - 0xC000, v)
            # wram bank switching
            return self.ram.write_to(a - 0xD000 + self.ram_bank * 0x1000, v)

        # --- Echo RAM (E000-FDFF) ---
        if a < 0xFE00:
            if a < 0xF000:
                self.ram.write_to(a - 0xE000, v)
            else:
                self.ram.write_to(a - 0xF000 + self.ram_bank * 0x1000, v)
            return

        # --- OAM (FE00-FE9F) ---
        # write to OAM (?)
        if a < 0xFEA0:
            self.OAM[a - 0xFE00] = v

        # --- Not usable (FEA0-FEFF) ---
        if a < 0xFF00:
            return

        # --- IO (FF00-FF7F) ---
        if a < 0xFF80:
            # Boot ROM disable register (FF50)
            if a == 0xFF70:
                self.io_registers[0xFF70] = v
                # update wram bank
                # 0 writes also point to bank 1
                self.ram_bank = v & 7 if v & 7 != 0 else 1

            if a == 0xFF6B:
                # obj palette data write
                self.io_registers[0xFF6B] = v
                obpi = self.io_registers[0xFF6A]
                self.obj_palette_ram.write_to(obpi & 0x3F, v)
                # auto increment
                self.io_registers[0xFF6A] = (
                    obpi & 0x80 | ((obpi & 0x7F) + (obpi >> 7 & 1))
                ) & 0xFF

            if a == 0xFF6A:
                # obj palette inxex data write
                self.io_registers[0xFF6A] = v

            if a == 0xFF69:
                # bg palette data write
                self.io_registers[0xFF69] = v
                bgpi = self.io_registers[0xFF68]
                self.bg_palette_ram.write_to(bgpi & 0x3F, v)
                # auto increment
                self.io_registers[0xFF68] = (
                    bgpi & 0x80 | ((bgpi & 0x7F) + (bgpi >> 7 & 1))
                ) & 0xFF

            if a == 0xFF68:
                # bg palette inxex data write
                self.io_registers[0xFF68] = v

            if a == 0xFF55:
                if self.gameboy.HBLANK_DMA and (v >> 7 & 1) == 0:
                    self.gameboy.HBLANK_DMA = False
                    self.io_registers[0xFF55] |= 0x80
                else:
                    self.io_registers[0xFF55] = v
                    self.gameboy.start_HDMA()
                return

            # hdma src hi
            if a == 0xFF51:
                self.hdma_src = (v << 8) | (self.hdma_src & 0x00FF)
            # hdma src low
            if a == 0xFF52:
                self.hdma_src = (self.hdma_src & 0xFF00) | (v & 0xF0)

            # hdma dest hi
            if a == 0xFF53:
                temp = (v << 8) | (self.hdma_dest & 0x00FF)
                self.hdma_dest = ((temp & 0x1FFF) >> 4) << 4

            # hdma dest low
            if a == 0xFF54:
                temp = (self.hdma_dest & 0xFF00) | v
                self.hdma_dest = ((temp & 0x1FFF) >> 4) << 4

            if a == 0xFF50:
                # Any nonzero write disables boot ROM
                self.disable_boot_rom()
                return

            if a == 0xFF45:
                self.io_registers[0xFF45] = v
                self.gameboy.PPU.handle_LY_compare()
                return

            if a == 0xFF46:
                self.io_registers[a] = v
                self.gameboy.start_OAM_DMA()
                return

            if a == 0xFF4C:
                # compatibility register
                self.io_registers[a] = v
                if v >> 2 & 1:
                    self.gameboy.start_DMG_compat_mode()

            if a == 0xFF4F:
                self.io_registers[a] = v
                # update wram bank
                self.vram_bank = v & 1

            if a == 0xFF00:
                # joyp write
                self.io_registers[0xFF00] = 0xC0 | (v & 0x30) | 0x0F
                return

            if a == 0xFF04:
                # div is always reset so no argument
                self.handle_DIV_write()
                return

            if a == 0xFF07:
                self.handle_TAC_write(v)
                return

            if a not in self.io_registers:
                # unimplemented/unused IO, ignore
                return

            self.io_registers[a] = v
            return

        # --- HRAM (FF80-FFFE) ---
        if a < 0xFFFF:
            self.hram.write_to(a - 0xFF80, v)
            return

        # --- IE (FFFF) ---
        self.io_registers[0xFFFF] = v

    # one 16 byte copy of HDMA
    def HDMA_copy(self):
        hdmactl = self.io_registers[0xFF55]

        copy = self.get_block_at(self.hdma_src, 16)
        vramstart = 0x2000 * self.vram_bank + self.hdma_dest
        self.vram.array[vramstart : vramstart + 16] = copy

        # update remaining lenth on hdma control
        remaining = hdmactl & 0x7F
        remaining = (remaining - 1) & 0xFF
        self.io_registers[0xFF55] = remaining

        # update internal counters
        self.hdma_src = (self.hdma_src + 0x10) & 0xFFFF
        self.hdma_dest = (self.hdma_dest + 0x10) & 0x1FFF

    def reset(self):
        super().reset()
        self.ram.resize(15)
        self.vram.resize(14)
        self.bg_palette_ram.reset()
        self.obj_palette_ram.reset()
        self.hdma_src = 0
        self.hdma_dest = 0
