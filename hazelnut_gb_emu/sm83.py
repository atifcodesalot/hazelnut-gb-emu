

from .loader import *
from . import logger
from .memory import *
from .aux import BO


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
    def __init__(self, memory, peripherals, general_registers: list[Register], flags, PC, SP=None):
        self.memory = memory
        self.peripherals = peripherals
        self.register_names = list(general_registers.keys()) + ["PC", "SP"]
        self.flag_names = flags.keys()
        self.__dict__.update(general_registers)
        self.flags = flags
        self.PC = PC
        self.SP = SP
        self.machine_cycles = 0
        self.turing_said_HALT = False

    def add_cycles(self, cycles):
        self.machine_cycles += cycles

    # very fast, can be used for every register fetching and writing
    # also handles register increment and decrement if needed
    def register_guard(self, register_name):
        if register_name not in self.register_names:
            raise ValueError(f"Invalid register name: {register_name}")

    def fetch_ins(self):
        prefixed = False
        opcode = self.memory.read_at(self.PC.value)

        if opcode == 0xCB:
            # the instruction is prefixed
            self.PC.value = (self.PC.value + 1) & 0xffff
            opcode = self.memory.read_at(self.PC.value)
            prefixed = True

        self.PC.value = (self.PC.value + 1) & 0xffff
        return opcode, prefixed

    def dump_state(self):
        return f"PC: {hex(self.PC)}, SP: {hex(self.SP)}, general_registers: {self.__dict__}"

    def set_flags(self, **values):
        for k in values.keys():
            if k not in self.flag_names:
                raise ValueError(f"Invalid flag name: {k}")
        self.flags.update(values)

    def get_register_obj(self, register_name: str):
        # self.register_guard(register_name)
        return self.__dict__[register_name]

    def get_register(self, register_name: str):
        # self.register_guard(register_name)
        return self.__dict__[register_name].value

    def set_register(self, register_name: str, value):
        # self.register_guard(register_name)
        r = self.__dict__[register_name]
        r.value = value & r.max_value

    def inc_register(self, register_name: str):
        # self.register_guard(register_name)
        r = self.__dict__[register_name]
        r.value = (r.value + 1) & r.max_value

    def dec_register(self, register_name: str):
        # self.register_guard(register_name)
        r = self.__dict__[register_name]
        r.value = (r.value - 1) & r.max_value

    def jump_to(self, address):
        self.set_register("PC", address)

    def call(self, address):
        current_PC = self.get_register('PC')
        PC_high, PC_low = current_PC >> 8, current_PC & 0xFF
        self.set_register("SP", self.SP.value - 2)
        # little endian
        self.memory.write_to(self.SP.value + 1, PC_high)
        self.memory.write_to(self.SP.value, PC_low)
        self.jump_to(address)

    def return__(self):
        self.set_register("SP", self.SP.value + 2)
        stack_top = BO.concat_bytes(high=self.memory.read_at(
            self.SP.value - 1), low=self.memory.read_at(self.SP.value - 2))
        self.jump_to(stack_top)


class SM83(CPU):
    def __init__(self, loader: GBRomLoader, memory, peripherals: list):
        def r8bit(name): return Register(
            name=name, value=0, max_value=0xFF, bit_length=8)
        def r16bit(name): return Register(
            name=name, value=0, max_value=0xFFFF, bit_length=16)

        general_registers = {
            'A': r8bit('A'),
            'B': r8bit('B'),
            'C': r8bit('C'),
            'D': r8bit('D'),
            'E': r8bit('E'),
            'H': r8bit('H'),
            'L': r8bit('L'),
        }

        general_registers['BC'] = PairRegister(
            'BC', general_registers['B'], general_registers['C'])
        general_registers['DE'] = PairRegister(
            'DE', general_registers['D'], general_registers['E'])
        general_registers['HL'] = PairRegister(
            'HL', general_registers['H'], general_registers['L'])

        flags = {'Z': False, 'N': False, 'H': False, 'C': False, 'IME': False}
        super().__init__(memory, peripherals,
                         general_registers, flags,
                         PC=r16bit('PC'),
                         SP=r16bit('SP'))
        self.loader = loader

        self.pending_interrupt_enable = False
        self.enable_interrupts_now = False

    def set_flags_fast(self, Z=None, N=None, H=None, C=None, IME=None):
        if Z is not None:
            self.flags['Z'] = Z
        if N is not None:
            self.flags['N'] = N
        if H is not None:
            self.flags['H'] = H
        if C is not None:
            self.flags['C'] = C
        if IME is not None:
            self.flags['IME'] = IME

    def flags_register(self):
        return (self.flags['Z'] << 7) | (self.flags['N'] << 6) |\
            (self.flags['H'] << 5) | (self.flags['C'] << 4)

    def get_operands(self, byte_count, ins_address):
        if byte_count == 0:
            return None
        if byte_count == 1:
            return [self.memory.read_at(ins_address + 1)]
        if byte_count == 2:
            return [self.memory.read_at(ins_address + 1),
                    self.memory.read_at(ins_address + 2)]

    # Load, copy related instructions start here
    ###
    # LD; LDH

    def handle_operand_inc(self, operand):
        if operand.increment or operand.decrement:
            if operand.increment:
                self.inc_register(operand.name)
            else:
                self.dec_register(operand.name)

    def exe_INS_LD(self, ins: GameboyInstruction):
        # at max 3 operands at a LD instruction
        # In fact only one instruction that uses 3 operands which is LD HL,SP+e8
        o1, o2, *oo = ins.operands
        if oo:
            e8 = ins.operands_raw[0]
            signed = BO.byte_twos_complement(e8)
            self.set_register("HL", self.SP.value + signed)
            self.set_flags_fast(Z=0, N=0, H=BO.add_half_carry(
                self.SP.value, signed), C=BO.add_full_carry(self.SP.value & 0xFF, e8))
            return

        # o1 is the load destionation, ALWAYS
        # o2 is ALWAYS the data to load
        if o2.name in ["n8", "n16", "a16"]:
            if o2.name == "n8":
                data = ins.operands_raw[0]
            else:
                data = BO.concat_bytes(
                    *ins.operands_raw[:2][::-1])  # little endian
            w = data if o2.immediate else self.memory.read_at(data)
        else:
            r = self.get_register(o2.name)
            w = r if o2.immediate else self.memory.read_at(r)

        # when operand 1 is an address, operand 2 is always a register, hence we use the whole raw operands
        # in fact it is either SP or A
        if o1.name == "a16":
            data = BO.concat_bytes(*ins.operands_raw[:2][::-1])
            if o2.name == "SP":
                high, low = self.SP.value >> 8, self.SP.value & 0xFF
                self.memory.write_to(data + 1, high)  # little endian
                self.memory.write_to(data, low)

            elif o2.name == "A":
                self.memory.write_to(data, self.get_register("A"))

        else:
            if o1.immediate:
                self.set_register(o1.name, w)
            else:
                self.memory.write_to(self.get_register(o1.name), w)

        self.handle_operand_inc(o1)
        self.handle_operand_inc(o2)

    def exe_INS_LDH(self, ins: GameboyInstruction):
        o1, o2 = ins.operands
        if o1.name == "a8":
            self.memory.write_to(
                0xFF00 + ins.operands_raw[0], self.get_register('A'))
        elif o1.name == 'C':
            self.memory.write_to(0xFF00 + self.get_register('C'),
                                 self.get_register('A'))
        elif o2.name == "a8":
            self.set_register('A', self.memory.read_at(
                0xFF00 + ins.operands_raw[0]))
        elif o2.name == 'C':
            self.set_register('A', self.memory.read_at(
                0xFF00 + self.get_register('C')))

    # Load, copy related instructions END here
    ###

    # arithmetic related instructions start here
    ###
    # ADD; ADC; SUB; DEC; INC

    def accumulate_A(self, ins: GameboyInstruction, include_carry=False, sub=False):
        # operand 1 is always A
        _, o2 = ins.operands

        current_A = self.get_register("A")

        func_half = BO.sub_half_borrow if sub else BO.add_half_carry
        func_full = BO.sub_full_borrow if sub else BO.add_full_carry

        if o2.name == 'n8':
            operand = ins.operands_raw[0]
        else:
            r = self.get_register(o2.name)
            operand = r if o2.immediate else self.memory.read_at(r)

        bch = func_half(
            current_A, operand)
        bcf = func_full(current_A, operand)
        self.set_flags_fast(H=bch, C=bcf)

        if sub:
            self.set_register('A', current_A - operand)
        else:
            self.set_register('A', current_A + operand)
        current_A = self.get_register("A")
        if include_carry:
            self.set_flags_fast(H=func_half(
                current_A, 1) or bch, C=func_full(current_A, 1) or bcf)
            if sub:
                self.dec_register('A')
            else:
                self.inc_register('A')

        self.set_flags_fast(Z=(self.get_register('A') == 0), N=sub)

    def exe_INS_ADD(self, ins: GameboyInstruction):
        o1, o2 = ins.operands
        # the first edge case when we add the signed byte to SP and not A
        if o1.name == "SP":
            e8 = ins.operands_raw[0]
            signed = BO.byte_twos_complement(e8)
            self.set_flags_fast(Z=False, N=False, H=BO.add_half_carry(
                self.SP.value, signed), C=BO.add_full_carry(self.SP.value & 0xFF, e8))
            self.set_register("SP", self.SP.value + signed)
        elif o1.name == 'A':
            self.accumulate_A(ins)
        # ADD HL,ss is the only instruction that has a 16 bit operand, and the operand is always a register pair,
        # so we can just check if o1 is HL to determine whether it is that instruction or not
        elif o1.name == "HL":
            addend = self.get_register("HL")
            summand = self.get_register(o2.name)
            self.set_register("HL", self.get_register("HL") + summand)
            self.set_flags_fast(N=False, H=BO.add_half_carry(addend, summand, high_half=True),
                                C=BO.add_full_carry(addend, summand, bit_width=16))

    def exe_INS_SUB(self, ins: GameboyInstruction):
        self.accumulate_A(ins, sub=True)

    def exe_INS_ADC(self, ins: GameboyInstruction):
        self.accumulate_A(ins, include_carry=self.flags['C'])

    def exe_INS_SBC(self, ins: GameboyInstruction):
        self.accumulate_A(ins, include_carry=self.flags['C'], sub=True)

    def exe_INS_INC(self, ins: GameboyInstruction):
        o = ins.operands[0]
        rname = o.name
        register = self.get_register_obj(rname)
        update_flags = not o.immediate or register.bit_length == 8
        if update_flags:
            pr_value = self.get_register(
                rname) if o.immediate else self.memory.read_at(self.get_register(rname))
            self.set_flags_fast(H=BO.add_half_carry(pr_value, 1))
        self.inc_register(rname) if o.immediate else self.memory.inc_byte_at(
            self.get_register(rname))
        if update_flags:
            if not o.immediate:
                self.set_flags_fast(Z=self.memory.read_at(
                    self.get_register(rname)) == 0, N=False)
            else:
                self.set_flags_fast(Z=self.get_register(rname) == 0, N=False)

    def exe_INS_DEC(self, ins: GameboyInstruction):
        o = ins.operands[0]
        rname = o.name
        register = self.get_register_obj(rname)
        update_flags = not o.immediate or register.bit_length == 8
        if update_flags:
            pr_value = self.get_register(
                rname) if o.immediate else self.memory.read_at(self.get_register(rname))
            self.set_flags_fast(
                H=BO.sub_half_borrow(pr_value, 1))
        self.dec_register(rname) if o.immediate else self.memory.dec_byte_at(
            self.get_register(rname))
        if update_flags:
            if not o.immediate:
                self.set_flags_fast(Z=self.memory.read_at(
                    self.get_register(rname)) == 0, N=True)
            else:
                self.set_flags_fast(Z=self.get_register(rname) == 0, N=True)

    def exe_INS_CP(self, ins: GameboyInstruction):
        # o1 is always A.
        _, o2 = ins.operands
        # o2 is the data to compare with A, which can be either a register or an immediate value
        if o2.name == "n8":
            byte = ins.operands_raw[0]
        else:
            r = self.get_register(o2.name)
            byte = r if o2.immediate else self.memory.read_at(r)
        A = self.get_register("A")
        self.set_flags_fast(Z=(A - byte) == 0, N=True,
                            H=BO.sub_half_borrow(A, byte), C=BO.sub_full_borrow(A, byte))

    # arithmetic related instructions END here
    ###

    # BIT OPERATION related instructions START here
    ###
    # AND; OR; XOR; CPL;

    def exe_INS_AND(self, ins: GameboyInstruction):
        _, o2 = ins.operands

        if o2.name == "n8":
            value = ins.operands_raw[0]
        else:
            r = self.get_register(o2.name)
            value = r if o2.immediate else self.memory.read_at(r)
        result = self.get_register('A') & value
        self.set_register('A', result)
        self.set_flags_fast(Z=result == 0, N=False, H=True, C=False)

    def exe_INS_OR(self, ins: GameboyInstruction):
        _, o2 = ins.operands

        if o2.name == "n8":
            value = ins.operands_raw[0]
        else:
            r = self.get_register(o2.name)
            value = r if o2.immediate else self.memory.read_at(r)
        result = self.get_register('A') | value
        self.set_register('A', result)
        self.set_flags_fast(Z=result == 0, N=False, H=False, C=False)

    def exe_INS_XOR(self, ins: GameboyInstruction):
        _, o2 = ins.operands

        if o2.name == "n8":
            value = ins.operands_raw[0]
        else:
            r = self.get_register(o2.name)
            value = r if o2.immediate else self.memory.read_at(r)
        result = self.get_register('A') ^ value
        self.set_register('A', result)
        self.set_flags_fast(Z=result == 0, N=False, H=False, C=False)

    def exe_INS_CPL(self, _: GameboyInstruction):
        result = 0xFF ^ self.get_register("A")
        self.set_register("A", result)
        self.set_flags_fast(N=1, H=1)

    # Stack related instructions start here
    ###
    # POP; PUSH

    def exe_INS_POP(self, ins: GameboyInstruction):
        def pop(highreg, lowreg, flag=False):
            self.set_register("SP", self.SP.value + 2)
            self.set_register(highreg, self.memory.read_at(self.SP.value - 1))
            if not flag:
                self.set_register(
                    lowreg, self.memory.read_at(self.SP.value - 2))
            else:
                b = self.memory.read_at(self.SP.value - 2)
                self.set_flags_fast(Z=bool(b >> 7 & 1), N=bool(
                    b >> 6 & 1), H=bool(b >> 5 & 1), C=bool(b >> 4 & 1))
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
            self.memory.write_to(
                self.SP.value + 1, self.get_register(highreg))  # little endian
            if not flag:
                self.memory.write_to(
                    self.SP.value, self.get_register(lowreg))
            else:
                flags_reg = self.flags_register()
                self.memory.write_to(self.SP.value, flags_reg)
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
            address = BO.concat_bytes(
                *ins.operands_raw[:2][::-1])  # little endian
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
            self.return__()
        elif ins.raw == 0xC0:
            if not self.flags['Z']:
                self.return__()
        elif ins.raw == 0xD0:
            if not self.flags['C']:
                self.return__()
        elif ins.raw == 0xC8:
            if self.flags['Z']:
                self.return__()
        elif ins.raw == 0xD8:
            if self.flags['C']:
                self.return__()

    def exe_INS_CALL(self, ins: GameboyInstruction):
        address = BO.concat_bytes(*ins.operands_raw[:2][::-1])  # little endian

        # unconditional call
        if ins.raw == 0xCD:
            self.call(address)
        # CALL NZ, a16
        elif ins.raw == 0xC4:
            if not self.flags['Z']:
                self.call(address)
        # JP NC, a16
        elif ins.raw == 0xD4:
            if not self.flags['C']:
                self.call(address)
        # CALL Z, a16
        elif ins.raw == 0xCC:
            if self.flags['Z']:
                self.call(address)
        # CALL C, a16
        elif ins.raw == 0xDC:
            if self.flags['C']:
                self.call(address)

    # RST: implicit call
    def exe_INS_RST(self, ins: GameboyInstruction):
        address = ins.raw & 0b00111000
        self.call(address)

    def exe_INS_RETI(self, _):
        # set interrupts immediately
        self.return__()
        self.set_flags_fast(IME=True)

    # control, subroutine related instructions END here
    ###

    # MISC instructions start here

    def exe_INS_NOP(self, _):
        # do nothing
        self.add_cycles(4)

    def exe_INS_DAA(self, _):
        adjustment = 0
        old_A = self.get_register('A')
        H = self.flags['H']
        N = self.flags['N']
        C = self.flags['C']

        if N:
            if H:
                adjustment += 0x6
            if C:
                adjustment += 0x60
            self.set_register('A', old_A - adjustment)
            new_Z = old_A - adjustment == 0

        else:
            if H or old_A & 0xF > 0x9:
                adjustment += 0x6
            if C or old_A > 0x99:
                adjustment += 0x60
                self.set_flags_fast(C=True)
            self.set_register('A', old_A + adjustment)
            new_Z = old_A + adjustment == 0

        self.set_flags_fast(H=False, Z=new_Z)

    def exe_INS_HALT(self, ins):
        logger.debug("HALT instruction executed.")
        self.turing_said_HALT = True
    
    def exe_INS_STOP(self, ins):
        pass

    # MISC instructions end here

    # interrupt related instructions start here
    ###
    # EI; DI

    def exe_INS_DI(self, _):
        self.set_flags_fast(IME=False)

    def exe_INS_EI(self, _):
        self.pending_interrupt_enable = True

    # interrupt related instructions end here
    ###

    # carry flag related instructions start here
    ###
    # CCF; SCF

    def exe_INS_CCF(self, _):
        cf = self.flags['C']
        self.set_flags_fast(C=not cf, N=False, H=False)

    def exe_INS_SCF(self, _):
        self.set_flags_fast(C=True, N=False, H=False)

    # carry flag related instructions END here
    ###

    # prefixed instructions START here
    ###
    # RLC; RL; RRC; RR; SLA; SRA; SWAP; SRL; BIT; RES; SET

    def exe_INS_BIT(self, ins: GameboyInstruction):
        o1, o2 = ins.operands
        r = self.get_register(o2.name)
        byte = r if o2.immediate else self.memory.read_at(
            self.get_register(o2.name))
        bit = bool(BO.get_nth_bit(byte, int(o1.name)))
        self.set_flags_fast(Z=not bit, N=False, H=True)

    def exe_INS_RES(self, ins: GameboyInstruction):
        o1, o2 = ins.operands
        byte = self.get_register(o2.name) if o2.immediate else self.memory.read_at(
            self.get_register(o2.name))
        result = BO.res_nth_bit(byte, int(o1.name))
        if o2.immediate:
            self.set_register(o2.name, result)
        else:
            self.memory.write_to(self.get_register(o2.name), result)

    def exe_INS_SET(self, ins: GameboyInstruction):
        o1, o2 = ins.operands
        byte = self.get_register(o2.name) if o2.immediate else self.memory.read_at(
            self.get_register(o2.name))
        result = BO.set_nth_bit(byte, int(o1.name))
        if o2.immediate:
            self.set_register(o2.name, result)
        else:
            self.memory.write_to(self.get_register(o2.name), result)

    def shift_rotate_to_carry(self, ins, bin_op, rotate=False):
        op = ins.operands[0]
        byte = self.get_register(op.name) if op.immediate else self.memory.read_at(
            self.get_register(op.name))
        if rotate:
            if bin_op == BO.rotate_byte_right or bin_op == BO.rotate_byte_left:
                bit, result = bin_op(byte)
            else:
                bit, result = bin_op(byte, self.flags['C'])
        else:
            bit, result = bin_op(byte)
        if op.immediate:
            self.set_register(op.name, result)
        else:
            self.memory.write_to(self.get_register(op.name), result)
        self.set_flags_fast(Z=result == 0, N=False, H=False, C=bool(bit))

    def exe_INS_RL(self, ins: GameboyInstruction):
        self.shift_rotate_to_carry(
            ins, BO.rotate_byte_left_through, rotate=True)

    def exe_INS_RLA(self, ins: GameboyInstruction):
        A = self.get_register("A")
        bit, result = BO.rotate_byte_left_through(A, self.flags['C'])
        self.set_register("A", result)
        self.set_flags_fast(Z=False, N=False, H=False, C=bool(bit))

    def exe_INS_RLC(self, ins: GameboyInstruction):
        self.shift_rotate_to_carry(ins, BO.rotate_byte_left, rotate=True)

    def exe_INS_RLCA(self, ins: GameboyInstruction):
        A = self.get_register("A")
        bit, result = BO.rotate_byte_left(A)
        self.set_register("A", result)
        self.set_flags_fast(Z=False, N=False, H=False, C=bool(bit))

    def exe_INS_RR(self, ins: GameboyInstruction):
        self.shift_rotate_to_carry(
            ins, BO.rotate_byte_right_through, rotate=True)

    def exe_INS_RRA(self, ins: GameboyInstruction):
        A = self.get_register("A")
        bit, result = BO.rotate_byte_right_through(A, self.flags['C'])
        self.set_register("A", result)
        self.set_flags_fast(Z=False, N=False, H=False, C=bool(bit))

    def exe_INS_RRC(self, ins: GameboyInstruction):
        self.shift_rotate_to_carry(ins, BO.rotate_byte_right, rotate=True)

    def exe_INS_RRCA(self, ins: GameboyInstruction):
        A = self.get_register("A")
        bit, result = BO.rotate_byte_right(A)
        self.set_register("A", result)
        self.set_flags_fast(Z=False, N=False, H=False, C=bit)

    def exe_INS_SLA(self, ins: GameboyInstruction):
        self.shift_rotate_to_carry(ins, BO.shift_byte_left)

    def exe_INS_SRL(self, ins: GameboyInstruction):
        self.shift_rotate_to_carry(ins, BO.shift_byte_right)

    def exe_INS_SRA(self, ins: GameboyInstruction):
        self.shift_rotate_to_carry(ins, BO.shift_byte_right_arithmetic)

    def exe_INS_SWAP(self, ins: GameboyInstruction):
        op = ins.operands[0]
        byte = self.get_register(op.name) if op.immediate else self.memory.read_at(
            self.get_register(op.name))
        result = BO.swap_nibbles(byte)
        if op.immediate:
            self.set_register(op.name, result)
        else:
            self.memory.write_to(self.get_register(op.name), result)
        self.set_flags_fast(Z=result == 0, N=False, H=False, C=False)

    # prefixed instructions END here
    ###

    def __getattr__(self, name):
        if name.startswith("exe_INS_"):
            raise NotImplementedError(
                f"Instruction {name} not implemented yet, if it exists.")
        else:
            raise AttributeError(f"{name} is not a valid attribute of CPU.")

    def decode(self, opcode, prefixed: bool):
        ins = self.loader.identify_instruction(
            opcode, prefixed)
        prefixl = 1 if prefixed else 0
        # fetch instruction incremented PC by 1, so we need to -1 to get the correct operands
        operands = self.get_operands(
            # if the instruction is prefixed, fetch ins already incremented the PC
            ins.byte_count - 1 - prefixl, self.PC.value - 1)
        # skip the operands
        self.PC.value = (self.PC.value + ins.byte_count - 1 - prefixl) & 0xffff
        ins.operands_raw = operands
        return ins

    def instruction_cycle(self):
        opcode, prefixed = self.fetch_ins()
        ins = self.decode(opcode, prefixed=prefixed)
        func = getattr(self, f"exe_INS_{ins.mnemonic}")
        func(ins)
        if self.pending_interrupt_enable and not self.flags['IME']:
            if not self.enable_interrupts_now:
                self.enable_interrupts_now = True
            else:
                self.set_flags_fast(IME=True)
                self.enable_interrupts_now = False
                self.pending_interrupt_enable = False

        return ins

    def disable_IF_at(self, IF, n):
        new_IF = BO.res_nth_bit(IF, n)
        self.memory.write_to(0xFF0F, new_IF)
        self.set_flags_fast(IME=False)

    def handle_interrupts(self):
        # interrupts are disabled, exit
        if not self.flags['IME']:
            return
        IE = self.memory.read_at(0xFFFF)
        IF = self.memory.read_at(0xFF0F)
        res = IF & IE
        # handle priorities
        if res & 1:
            self.call(0x40)
            self.disable_IF_at(IF, 0)
            return
        elif res >> 1 & 1:
            self.call(0x48)
            self.disable_IF_at(IF, 1)
            return
        elif res >> 2 & 1:
            self.call(0x50)
            self.disable_IF_at(IF, 2)
            return
        elif res >> 3 & 1:
            self.call(0x58)
            self.disable_IF_at(IF, 3)
            return
        elif (res >> 4) & 1:
            self.call(0x60)
            self.disable_IF_at(IF, 4)

    def tick_one_ins(self):
        self.handle_interrupts()
        ins = self.instruction_cycle()
        cycles = ins.cycles if ins else 0
        self.add_cycles(cycles)
        return ins, cycles

    def dump_state_colorama(self, colorama):
        fg = colorama.Fore.GREEN
        fr = colorama.Fore.RED
        fb = colorama.Fore.BLUE
        Ra = colorama.Style.RESET_ALL
        register_dict = {k: hex(r.value) for k, r in self.__dict__.items(
        ) if k in self.register_names}
        return f"PC: {fg}{hex(self.PC.value)}{Ra}\
    SP: {colorama.Fore.CYAN}{hex(self.SP.value)}{Ra}\
    general_registers: {fb}{register_dict}{Ra}\
    flags: {fr}{self.flags}{Ra}"
