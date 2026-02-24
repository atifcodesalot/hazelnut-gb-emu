
from .loader import *
from . import logger
from .memory import *

# from loader import *


class PairRegister:
    def __init__(self, name, hi_reg, low_reg):
        self.name = name
        self.hi = hi_reg
        self.low = low_reg
        self.max_value = 0xFFFF
        self.bit_length = 16

    @property
    def value(self):
        return ((self.hi.value & 0xFF) << 8) | (self.low.value & 0xFF)

    @value.setter
    def value(self, v):
        v &= 0xFFFF
        self.hi.value = (v >> 8) & 0xFF
        self.low.value = v & 0xFF

    def __repr__(self):
        return str(self.value)


class CPU:
    def __init__(self, peripherals, general_registers: list[Register], flags, PC, SP=None):
        self.peripherals = peripherals
        self.register_names = list(general_registers.keys()) + ["PC", "SP"]
        self.flag_names = flags.keys()
        self.__dict__.update(general_registers)
        self.flags = flags
        self.PC = PC
        self.SP = SP
        self.machine_cycles = 0

    def add_cycles(self, cycles):
        self.machine_cycles += cycles

    # very fast, can be used for every register fetching and writing
    # also handles register increment and decrement if needed
    def register_guard(self, register_name):
        if register_name not in self.register_names:
            raise ValueError(f"Invalid register name: {register_name}")

    def fetch_ins(self, memory):
        ins = memory[self.PC.value]
        self.inc_register('PC')
        return ins

    def dump_state(self):
        return f"PC: {hex(self.PC)}, SP: {hex(self.SP)}, general_registers: {self.__dict__}"

    def set_flags(self, **values):
        for k in values.keys():
            if k not in self.flag_names:
                raise ValueError(f"Invalid flag name: {k}")
        self.flags.update(values)

    def get_register_obj(self, register_name: str):
        self.register_guard(register_name)
        return self.__dict__[register_name]

    def get_register(self, register_name: str):
        self.register_guard(register_name)
        return self.__dict__[register_name].value

    def set_register(self, register_name: str, value):
        self.register_guard(register_name)
        r = self.__dict__[register_name]
        r.value = value % (r.max_value + 1)

    def inc_register(self, register_name: str):
        self.register_guard(register_name)
        r = self.__dict__[register_name]
        r.value = (r.value + 1) % (r.max_value + 1)

    def dec_register(self, register_name: str):
        self.register_guard(register_name)
        r = self.__dict__[register_name]
        r.value = (r.value - 1) % (r.max_value + 1)

    def jump_to(self, address):
        self.set_register("PC", address)
        
    def call(self, memory, address):
        current_PC = self.get_register('PC')
        PC_high, PC_low = current_PC << 8, current_PC & 0xFF
        self.set_register("SP", self.SP.value - 2)
        memory.write_to(self.SP.value, PC_high)
        memory.write_to(self.SP.value + 1, PC_low)
        self.jump_to(address)
        
    def __return(self, memory):
        self.set_register("SP", self.SP.value + 2)
        stack_top = BO.concat_bytes(high=memory.read_at(
            self.SP.value + 2), low=memory.read_at(self.SP.value + 1))
        self.jump_to(stack_top)


class ByteOperator:
    @classmethod
    def get_nth_bit(cls, b, n):
        return (b & pow(2, n)) >> n

    @classmethod
    def byte_twos_complement(cls, b):
        return (-128) * (cls.get_nth_bit(b, 7)) + (b & 127)

    @staticmethod
    def nibblesfrom_bytes(byte):
        n1 = byte >> 4
        n2 = byte & 0b00001111
        return n1, n2

    @staticmethod
    def concat_bytes(high, low):
        return (high << 8) | low

    @classmethod
    def add_half_carry(cls, addend, summand) -> bool:
        return (addend & 0x0F) + (summand & 0x0F) > 0x0F

    @classmethod
    def add_full_carry(cls, addend, summand) -> bool:
        return (addend + summand) > 0xFF


BO = ByteOperator()


class SM83(CPU):
    def __init__(self, peripherals):
        general_registers = {
            'A': Register(name='A', value=0, max_value=0xFF, bit_length=8),
            'B': Register(name='B', value=0, max_value=0xFF, bit_length=8),
            'C': Register(name='C', value=0, max_value=0xFF, bit_length=8),
            'D': Register(name='D', value=0, max_value=0xFF, bit_length=8),
            'E': Register(name='E', value=0, max_value=0xFF, bit_length=8),
            'H': Register(name='H', value=0, max_value=0xFF, bit_length=8),
            'L': Register(name='L', value=0, max_value=0xFF, bit_length=8),
            'IME': Register(name='IME', value=0, max_value=1, bit_length=1)
        }

        general_registers['BC'] = PairRegister(
            'BC', general_registers['B'], general_registers['C'])
        general_registers['DE'] = PairRegister(
            'DE', general_registers['D'], general_registers['E'])
        general_registers['HL'] = PairRegister(
            'HL', general_registers['H'], general_registers['L'])

        flags = {'Z': False, 'N': False, 'H': False, 'C': False, 'IME': False}
        super().__init__(peripherals,
                         general_registers, flags,
                         PC=Register(name='PC', value=0,
                                     max_value=0xFFFF, bit_length=16),
                         SP=Register(name='SP', value=0,
                                     max_value=0xFFFF, bit_length=16))
        self.mem_ctl = GBMemoryController()
        
    def flags_register(self):
        return (self.flags['Z'] << 7) | (self.flags['N'] << 6) |\
            (self.flags['H'] << 5) | (self.flags['C'] << 4)

    def handle_operand_inc(self, operand):
        if operand.increment or operand.decrement:
            if operand.increment:
                self.inc_register(operand.name)
            else:
                self.dec_register(operand.name)

    # Load, copy related instructions start here
    ###
    # LD; LDH

    def exe_INS_LD(self, ins: GameboyInstruction):
        # at max 3 operands at a LD instruction
        # In fact only one instruction that uses 3 operands which is LD HL,SP+e8
        o1, o2, *oo = ins.operands
        if oo:
            e8 = ins.operands_raw[0]
            signed = BO.byte_twos_complement(e8)
            self.set_register("SP", self.SP.value + signed)

        # o1 is the load destionation, ALWAYS
        # o2 is ALWAYS the data to load
        if o2.name in ["n8", "a16"]:
            if o2.name == "n8":
                data = ins.operands_raw[0]
            else:
                data = BO.concat_bytes(*ins.operands_raw[:2])
            w = data if o2.immediate else self.mem_ctl.read_at(data)
        else:
            w = self.get_register(o2.name)

        # when operand 1 is an address, operand 2 is always a register, hence we use the whole raw operands
        # in fact it is either SP or A
        if o1.name == "a16":
            data = BO.concat_bytes(*ins.operands_raw[:2])
            if o2.name == "SP":
                self.mem_ctl.write_to(data, self.SP.value & 0xFF)
                self.mem_ctl.write_to(data + 1, self.SP.value >> 8)
            elif o2.name == "A":
                self.mem_ctl.write_to(data, self.get_register("A"))

        else:
            if o1.immediate:
                self.set_register(o1.name, w)
            else:
                self.mem_ctl.write_to(self.get_register(o1.name), w)
        if oo:
            self.set_flags(Z=0, N=0, H=BO.add_half_carry(
                self.SP, signed), C=BO.add_full_carry(self.SP, signed))
        self.handle_operand_inc(o1)
        self.handle_operand_inc(o2)

    def exe_INS_LDH(self, ins: GameboyInstruction):
        o1, o2 = ins.operands
        if o1.name == "n16":
            self.mem_ctl.write_to(
                0xFF00 + ins.operands_raw[0], self.get_register('A'))
        elif o1.name == 'C':
            self.mem_ctl.write_to(0xFF00 + self.get_register('C'),
                              self.get_register('A'))
        elif o2.name == "n16":
            self.set_register('A', self.mem_ctl.read_at(
                0xFF00 + ins.operands_raw[0]))
        elif o2.name == 'C':
            self.set_register('A', self.mem_ctl.read_at(
                0xFF00 + self.get_register('C')))

    # Load, copy related instructions END here
    ###

    # arithmetic related instructions start here
    ###
    # ADD; ADC; SUB; DEC; INC
    def exe_INS_ADD(self, ins: GameboyInstruction):
        pass
        # o1, o2 = ins.operands
        # if o1.name == "SP":
        #     signed = BO.byte_twos_complement(ins.operands_raw[0])
        #     self.set_register("SP", self.get_register("SP") + signed)
        #     return

    def exe_INS_SUB(self, ins: GameboyInstruction):
        pass

    def exe_INS_INC(self, ins: GameboyInstruction):
        o = ins.operands[0]
        rname = o.name
        register = self.get_register_obj(rname)
        update_flags = o.immediate or register.bit_length == 8
        if update_flags:
            self.set_flags(H=BO.add_half_carry(self.get_register(rname), 1))
        self.inc_register(rname) if o.immediate else self.ram.inc_byte_at(
            self.get_register(rname))
        if update_flags:
            self.set_flags(Z=self.get_register(rname) == 0, N=False)

    def exe_INS_DEC(self, ins: GameboyInstruction):
        o = ins.operands[0]
        rname = o.name
        register = self.get_register_obj(rname)
        update_flags = o.immediate or register.bit_length == 8
        if update_flags:
            self.set_flags(
                H=BO.add_half_carry(self.get_register(rname), -1))
        self.dec_register(rname) if o.immediate else self.ram.dec_byte_at(
            self.get_register(rname))
        if update_flags:
            self.set_flags(Z=self.get_register(rname) == 0, N=True)

    # arithmetic related instructions END here
    ###

    # few enough to hardcode

    # Stack related instructions start here
    ###
    # POP; PUSH

    def exe_INS_POP(self, ins: GameboyInstruction):
        def pop(highreg, lowreg, flag=False):
            self.set_register("SP", self.SP.value + 2)
            self.set_register(highreg, self.mem_ctl.read_at(self.SP.value - 2))
            if not flag:
                self.set_register(
                    lowreg, self.mem_ctl.read_at(self.SP.value - 1))
            else:
                b = self.mem_ctl.read_at(self.SP.value - 1)
                self.set_flags(Z=bool(BO.get_nth_bit(b, 7)), N=bool(BO.get_nth_bit(
                    b, 6)), H=bool(BO.get_nth_bit(b, 5)), C=bool(BO.get_nth_bit(b, 4)))
        if ins.raw == 0xC1:
            pop("B", "C")
        elif ins.raw == 0xD1:
            pop("D", "E")
        elif ins.raw == 0xE1:
            pop("H", "L")
        elif ins.raw == 0xF1:
            pop("A", None, flag=True)

    def exe_INS_PUSH(self, ins: GameboyInstruction):
        def push(highreg, lowreg, flag=False):
            self.set_register("SP", self.SP.value - 2)
            self.mem_ctl.write_to(self.SP.value, self.get_register(highreg))
            if not flag:
                self.mem_ctl.write_to(self.SP.value + 1, self.get_register(lowreg))
            else:
                flags_reg = self.flags_register()
                self.mem_ctl.write_to(self.SP.value + 1, flags_reg)
        if ins.raw == 0xC5:
            push("B", "C")
        elif ins.raw == 0xD5:
            push("D", "E")
        elif ins.raw == 0xE5:
            push("H", "L")
        elif ins.raw == 0xF5:
            push("A", None, flag=True)
    # Stack related instructions END here
    ###

    # control, subroutine related instructions start here
    ###
    # JP; JR; CALL; RET

    def exe_INS_JP(self, ins: GameboyInstruction):
        if ins.byte_count > 1:
            address = BO.concat_bytes(*ins.operands_raw[:2])
        # JP NZ, a16
        if ins.raw == 0xC2:
            if not self.flags["Z"]:
                self.jump_to(address)
        # JP a16, unconditional jump kappa pride
        elif ins.raw == 0xC3:
            self.jump_to(address)
        # JP Z, a16
        elif ins.raw == 0xCA:
            if self.flags["Z"]:
                self.jump_to(address)
        # JP NC, a16
        elif ins.raw == 0xD2:
            if not self.flags["C"]:
                self.jump_to(address)
        # JP C, a16
        elif ins.raw == 0xDA:
            if self.flags["C"]:
                self.jump_to(address)
        # JP HL
        elif ins.raw == 0xE9:
            self.jump_to(self.get_register("HL"))

    def exe_INS_JR(self, ins: GameboyInstruction):
        e8 = ins.operands_raw[0]
        signed = BO.byte_twos_complement(e8)
        address = (self.PC.value + signed) % 0x10000
        # JR NZ, r8
        if ins.raw == 0x20:
            if not self.flags["Z"]:
                self.jump_to(address)
        # JR r8, unconditional jump kappa pride
        elif ins.raw == 0x18:
            self.jump_to(address)
        # JR Z, r8
        elif ins.raw == 0x28:
            if self.flags["Z"]:
                self.jump_to(address)
        # JR NC, r8
        elif ins.raw == 0x30:
            if not self.flags["C"]:
                self.jump_to(address)
        # JR C, r8
        elif ins.raw == 0x38:
            if self.flags["C"]:
                self.jump_to(address)

    def exe_INS_RET(self, ins: GameboyInstruction):
        if ins.raw == 0xC9:
            self.__return(self.mem_ctl)
        elif ins.raw == 0xC0:
            if not self.flags['Z']:
                self.__return(self.mem_ctl)
        elif ins.raw == 0xD0:
            if not self.flags['C']:
                self.__return(self.mem_ctl)
        elif ins.raw == 0xC8:
            if self.flags['Z']:
                self.__return(self.mem_ctl)
        elif ins.raw == 0xD8:
            if self.flags['C']:
                self.__return(self.mem_ctl)

    def exe_INS_CALL(self, ins: GameboyInstruction):
        address = BO.concat_bytes(*ins.operands_raw[:2])

        # unconditional call
        if ins.raw == 0xCD:
            self.call(self.mem_ctl, address)
        # CALL NZ, a16
        elif ins.raw == 0xC4:
            if not self.flags['Z']:
                self.call(self.mem_ctl, address)
        # JP NC, a16
        elif ins.raw == 0xD4:
            if not self.flags['C']:
                self.call(self.mem_ctl, address)
        # CALL Z, a16
        elif ins.raw == 0xCC:
            if self.flags['Z']:
                self.call(self.mem_ctl, address)
        # CALL C, a16
        elif ins.raw == 0xDC:
            if self.flags['C']:
                self.call(self.mem_ctl, address)

    # RST: implicit call
    def exe_INS_RST(self, ins):
        address = ins.raw & 0b00111000
        PC_high, PC_low = self.get_register(
            'PC') >> 8, self.get_register('PC') & 0xFF
        self.set_register("SP", self.SP.value - 2)
        self.mem_ctl.write_to(self.SP.value, PC_high)
        self.mem_ctl.write_to(self.SP.value + 1, PC_low)
        self.jump_to(address)
        
    def exe_INS_RETI(self, ins):
        self.exe_INS_RET(ins)

    # control, subroutine related instructions END here
    ###

    # MISC instructions

    def exe_INS_NOP(self, _):
        self.add_cycles(4)
    ###

    def __getattr__(self, name):
        print(f"Trying to access {name}")
        raise NotImplementedError(
            f"Instruction {name} not implemented yet, if it exists.")

    def decode(self, ins):
        print(f"decoding instruction: {ins.mnemonic}")
        return getattr(self, f"exe_INS_{ins.mnemonic}")

    def instruction_cycle(self, ROM):
        try:
            ins = self.fetch_ins(ROM)
            func = self.decode(ins)
            func(ins)
            return ins
        except NotImplementedError:
            logger.warning(f"Instruction {ins} not implemented yet, skipping.")
            return None
        
    def handle_interrupts(self):
        # interrupts are not enabled
        if not self.IME.value:
            return
        IF = self.mem_ctl.read_at(0xFFFF)
        IE = self.mem_ctl.read_at(0xFF0F)
        res = IF & IE
        # handle priorities
        if BO.get_nth_bit(res, 0):
            self.exe_INS_RETI(GameboyInstruction(raw=0x40, mnemonic="RETI", operands=[]))
            return
        elif BO.get_nth_bit(res, 1):
            self.exe_INS_RETI(GameboyInstruction(raw=0x48, mnemonic="RETI", operands=[]))
            return
        elif BO.get_nth_bit(res, 2):
            self.exe_INS_RETI(GameboyInstruction(raw=0x50, mnemonic="RETI", operands=[]))
            return
        elif BO.get_nth_bit(res, 3):
            self.exe_INS_RETI(GameboyInstruction(raw=0x58, mnemonic="RETI", operands=[]))
            return
        elif BO.get_nth_bit(res, 4):
            self.exe_INS_RETI(GameboyInstruction(raw=0x60, mnemonic="RETI", operands=[]))
            return

    def execute_prog(self, prog: list[GameboyInstruction]):
        while True:
            ins = self.instruction_cycle(prog)
            self.add_cycles(ins.cycles[0])

    def execute_prog_debug(self, prog: list[GameboyInstruction], delay=0.1):
        import colorama
        import time
        exed = 0
       
        while exed != 500000:
            logger.debug(self.dump_state_colorama(colorama))
            time.sleep(delay)
            
            ins = self.instruction_cycle(prog)
            exed += 1
            # print(exed)
            if ins is None:
                logger.warning("Instruction was not implemented.")
                continue
            self.add_cycles(ins.cycles[0])
            logger.debug(
                f"Executed instruction: {colorama.Fore.YELLOW}{ins}{colorama.Style.RESET_ALL}")
            print("--" * 20)

    def dump_state_colorama(self, colorama):
        register_dict = {k: v for k, v in self.__dict__.items(
        ) if k in self.register_names}
        return f"PC: {colorama.Fore.GREEN}{hex(self.PC.value)}{colorama.Style.RESET_ALL},\
            SP: {colorama.Fore.RED}{hex(self.SP.value)}{colorama.Style.RESET_ALL},\
            general_registers: {colorama.Fore.BLUE}{register_dict}{colorama.Style.RESET_ALL},\
                flags: {colorama.Fore.MAGENTA}{self.flags}{colorama.Style.RESET_ALL}"
