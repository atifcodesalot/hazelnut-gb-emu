
from .aux import BO
from .cartridge import Cartridge
from . import logger
from . import IOhole, Register
import math
from .MBCs import MBC1, MBC3


class RAM:
    def __init__(self, addressable_bits):
        self.size = pow(2, addressable_bits)
        self.initialize()
        
    def resize(self, new_addr_bits):
        self.size = pow(2, new_addr_bits)
        self.initialize()

    def initialize(self):
        self.array = bytearray(self.size)

    def address_range_guard(self, i):
        if i >= self.size or i < 0:
            raise IndexError(f"Address out of bounds: {hex(i)} for {self}.")

    def get_byte_at(self, i) -> int:
        # self.address_range_guard(i)
        return self.array[i]

    def get_block_at(self, i, block_size) -> bytearray:
        # self.address_range_guard(i)
        return self.array[i: i+block_size]

    def write_to(self, i, byte):
        # self.address_range_guard(i)
        self.array[i] = byte

    def inc_byte_at(self, i):
        # self.address_range_guard(i)
        self.array[i] = (self.array[i] + 1) % 256

    def dec_byte_at(self, i):
        # self.address_range_guard(i)
        self.array[i] = (self.array[i] - 1) % 256


class ROM(RAM):
    def __init__(self, addressable_bits):
        super().__init__(addressable_bits=addressable_bits)

    def burn_from(self, cartridge: Cartridge):
        self.array[:len(cartridge.content)] = cartridge.content

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
        self.array = bytearray([
            0x31, 0xFE, 0xFF, 0xAF, 0x21, 0xFF, 0x9F, 0x32, 0xCB, 0x7C, 0x20, 0xFB, 0x21, 0x26, 0xFF, 0x0E,
            0x11, 0x3E, 0x80, 0x32, 0xE2, 0x0C, 0x3E, 0xF3, 0xE2, 0x32, 0x3E, 0x77, 0x77, 0x3E, 0xFC, 0xE0,
            0x47, 0x11, 0x04, 0x01, 0x21, 0x10, 0x80, 0x1A, 0xCD, 0x95, 0x00, 0xCD, 0x96, 0x00, 0x13, 0x7B,
            0xFE, 0x34, 0x20, 0xF3, 0x11, 0xD8, 0x00, 0x06, 0x08, 0x1A, 0x13, 0x22, 0x23, 0x05, 0x20, 0xF9,
            0x3E, 0x19, 0xEA, 0x10, 0x99, 0x21, 0x2F, 0x99, 0x0E, 0x0C, 0x3D, 0x28, 0x08, 0x32, 0x0D, 0x20,
            0xF9, 0x2E, 0x0F, 0x18, 0xF3, 0x67, 0x3E, 0x64, 0x57, 0xE0, 0x42, 0x3E, 0x91, 0xE0, 0x40, 0x04,
            0x1E, 0x02, 0x0E, 0x0C, 0xF0, 0x44, 0xFE, 0x90, 0x20, 0xFA, 0x0D, 0x20, 0xF7, 0x1D, 0x20, 0xF2,
            0x0E, 0x13, 0x24, 0x7C, 0x1E, 0x83, 0xFE, 0x62, 0x28, 0x06, 0x1E, 0xC1, 0xFE, 0x64, 0x20, 0x06,
            0x7B, 0xE2, 0x0C, 0x3E, 0x87, 0xE2, 0xF0, 0x42, 0x90, 0xE0, 0x42, 0x15, 0x20, 0xD2, 0x05, 0x20,
            0x4F, 0x16, 0x20, 0x18, 0xCB, 0x4F, 0x06, 0x04, 0xC5, 0xCB, 0x11, 0x17, 0xC1, 0xCB, 0x11, 0x17,
            0x05, 0x20, 0xF5, 0x22, 0x23, 0x22, 0x23, 0xC9, 0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B,
            0x03, 0x73, 0x00, 0x83, 0x00, 0x0C, 0x00, 0x0D, 0x00, 0x08, 0x11, 0x1F, 0x88, 0x89, 0x00, 0x0E,
            0xDC, 0xCC, 0x6E, 0xE6, 0xDD, 0xDD, 0xD9, 0x99, 0xBB, 0xBB, 0x67, 0x63, 0x6E, 0x0E, 0xEC, 0xCC,
            0xDD, 0xDC, 0x99, 0x9F, 0xBB, 0xB9, 0x33, 0x3E, 0x3C, 0x42, 0xB9, 0xA5, 0xB9, 0xA5, 0x42, 0x3C,
            0x21, 0x04, 0x01, 0x11, 0xA8, 0x00, 0x1A, 0x13, 0xBE, 0x20, 0xFE, 0x23, 0x7D, 0xFE, 0x34, 0x20,
            0xF5, 0x06, 0x19, 0x78, 0x86, 0x23, 0x05, 0x20, 0xFB, 0x86, 0x20, 0xFE, 0x3E, 0x01, 0xE0, 0x50
        ])


class VRAM(RAM):
    pass


hole = IOhole(0xFF)


class GBMemoryController:
    def __init__(self, gameboy, ext_ram=False, bank_switching=None):
        self.gameboy = gameboy
        self.TIMA_hertz_bit_index = [int(math.log(i))
                                     for i in self.gameboy.TIMA_hertz]
        self.input_state = gameboy.input_state

        self.ext_ram_enabled = ext_ram
        self.bank_switching = bank_switching

        self.boot_enabled = True
        self.boot_rom = GBbootROM()
        self.rom = ROM(addressable_bits=15)  # 32KB
        self.ram = RAM(addressable_bits=13)  # 8KB
        self.vram = VRAM(addressable_bits=13)  # 8KB
        self.ext_ram = RAM(addressable_bits=13)
        self.hram = RAM(addressable_bits=7)  # 127B
        self.OAM = bytearray(160)
        def r8bit(name): return Register(
            name=name, value=0, max_value=0xFF, bit_length=8)
        # Note: Audio, serial transfer registers are not implemented.
        self.io_registers = {
            # --- Joypad / Serial ---
            0xFF00: r8bit('JOYP'),
            0xFF01: r8bit('SB'),
            0xFF02: r8bit('SC'),

            # --- Timer ---
            0xFF04: r8bit('DIV'),
            0xFF05: r8bit('TIMA'),
            0xFF06: r8bit('TMA'),
            0xFF07: r8bit('TAC'),

            # --- Interrupt flag ---
            0xFF0F: r8bit('IF'),

            # --- Sound (stub for now) ---
            # FF10–FF3F
            **{addr: r8bit(f'SND_{hex(addr)}') for addr in range(0xFF10, 0xFF40)},

            # --- LCD / PPU ---
            0xFF40: r8bit('LCDC'),
            0xFF41: r8bit('STAT'),
            0xFF42: r8bit('SCY'),
            0xFF43: r8bit('SCX'),
            0xFF44: r8bit('LY'),
            0xFF45: r8bit('LYC'),
            0xFF46: r8bit('DMA'),   # IMPORTANT: separate from BGP
            0xFF47: r8bit('BGP'),
            0xFF48: r8bit('OBP0'),
            0xFF49: r8bit('OBP1'),
            0xFF4A: r8bit('WY'),
            0xFF4B: r8bit('WX'),
            0xFF50: r8bit('BOOT'),

            # --- Unused area FF4C–FF7F ---
            **{addr: r8bit(f'UNUSED_{hex(addr)}') for addr in range(0xFF4C, 0xFF80)},

            # --- Interrupt Enable ---
            0xFFFF: r8bit('IE'),
        }

    def configure_bank_switching(self, cartridge: Cartridge):
        # ROM only
        if cartridge.type == 0:
            self.bank_switching = None

        # MBC1
        elif cartridge.type in [0x1, 0x2, 0x3]:
            self.bank_switching = True
            self.mbc = MBC1(self, cartridge)
        elif cartridge.type in [0x11, 0x12, 0x13]:
            self.bank_switching = True
            self.mbc = MBC3(self, cartridge)

    def hex_dump(self, start, end):
        for i in range(start, end + 1):
            print(f"{hex(i)}: {hex(self.read_at(i))}")

    def set_register(self, reg_loc: str, value):
        r = self.io_registers[reg_loc]
        r.value = value % (r.max_value + 1)

    def handle_joypad_read(self):
        current_joyp = self.io_registers[0xFF00].value

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
        TIMA = self.io_registers[0xFF05].value
        if BO.add_full_carry(TIMA, 1):
            TMA = self.io_registers[0xFF06].value
            # wrap to TMA
            self.io_registers[0xFF05].value = TMA
            IF = self.io_registers[0xFF0F].value
            new_IF = BO.set_nth_bit(IF, 2)
            # request a timer interupt
            self.io_registers[0xFF0F].value = new_IF
        else:
            self.inc_byte_at(0xFF05)

    def handle_DIV_write(self):
        TAC = self.io_registers[0xFF07].value
        old_cycles = self.gameboy.cycles
        self.io_registers[0xFF04].value = 0
        self.gameboy.cycles = 0
        mc = self.io_registers[0xFF07].value & 0b11
        wbit = self.TIMA_hertz_bit_index[mc]  # watch bit
        old_bit = (old_cycles >> wbit) & 1
        if old_bit and (TAC & 0b100):
            self.inc_TIMA()

    def handle_TAC_write(self, v):
        TAC = self.io_registers[0xFF07]
        old_TAC = TAC.value
        old_mc = TAC.value & 0b11
        TAC.value = v
        new_mc = v & 0b11
        neww = self.TIMA_hertz_bit_index[new_mc]  # new watch bit
        oldw = self.TIMA_hertz_bit_index[old_mc]  # old watch bit

        old_bit = (self.gameboy.cycles >> oldw) & 1
        new_bit = (self.gameboy.cycles >> neww) & 1
        # if the watched bit has fell
        if not (new_bit and v & 0b100) and (old_bit and old_TAC & 0b100):
            self.inc_TIMA()

    def read_at(self, loc):
        a = loc
        # --- ROM / Boot ROM overlay (hottest path: instruction fetch) ---
        if a < 0x8000:
            # Boot ROM overlays 0x0000-0x00FF while enabled
            if a <= 0x00FF and self.boot_enabled:
                # or boot_rom[a] if bytearray
                return self.boot_rom.get_byte_at(a)
            if self.bank_switching is not None:
                # logger.debug(f"Bank switching read at address {hex(a)}")
                return self.mbc.read(a, rom=True)
            else:
                # logger.debug(f"Reading from ROM at address {hex(a)}")
                # simply get the byte from ROM
                return self.rom.get_byte_at(a)

        # --- VRAM ---
        if a < 0xA000:
            return self.vram.get_byte_at(a - 0x8000)

        # --- External RAM ---
        if a < 0xC000:
            if self.ext_ram_enabled:
                return self.mbc.read(a, rom=False)
            else:
                return 0xFF

        # --- WRAM (C000-DFFF) ---
        if a < 0xE000:
            return self.ram.get_byte_at(a - 0xC000)

        # --- Echo RAM unusable yet (E000-FDFF) ---
        if a < 0xFE00:
            return 0xFF

        # --- OAM (FE00-FE9F) marked unimplemented in your map ---
        if a < 0xFEA0:
            return self.OAM[a - 0xFE00]

        # --- Not usable (FEA0-FEFF) ---
        if a < 0xFF00:
            return 0xFF

        # --- IO / HRAM / IE ---
        if a < 0xFF80:
            if a == 0xFF00:
                return self.handle_joypad_read()

            return self.io_registers.get(a, hole).value

        # --- HRAM (FF80-FFFE) ---
        if a < 0xFFFF:
            return self.hram.get_byte_at(a - 0xFF80)

        # --- IE (FFFF) ---
        return self.io_registers[0xFFFF].value

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
        # SOme emulators mark this as None/unusable. Real HW mirrors C000-DDFF.
        # Choose one behavior. For speed + later correctness, mirroring is nice:
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
                # Any nonzero write disables boot ROM on DMG
                self.disable_boot_rom()
                return

            if a == 0xFF46:
                self.gameboy.start_DMA()

            if a == 0xFF00:
                # joyp write
                self.io_registers[0xFF00].value = 0xC0 | (v & 0x30) | 0x0F
                return

            if a == 0xFF04:
                # div is reset always so no argument
                self.handle_DIV_write()
                return

            if a == 0xFF07:
                self.handle_TAC_write(v)
                return

            reg = self.io_registers.get(a)
            if reg is None:
                # unimplemented/unused IO, ignore
                return

            # DMA (FF46) often triggers a transfer;
            # later when implementing DMA, hook it here.
            reg.value = (v) % 256
            return

        # --- HRAM (FF80-FFFE) ---
        if a < 0xFFFF:
            self.hram.write_to(a - 0xFF80, v)
            return

        # --- IE (FFFF) ---
        reg_ie = self.io_registers.get(0xFFFF) or self.io_registers.get("IE")
        if reg_ie is None:
            raise KeyError("IE register not found in io_registers")
        reg_ie.value = v

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
