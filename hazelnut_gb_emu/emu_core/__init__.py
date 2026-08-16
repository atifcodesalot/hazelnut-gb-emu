import logging
from dataclasses import dataclass

__author__ = "Burzum"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



GB_LCD_RES = (160, 144)

GB_LCD_PALETTE = ("#e0f8d0", "#88c070",  "#346856", "#081820")
GB_LCD_OFF = "#1D0118"

IMPLEMENTED_MODES = [0x00, 0x01, 0x02, 0x3, 0x5, 0x6, 0x11, 0x12, 0x13, 0x19, 0x1A, 0x1B]


@dataclass
class Register:
    name: str
    value: int
    max_value: int
    bit_length: int
    
    def set_val(self, val):
        self.value = val % self.max_value

    def __repr__(self):
        return str(self.value)
