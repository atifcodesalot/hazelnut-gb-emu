
from math import log
from .cartridge import Cartridge
from . import Register


class MBC1:
    def __init__(self, memctl, cartridge):
        self.memctl = memctl
        self.cartridge = cartridge

        # adjust rom and external ram size
        self.memctl.rom.resize(
            int(log(cartridge.rom_size, 2)))
        if cartridge.ram_size != 0:
            self.memctl.ext_ram.resize(
                int(log(cartridge.ram_size, 2)))
        #

        self.cart_regs = {
            0x2000: Register("RAM EN", 0, 0xFF, 8),
            0x4000: Register("ROM BANK NUM", 1, 0x1F, 5),
            0x6000: Register("RAM BANK/UPPER", 0, 0x03, 2),
            0x8000: Register("BANK MODE", 0, 0x01, 1)
        }

        self.memctl.rom_banks = cartridge.rom_banks
        self.memctl.ram_banks = cartridge.ram_banks

    def read(self, address, rom: bool):
        m = self.memctl
        mode = self.cart_regs[0x8000].value  # get mode
        if rom:
            offset = address & 0x3fff  # get the lower 14 bits
            bank_i = (address >> 14) & 1
            r2 = self.cart_regs[0x6000].value
            bank_num = (
                (r2 << 5) | self.cart_regs[0x4000].value) % m.rom_banks
            switched_addr_b1 = bank_num * 0x4000 + offset

            if mode == 0:
                if bank_i == 0:
                    return m.rom.get_byte_at(address)
                # bank 1
                return m.rom.get_byte_at(switched_addr_b1)

            # MBC1 mode 1 starts here
            if bank_i == 0:
                switched_addr_b0 = ((r2 << 5) %
                                    m.rom_banks * 0x4000) + offset
                return m.rom.get_byte_at(switched_addr_b0)

            # bank 1
            # logger.debug("MBC1 mode 1 read at address %s" % hex(address))
            switched_addr_b1 = bank_num * 0x4000 + offset
            return m.rom.get_byte_at(switched_addr_b1)

        # ram banked read starts here
        offset = address & 0x1fff

        if mode == 1 and m.rom_banks > 1:
            bank_num = self.cart_regs[0x6000].value % m.ram_banks
        else:
            bank_num = 0
            switched_addr = 0x2000 * bank_num + offset
            return m.ext_ram.get_byte_at(switched_addr)
        return m.ext_ram.get_byte_at(offset)

    def write(self, address, value):
        m = self.memctl
        if address < 0x2000:
            m.ext_ram_enabled = (value & 0x0F) == 0x0A
            return
        if address < 0x4000:
            # cant be 0
            low_5 = value & 0x1F
            if low_5 == 0:
                low_5 = 1
            self.cart_regs[0x4000].value = low_5
            return
        if address < 0x6000:
            self.cart_regs[0x6000].value = value & 0x3
            return
        if address < 0x8000:
            self.cart_regs[0x8000].value = value & 0x1
            return

        if 0xA000 < address < 0xC000:
            # ram banked write starts here
            mode = self.cart_regs[0x8000].value
            offset = address & 0x1fff
            if mode == 0:
                # logger.debug(
                #     "MBC1 ext ram mode 0 write at address %s" % hex(address))
                m.ext_ram.write_to(offset, value)
            else:
                bank_num = self.cart_regs[0x6000].value
                switched_addr = 0x2000 * bank_num + offset
                m.ext_ram.write_to(switched_addr, value)
