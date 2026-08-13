
from math import log
from .cartridge import Cartridge
from . import Register
import time


class MBC:
    def __init__(self, memctl, cartridge: Cartridge):
        self.memctl = memctl
        self.cart = cartridge

        # adjust rom and external ram size
        self.memctl.rom.resize(
            int(log(cartridge.rom_size, 2)))
        if cartridge.ram_size != 0:
            self.memctl.ext_ram.resize(
                int(log(cartridge.ram_size, 2)))


class MBC1(MBC):
    def __init__(self, memctl, cartridge: Cartridge):
        super().__init__(memctl, cartridge)
        self.cart_regs = {
            0x2000: 0, # RAM EN
            0x4000: 1, # ROM BANK NUM
            0x6000: 0, # RAM BANK/UPPER
            0x8000: 0  # BANK MODE
        }

    def handle_rom_banking(self, address, mode):
        m = self.memctl
        bank_i = (address >> 14) & 1

        if mode == 0 and bank_i == 0:
            return m.rom.array[address]

        r2 = self.cart_regs[0x6000]
        bank_num = (
            (r2 << 5) | self.cart_regs[0x4000]) % self.cart.rom_banks
        offset = address & 0x3fff  # get the lower 14 bits
        switched_addr_b1 = bank_num * 0x4000 + offset

        # bank 1
        if mode == 0 and bank_i == 1:
            return m.rom.array[switched_addr_b1]

        # MBC1 mode 1 starts here
        if bank_i == 0:
            switched_addr_b0 = ((r2 << 5) %
                                self.cart.rom_banks * 0x4000) + offset
            return m.rom.array[switched_addr_b0]

        # bank 1, mode 1
        # logger.debug("MBC1 mode 1 read at address %s" % hex(address))
        return m.rom.array[switched_addr_b1]

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
            self.cart_regs[0x4000] = low_5
            return
        if address < 0x6000:
            self.cart_regs[0x6000] = value & 0x3
            return
        if address < 0x8000:
            self.cart_regs[0x8000] = value & 0x1
            return

    def handle_ram_banking_read(self, address, mode):
        m = self.memctl
        offset = address & 0x1fff

        if mode == 1:
            if self.cart.ram_banks > 0:
                bank_num = self.cart_regs[0x6000] % self.cart.ram_banks
            else:
                bank_num = 0
            switched_addr = 0x2000 * bank_num + offset
            return m.ext_ram.array[switched_addr]
        else:
            return m.ext_ram.array[offset]

    def handle_ram_banking_write(self, address, value):
        m = self.memctl
        mode = self.cart_regs[0x8000]
        offset = address & 0x1fff
        if mode == 1:
            if self.cart.ram_banks > 0:
                bank_num = self.cart_regs[0x6000] % self.cart.ram_banks
            else:
                bank_num = 0
            switched_addr = 0x2000 * bank_num + offset
            m.ext_ram.write_to(switched_addr, value)
        else:
            m.ext_ram.write_to(offset, value)

    def read(self, address, rom: bool):
        mode = self.cart_regs[0x8000] # get mode
        if rom:
            return self.handle_rom_banking(address, mode)

        return self.handle_ram_banking_read(address, mode)

    def write(self, address, value):
        if address < 0xA000:
            self.handle_rom_write(address, value)
            return

        # ram banked write starts here
        self.handle_ram_banking_write(address, value)


class MBC2(MBC):
    def __init__(self, memctl, cartridge):
        super().__init__(memctl, cartridge)
        self.cart_regs = {
            # technically there is one register
            0x4000: 0, # RAM EN
            0x4001: 0, # ROM BANK
        }

    def handle_ram_read(self, address):
        m = self.memctl

        # echo of half byte ram 15 times
        offset = (address - 0xA000) % 200

        return m.ext_ram.array[offset]

    def handle_ram_write(self, address, value):
        m = self.memctl
        # echo of half byte ram 15 times
        offset = (address - 0xA000) % 200
        m.ext_ram.array[offset] = value

    def handle_rom_read(self, address):
        if address < 0x4000:
            return self.memctl.rom.array[address]

        # banked read starts here
        offset = address & 0x3fff
        reg = self.cart_regs[0x4001]

        ln = reg & 0xF
        # bank number on the register can't be 0 as usual
        bank_num = ln if ln != 0 else 1
        bank_num %= self.cart.rom_banks
        return self.memctl.rom.array[bank_num * 0x4000 + offset]

    def read(self, address, rom: bool):
        if rom:
            return self.handle_rom_read(address)
        else:
            return self.handle_ram_read(address)

    def write(self, address, value):
        if address < 0x4000:
            self.handle_reg_write(address, value)
            return
        # ram write
        self.handle_ram_write(address, value)

    def handle_reg_write(self, address, value):
        reg_num = ((address >> 8) & 0xFF) & 1
        self.cart_regs[0x4000 + reg_num] = value
        # if bit 8 was clear, control extram enable
        if not reg_num:
            self.memctl.ext_ram_enabled = (value & 0xF == 0xA)


class MBC3(MBC):
    def __init__(self, memctl, cartridge: Cartridge):
        super().__init__(memctl, cartridge)
        self.cart_regs = {
            0x2000: 0, # RAM/TIMER EN
            0x4000: 1, # ROM BANK NUM
            0x6000: 0, # RAM BANK/RTC SEL
            0x8000: 0, # LATCH CLK
            0xA008: 0, # RTC S
            0xA009: 0, # RTC M
            0xA00A: 0, # RTC H
            0xA00B: 0, # RTC DL
            0xA00C: 0, # RTC DH
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
        self.cart_regs[0xA008] = self.seconds

    def sample_minutes_reg(self):
        self.cart_regs[0xA009] = self.seconds // 60

    def sample_hours_reg(self):
        self.cart_regs[0xA00A] = self.seconds // 3600

    def sample_days(self):
        days = self.seconds // 86400
        self.cart_regs[0xA00B] = days & 0xFF
        self.cart_regs[0xA00C] = days >> 8

    def handle_rom_banking(self, address):
        m = self.memctl
        offset = address & 0x3fff
        bank_i = (address >> 14) & 1
        if bank_i == 0:
            # no conversion, bank 0 is never bank switched in mbc3
            return m.rom.array[address]
        # bank 1 handling starts here
        bank_num = self.cart_regs[0x4000]
        return m.rom.array[bank_num * 0x4000 + offset]

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
            self.cart_regs[0x4000] = value
            return
        if address < 0x6000:
            self.cart_regs[0x6000] = value & 0x0F
            return
        if address < 0x8000:
            self.cart_regs[0x8000] = value & 1
            return

    def handle_ram_banking_read(self, address, sel):
        offset = address & 0x1fff
        return self.memctl.ext_ram.array[
            sel * 0x2000 + offset]

    def handle_ram_banking_write(self, address, value, sel):
        offset = address & 0x1fff
        switched_addr = sel * 0x2000 + offset
        self.memctl.ext_ram.write_to(switched_addr, value)

    def handle_RTC_read(self, sel):
        self.update_seconds()
        if sel == 0x08:
            self.sample_seconds_reg()
            return self.cart_regs[0xA008]
        if sel == 0x09:
            self.sample_minutes_reg()
            return self.cart_regs[0xA009]
        if sel == 0x0A:
            self.sample_hours_reg()
            return self.cart_regs[0xA00A]
        if sel == 0x0B or sel == 0x0C:
            self.sample_days()
            return self.cart_regs[0xA000 + sel]

    def handle_RTC_write(self, sel, value):
        self.update_seconds()
        reg = self.cart_regs[0xA008]
        diff = value - reg
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

        sel = self.cart_regs[0x6000]
        if sel < 0x04:
            # ram banking starts here
            return self.handle_ram_banking_read(address, sel)

        # rtc register reads start here
        if self.RTC_read_enabled:
            return self.handle_RTC_read(sel)
        # if RTC isn't enabled, read nothing
        return 0xFF

    def write(self, address, value):
        if address < 0xA000:
            self.handle_rom_write(address, value)
            return

        # ram banking, RTC writes start here
        sel = self.cart_regs[0x6000]
        if sel < 0x04:
            # ram banking starts here
            return self.handle_ram_banking_write(address, value, sel)

        if self.RTC_read_enabled:
            self.handle_RTC_write(sel, value)
         # if RTC isn't enabled, write nothing
         
         

class MBC5(MBC):
    def __init__(self, memctl, cartridge):
        super().__init__(memctl, cartridge)
        self.cart_regs = {
            0x2000: 0, # RAM EN
            0x3000: 0, # ROM 8 
            0x4000: 0, # ROM 9
            0x6000: 0 # RAM BANK NUM
        }
        
    def read(self, address, rom: bool):
        pass
    
    def write(self, address, value):
        pass

