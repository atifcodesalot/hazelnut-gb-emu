

import json
from dataclasses import dataclass
from typing import Optional
import os

path = os.path.dirname(os.path.abspath(__file__))

GB_OPCODES_JSON = json.load(open(os.path.join(path, "Opcodes.json"), "r"))
GB_UNPREFIXED_OPCODES_JSON = GB_OPCODES_JSON["unprefixed"]
GB_PREFIXED_OPCODES_JSON = GB_OPCODES_JSON["cbprefixed"]


@dataclass
class Operand:
    name: str
    immediate: bool
    bytes: Optional[int] = None
    increment: Optional[bool] = None
    decrement: Optional[bool] = None


@dataclass
class GameboyInstruction:
    prefixed: bool
    mnemonic: str
    raw: bytes
    operands_raw: bytearray
    operands: list[Operand]
    cycles: list
    byte_count: int  # variable instruction size
    immediate: bool

    def __repr__(self):
        return f"<GB_INS: {'prefixed ' if self.prefixed else ''}\
            {self.mnemonic}, opcode: {hex(self.raw)} with operands\
                {[hex(op) for op in self.operands_raw]} and cycles {self.cycles}>"

    def __str__(self):
        return self.__repr__()


class GBRomLoader:
    unprefixed_opcodes = GB_UNPREFIXED_OPCODES_JSON
    prefixed_opcodes = GB_PREFIXED_OPCODES_JSON

    def __init__(self, filename):
        self.filename = filename
        self.instructions = []

    def read(self):
        with open(self.filename, 'rb') as f:
            self.prog = bytearray(f.read())

    def adapt_opcode_to_JSON(self, opcode):
        opcode = list(str(hex(opcode)).upper())
        opcode[1] = 'x'
        if len(opcode) == 3:
            opcode.insert(2, '0')
        opcode = ''.join(opcode)
        return opcode

    def identify_instruction(self, byte, byte_index):
        opcode = self.adapt_opcode_to_JSON(byte)
        prefixed = opcode.startswith("0xCB")
        opcodes = self.unprefixed_opcodes if not prefixed else self.prefixed_opcodes
        ins_json = opcodes[opcode]
        byte = self.get_prefix_byte(byte_index) if prefixed else byte
        return GameboyInstruction(
            prefixed=prefixed,
            mnemonic=ins_json["mnemonic"],
            raw=byte,
            operands_raw=[],
            operands=[Operand(**op) for op in ins_json["operands"]],
            cycles=ins_json["cycles"],
            byte_count=int(ins_json["bytes"]),
            immediate=ins_json["immediate"],
        )

    def get_prefix_byte(self, cb_index):
        opcode = self.prog[cb_index + 1]
        return opcode

    def get_operands(self, ins: GameboyInstruction, ins_index):
        operand_array = self.prog[ins_index+1: ins_index+ins.byte_count]
        ins.operands_raw = operand_array

    def __getattr__(self, name):
        if name == "prog":
            raise AttributeError("read function is not called: no ROM read.")
        else:
            return self.__getattribute__(name)

    def get_instructions(self):
        for i in range(len(self.prog)):
            opcode = self.prog[i]
            gb_ins = self.identify_instruction(opcode, i)
            self.get_operands(gb_ins, i)
            self.instructions.append(gb_ins)
            i += gb_ins.byte_count - 1  # -1 because of the for loop increment
