
from math import log
from .cartridge import Cartridge
from . import Register
import time


class MBC:
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

        self.memctl.rom_banks = cartridge.rom_banks
        self.memctl.ram_banks = cartridge.ram_banks


class MBC1(MBC):
    def __init__(self, memctl, cartridge: Cartridge):
        super().__init__(memctl, cartridge)
        self.cart_regs = {
            0x2000: Register("RAM EN", 0, 0xFF, 8),
            0x4000: Register("ROM BANK NUM", 1, 0x1F, 5),
            0x6000: Register("RAM BANK/UPPER", 0, 0x03, 2),
            0x8000: Register("BANK MODE", 0, 0x01, 1)
        }

    def handle_rom_banking(self, address, mode):
        m = self.memctl
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

    def handle_rom_write(self, address, value):
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

    def handle_ram_banking_read(self, address, mode):
        m = self.memctl
        offset = address & 0x1fff

        if mode == 1 and m.rom_banks > 1:
            bank_num = self.cart_regs[0x6000].value % m.ram_banks
        else:
            bank_num = 0
            switched_addr = 0x2000 * bank_num + offset
            return m.ext_ram.get_byte_at(switched_addr)
        return m.ext_ram.get_byte_at(offset)

    def handle_ram_banking_write(self, address, value):
        m = self.memctl
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

    def read(self, address, rom: bool):
        mode = self.cart_regs[0x8000].value  # get mode
        if rom:
            return self.handle_rom_banking(address, mode)

        return self.handle_ram_banking_read(address, mode)

    def write(self, address, value):
        if address < 0xA000:
            self.handle_rom_write(address, value)
            return

        # ram banked write starts here
        self.handle_ram_banking_write(address, value)


class MBC3(MBC):
    def __init__(self, memctl, cartridge: Cartridge):
        super().__init__(memctl, cartridge)
        self.cart_regs = {
            0x2000: Register("RAM \ TIMER EN", 0, 0xFF, 8),
            0x4000: Register("ROM BANK NUM", 1, 0x7F, 7),
            0x6000: Register("RAM BANK/RTC SEL", 0, 0x0C, 4),
            0x8000: Register("LATCH CLK", 0, 0x01, 1),
            0xA008: Register("RTC S", 0, 0xFF, 8),
            0xA009: Register("RTC M", 0, 0x3B, 6),
            0xA00A: Register("RTC H", 0, 0x17, 5),
            0xA00B: Register("RTC DL", 0, 0xFF, 8),
            0xA00C: Register("RTC DH", 0, 0x7, 3),
        }
        self.last_sample = 0
        self.seconds = 0
        self.RTC_read_enabled = False

    def start_RTC(self):
        self.start_seconds = time.monotonic()

    def sample_sec_diff(self):
        now = time.monotonic()
        elapsed = now - self.last_sample
        self.last_sample = now
        return elapsed

    def update_seconds(self):
        self.seconds += self.sample_sec_diff()

    def sample_seconds_reg(self):
        self.cart_regs[0xA008].value = self.seconds

    def sample_minutes_reg(self):
        self.cart_regs[0xA009].value = self.seconds // 60

    def sample_hours_reg(self):
        self.cart_regs[0xA00A].value = self.seconds // 3600

    def sample_days(self):
        days = self.seconds // 86400
        self.cart_regs[0xA00B].value = days & 0xFF
        self.cart_regs[0xA00C].value = days >> 8

    def handle_rom_banking(self, address):
        m = self.memctl
        offset = address & 0x3fff
        bank_i = (address >> 14) & 1
        if bank_i == 0:
            # no conversion, bank 0 is never bank switched in mbc3
            return m.rom.get_byte_at(address)
        # bank 1 handling starts here
        bank_num = self.cart_regs[0x4000].value
        return m.rom.get_byte_at(bank_num * 0x4000 + offset)

    def handle_rom_write(self, address, value):
        m = self.memctl
        if address < 0x2000:
            b = (value & 0x0F) == 0x0A
            m.ext_ram_enabled = b
            self.RTC_read_enabled = b
            return
        if address < 0x4000:
            # cant be 0, reset to 1 like mbc1
            if value == 0:
                value = 1
            self.cart_regs[0x4000].value = value
            return
        if address < 0x6000:
            self.cart_regs[0x6000].value = value % 0x0C
            return
        if address < 0x8000:
            self.cart_regs[0x8000].value = value & 0x1
            return

    def handle_ram_banking_read(self, address, sel):
        offset = address & 0x1fff
        return self.memctl.ext_ram.get_byte_at(
            sel * 0x2000 + offset)

    def handle_ram_banking_write(self, address, value, sel):
        offset = address & 0x1fff
        switched_addr = sel * 0x2000 + offset
        self.memctl.ext_ram.write_to(switched_addr, value)

    def handle_RTC_read(self, sel):
        self.update_seconds()
        if sel == 0x08:
            self.sample_seconds_reg()
            return self.cart_regs[0xA008].value
        if sel == 0x09:
            self.sample_minutes_reg()
            return self.cart_regs[0xA009].value
        if sel == 0x0A:
            self.sample_hours_reg()
            return self.cart_regs[0xA00A].value
        if sel == 0x0B or sel == 0x0C:
            self.sample_days()
            return self.cart_regs[0xA000 + sel].value

    def handle_RTC_write(self, sel, value):
        self.update_seconds()
        reg = self.cart_regs[0xA008]
        diff = value - reg.value
        if sel == 0x08:
            self.seconds += diff
        if sel == 0x09:
            self.seconds += diff * 60
        if sel == 0x0A:
            self.seconds += diff * 3600
        if sel == 0x0B or sel == 0x0C:
            self.seconds += diff * 86400
            
        reg.set_val(value)

    def read(self, address, rom: bool):
        if rom:
            return self.handle_rom_banking(address)

        sel = self.cart_regs[0x6000].value
        if sel < 0x08:
            # ram banking starts here
            return self.handle_ram_banking_read(address, sel)

        # rtc register reads start here
        if self.RTC_read_enabled:
            return self.handle_RTC_read(sel)
        # if RTC isn't enabled, do nothing

    def write(self, address, value):
        if address < 0xA000:
            self.handle_rom_write(address, value)
            return

        # ram banking, RTC writes start here
        sel = self.cart_regs[0x6000].value
        if sel < 0x08:
            # ram banking starts here
            return self.handle_ram_banking_write(address, value, sel)

        if self.RTC_read_enabled:
            self.handle_RTC_write(sel, value)
