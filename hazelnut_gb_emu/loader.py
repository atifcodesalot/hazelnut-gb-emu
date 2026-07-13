

import json
from . import dataclass
from typing import Optional
import os

path = os.path.dirname(os.path.abspath(__file__))

GB_OPCODES_JSON = json.load(open(os.path.join(path, "Opcodes.json"), "r"))


# operand format in the json file
@dataclass
class Operand:
    name: str
    immediate: bool
    bytes: Optional[int] = None
    increment: Optional[bool] = None
    decrement: Optional[bool] = None


# turn the operands in the json file to dataclasses
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
    operands_raw: tuple
    operands: tuple[Operand]
    cycles: list
    byte_count: int  # variable instruction size
    immediate: bool

    def __repr__(self):
        return f"<GB_INS: {'prefixed ' if self.prefixed else ''}\
{self.mnemonic}, opcode: {hex(self.raw)} with operands\
{None if not self.operands_raw else [hex(op) for op in self.operands_raw]} and cycles {self.cycles}>"

    def __str__(self):
        return self.__repr__()


GB_UNPREFIXED_OPCODES_JSON = dict()
GB_PREFIXED_OPCODES_JSON = dict()


def init_instructions():
    global GB_OPCODES_JSON
    for i in ["unprefixed", "cbprefixed"]:
        inset = GB_PREFIXED_OPCODES_JSON if i == "cbprefixed" else GB_UNPREFIXED_OPCODES_JSON
        for opcode in GB_OPCODES_JSON[i]:
            ins_json = GB_OPCODES_JSON[i][opcode]
            ins_json["cycles"] = int(ins_json["cycles"][0])
            inset[int(opcode, 16)] = GameboyInstruction(
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
