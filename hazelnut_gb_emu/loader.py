

import json
from dataclasses import dataclass
from typing import Optional
import os
from .memory import ROM

from numpy import byte

path = os.path.dirname(os.path.abspath(__file__))

GB_OPCODES_JSON = json.load(open(os.path.join(path, "Opcodes.json"), "r"))


@dataclass
class Operand:
    name: str
    immediate: bool
    bytes: Optional[int] = None
    increment: Optional[bool] = None
    decrement: Optional[bool] = None


def init_operands():
    global GB_OPCODES_JSON
    for i in ["unprefixed", "cbprefixed"]:
        inset = GB_OPCODES_JSON[i]
        for opcode in inset:
            inset[opcode]["operands"] = [
                Operand(**op) for op in inset[opcode]["operands"]]


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


def init_instructions():
    global GB_OPCODES_JSON
    for i in ["unprefixed", "cbprefixed"]:
        inset = GB_OPCODES_JSON[i]
        for opcode in inset:
            ins_json = inset[opcode]
            ins_json["cycles"] = int(ins_json["cycles"][0])
            inset[opcode] = GameboyInstruction(
                prefixed=i == "cbprefixed",
                mnemonic=ins_json["mnemonic"],
                raw=int(opcode, 16),
                operands_raw=[],
                operands=ins_json["operands"],
                cycles=ins_json["cycles"],
                byte_count=int(ins_json["bytes"]),
                immediate=ins_json["immediate"],
            )


init_operands()
init_instructions()

GB_UNPREFIXED_OPCODES_JSON = GB_OPCODES_JSON["unprefixed"]
GB_PREFIXED_OPCODES_JSON = GB_OPCODES_JSON["cbprefixed"]


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
        return "0x" + hex(opcode)[2:].upper().zfill(2)

    def identify_instruction(self, opcode, prefixed):
        opcode = self.adapt_opcode_to_JSON(opcode)
        if prefixed:
            ins = self.prefixed_opcodes[opcode]
        else:
            ins = self.unprefixed_opcodes[opcode]
        return ins

    def get_prefix_byte(self, cb_index):
        opcode = self.prog[cb_index + 1]
        return opcode

    def __getattr__(self, name):
        if name == "prog":
            raise AttributeError("read function is not called: no ROM read.")
        else:
            return AttributeError()

    def get_instructions(self):
        for i in range(len(self.prog)):
            opcode = self.prog[i]
            gb_ins = self.identify_instruction(opcode, i)
            self.instructions.append(gb_ins)
            i += gb_ins.byte_count - 1  # -1 because of the for loop increment

    def load_to(self, rom: ROM):
        rom.load_from(self)
