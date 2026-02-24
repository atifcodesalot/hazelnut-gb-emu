
from dataclasses import dataclass


class RAM:
    def __init__(self, addressable_bits):
        self.size = pow(2, addressable_bits) - 1
        self.initialize()

    def initialize(self):
        self.array = bytearray(self.size)

    def address_range_guard(self, i):
        if i > self.size or i < 0:
            raise IndexError("Address out of bounds")

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
    def __init__(self, size):
        pass


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
        self.rom = ROM(None)
        self.ram = RAM(addressable_bits=13)  # 8KB
        self.vram = VRAM(addressable_bits=12)  # 4KB
        self.ext_ram = RAM(addressable_bits=13) if ext_ram else None
        self.hram = RAM(addressable_bits=7)  # 127B
        self.io_registers = {
            'JOYP': Register(name='JOYP', value=0, max_value=0xFF, bit_length=8),
            'IF': Register(name='IF', value=0, max_value=0xFF, bit_length=8),
            'IE': Register(name='IE', value=0, max_value=0xFF, bit_length=8),
            'SB': Register(name='SB', value=0, max_value=0xFF, bit_length=8),
            'SC': Register(name='SC', value=0, max_value=0xFF, bit_length=8),
            'SCX': Register(name='SCX', value=0, max_value=0xFF, bit_length=8),
            'SCY': Register(name='SCY', value=0, max_value=0xFF, bit_length=8)
        }

        self.memory_map = {
            range(0x0000,	0x3FFF+1): self.rom,
            range(0x4000,	0x7FFF+1): self.rom,
            range(0x8000,	0x9FFF+1): self.vram,
            range(0xA000,	0xBFFF+1): self.ext_ram,
            range(0xC000,	0xCFFF+1): self.ram,
            range(0xD000,	0xDFFF+1): self.ram,
            range(0xE000,	0xFDFF+1): None,  # unusable
            range(0xFE00,	0xFE9F+1): None,
            range(0xFEA0,	0xFEFF+1): None,  # unusable
            range(0xFF00,	0xFF01 + 1): self.io_registers['JOYP'],
            range(0xFF02,	0xFF02 + 1): self.io_registers['SB'],
            range(0xFF03,	0xFF03 + 1): self.io_registers['SC'],
            range(0xFF04,	0xFF07 + 1): None,  # timer registers
            range(0xFF0F,	0xFF0F + 1): self.io_registers['IF'],
            range(0xFF10,	0xFF3F + 1): None,  # sound registers
            range(0xFF40,	0xFF4B + 1): None,  # LCD control registers
            range(0xFF4C,	0xFF7F + 1): None,  # unused
            
            range(0xFF80,	0xFFFE+1): self.hram,
            range(0xFFFF,	0xFFFF+1): self.io_registers['IE']
        }

    def get_register(self, register_name: str):
        return self.io_registers[register_name].value

    def set_register(self, register_name: str, value):
        r = self.io_registers[register_name]
        r.value = value % (r.max_value + 1)

    def get_mem_device(self, loc):
        for r in self.memory_map.keys():
            if loc in r:
                mem_device = self.memory_map[r]
                break
        return mem_device

    def read_at(self, loc):
        mem_device = self.get_mem_device(loc)
        if mem_device is RAM:
            return mem_device.get_byte_at(loc)
        elif mem_device is Register:
            return mem_device.value

    def write_to(self, loc, byte):
        mem_device = self.get_mem_device(loc)
        if mem_device is RAM:
            mem_device.write_to(loc, byte)
        elif mem_device is Register:
            self.set_register(mem_device.name, byte)
