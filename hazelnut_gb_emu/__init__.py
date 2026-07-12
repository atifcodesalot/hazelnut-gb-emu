import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


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


@dataclass
class IOhole:
    value: int