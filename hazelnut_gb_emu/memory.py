
from dataclasses import dataclass


class RAM:
    def __init__(self, addressable_bits):
        self.size = pow(2, addressable_bits)
        self.initialize()

    def initialize(self):
        self.array = bytearray(self.size)

    def address_range_guard(self, i):
        if i >= self.size or i < 0:
            raise IndexError(f"Address out of bounds: {hex(i)} for {self}.")

    def get_byte_at(self, i) -> int:
        self.address_range_guard(i)
        return self.array[i]

    def get_block_at(self, i, block_size) -> bytearray:
        self.address_range_guard(i)
        return self.array[i: i+block_size]

    def write_to(self, i, byte):
        self.address_range_guard(i)
        self.array[i] = byte

    def inc_byte_at(self, i):
        self.address_range_guard(i)
        self.array[i] = (self.array[i] + 1) % 256

    def dec_byte_at(self, i):
        self.address_range_guard(i)
        self.array[i] = (self.array[i] - 1) % 256


class ROM(RAM):
    def __init__(self, addressable_bits):
        super().__init__(addressable_bits=addressable_bits)

    def burn_from(self, rom_loader):
        self.array[:len(rom_loader.prog)] = rom_loader.prog

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
    def __init__(self, addressable_bits):
        super().__init__(addressable_bits)


@dataclass
class Register:
    name: str
    value: int
    max_value: int
    bit_length: int

    def __repr__(self):
        return str(self.value)


class GBMemoryController:
    def __init__(self, ext_ram=False):
        self.boot_enabled = True
        self.boot_rom = GBbootROM()
        self.rom = ROM(addressable_bits=16)  # 32KB
        self.ram = RAM(addressable_bits=13)  # 8KB
        self.vram = VRAM(addressable_bits=13)  # 8KB
        self.ext_ram = RAM(addressable_bits=13) if ext_ram else None
        self.hram = RAM(addressable_bits=7)  # 127B
        def r8bit(name): return Register(
            name=name, value=0, max_value=0xFF, bit_length=8)
        # Note: Audio, serial transfer registers are not implemented.
        self.io_registers = {
            'JOYP': r8bit('JOYP'),
            'IF': r8bit('IF'),
            'IE': r8bit('IE'),
            'SB': r8bit('SB'),
            'SC': r8bit('SC'),
            'SCX': r8bit('SCX'),
            'SCY': r8bit('SCY'),
            'LY': r8bit('LY'),
            'LYC': r8bit('LYC'),
            'LCDC': r8bit('LCDC'),
            'WY': r8bit('WY'),
            'WX': r8bit('WX'),
            'STAT': r8bit('STAT'),
            'BGP': r8bit('BGP'),
            'OBP0': r8bit('OBP0'),
            'OBP1': r8bit('OBP1'),
        }

        self.memory_map = {
            range(0x0000,	0x00FF+1): self.boot_rom,
            range(0x0000,	0x7FFF+1): self.rom,
            range(0x8000,	0x9FFF+1): self.vram,
            range(0xA000,	0xBFFF+1): self.ext_ram,
            range(0xC000,	0xDFFF+1): self.ram,
            # unusable echo ram
            range(0xE000,	0xFDFF+1): None,
            #
            range(0xFE00,	0xFE9F+1): "unimplemented",  # OAM
            # nintendo prohibits access to this region.
            range(0xFEA0,	0xFEFF+1): None,
            #
            range(0xFF00,	0xFF01 + 1): self.io_registers['JOYP'],
            range(0xFF02,	0xFF02 + 1): self.io_registers['SB'],
            range(0xFF03,	0xFF03 + 1): self.io_registers['SC'],
            range(0xFF04,	0xFF07 + 1): "unimplemented",  # timer registers
            range(0xFF0F,	0xFF0F + 1): self.io_registers['IF'],
            range(0xFF10,	0xFF3F + 1): "unimplemented",  # sound registers
            # LCD control registers
            range(0xFF40,	0xFF40 + 1): self.io_registers["LCDC"],
            # LCD status register
            range(0xFF41,	0xFF41 + 1): self.io_registers["STAT"],
            # scroll registers
            range(0xFF42,	0xFF42 + 1): self.io_registers["SCY"],
            range(0xFF43,	0xFF43 + 1): self.io_registers["SCX"],
            # LCD Y position register
            range(0xFF44,	0xFF44 + 1): self.io_registers["LY"],
            # LCD Y compare register
            range(0xFF45,	0xFF45 + 1): self.io_registers["LYC"],
            # Background palette register
            range(0xFF46,	0xFF47 + 1): self.io_registers["BGP"],
            # Object palette registers
            range(0xFF48,	0xFF48 + 1): self.io_registers["OBP0"],
            range(0xFF49,	0xFF49 + 1): self.io_registers["OBP1"],
            # Window Y position register
            range(0xFF4A,	0xFF4A + 1): self.io_registers["WY"],
            # Window X position register
            range(0xFF4B,	0xFF4B + 1): self.io_registers["WX"],
            range(0xFF4C,	0xFF7F + 1): "unimplemented",  # unused

            range(0xFF80,	0xFFFE+1): self.hram,
            range(0xFFFF,	0xFFFF+1): self.io_registers['IE']
        }

    def hex_dump(self, start, end):
        for i in range(start, end + 1):
            print(f"{hex(i)}: {hex(self.read_at(i))}")

    def get_register(self, register_name: str):
        return self.io_registers[register_name].value

    def unused_guard(self, r):
        if self.memory_map[r] is None:
            raise Exception(f"Address {r} is in an unusable memory region.")

    def set_register(self, register_name: str, value):
        r = self.io_registers[register_name]
        r.value = value % (r.max_value + 1)

    def get_mem_device(self, loc):
        for r in self.memory_map.keys():
            if loc in r:
                self.unused_guard(r)
                mem_device = self.memory_map[r]
                offset = loc - r.start
                break
        else:
            raise IndexError(f"Address {loc} is out of bounds.")
        return mem_device, offset

    def read_at(self, loc):
        if loc == 0xFF44:
            return 0x90
        mem_device, offset = self.get_mem_device(loc)
        if mem_device == "unimplemented":
            return 0xFF
        t = type(mem_device)
        if t in [RAM, ROM, VRAM, GBbootROM]:
            return mem_device.get_byte_at(offset)
        elif t is Register:
            return mem_device.value
        else:
            raise Exception(
                f"Invalid memory device {type(mem_device)} at address {hex(offset)}.")

    def write_to(self, loc, byte):
        mem_device, offset = self.get_mem_device(loc)
        if mem_device == "unimplemented":
            return
        t = type(mem_device)
        if t in [RAM, VRAM]:
            # print(f"writing {hex(byte)} to {mem_device} at address {hex(offset)}")
            mem_device.write_to(offset, byte)
        elif t is Register:
            self.set_register(mem_device.name, byte)
        else:
            raise Exception(
                f"Invalid memory device {type(mem_device)} at address {hex(offset)}.")
            
    def get_block_at(self, loc, byte_count):
        mem_device, offset = self.get_mem_device(loc)
        return mem_device.get_block_at(offset, byte_count)
    
    def dec_byte_at(self, loc):
        mem_device, offset = self.get_mem_device(loc)
        t = type(mem_device)
        if t in [RAM, VRAM]:
            mem_device.dec_byte_at(offset)
        elif t is Register:
            self.set_register(mem_device.name, self.get_register(mem_device.name) - 1)
        else:
            raise Exception(
                f"Invalid memory device {t} at address {hex(offset)} for dec operation.")
    
    def inc_byte_at(self, loc):
        mem_device, offset = self.get_mem_device(loc)
        t = type(mem_device)
        if t in [RAM, VRAM]:
            mem_device.inc_byte_at(offset)
        elif t is Register:
            self.set_register(mem_device.name, self.get_register(mem_device.name) + 1)
        else:
            raise Exception(
                f"Invalid memory device {t} at address {hex(offset)} for inc operation.")

    def disable_boot_rom(self):
        self.memory_map[range(0x0000,	0x00FF+1)] = self.rom

    def __getitem__(self, key):
        return self.read_at(key)

    def __setitem__(self, key, value):
        self.write_to(key, value)
