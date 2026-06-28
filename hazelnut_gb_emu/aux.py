

class ByteOperator:
    # dont call this in hot paths
    @classmethod
    def get_nth_bit(cls, b, n):
        return (b >> n) & 1

    @classmethod
    def byte_twos_complement(cls, b):
        return (-128) * (cls.get_nth_bit(b, 7)) + (b & 127)

    @staticmethod
    def nibblesfrom_bytes(byte):
        n1 = byte >> 4
        n2 = byte & 15
        return n1, n2

    @staticmethod
    def concat_bytes(high, low):
        return (high << 8) | low

    @classmethod
    def add_half_carry(cls, addend, summand, high_half=False) -> bool:
        if high_half:
            return (addend & 0xFFF) + (summand & 0xFFF) > 0xFFF

        return (addend & 0x0F) + (summand & 0x0F) > 0x0F

    @classmethod
    def add_full_carry(cls, addend, summand, bit_width=8) -> bool:
        return (addend + summand) > (pow(2, bit_width) - 1)

    @classmethod
    def sub_half_borrow(cls, minuend, subtrahend) -> bool:
        return (minuend & 0x0F) < (subtrahend & 0x0F)

    @classmethod
    def sub_full_borrow(cls, minuend, subtrahend) -> bool:
        return minuend < subtrahend

    @classmethod
    def rotate_byte_left(cls, byte):
        nbit = cls.get_nth_bit(byte, 7)
        shifted = (byte << 1) | nbit
        return nbit, shifted & 0xFF

    @classmethod
    def rotate_byte_left_through(cls, byte, bit):
        nbit = cls.get_nth_bit(byte, 7)
        shifted = (byte << 1) | bit
        return nbit, shifted & 0xFF

    @classmethod
    def rotate_byte_right(cls, byte):
        nbit = cls.get_nth_bit(byte, 0)
        shifted = (byte >> 1) | nbit * 128
        return nbit, shifted

    @classmethod
    def rotate_byte_right_through(cls, byte, bit):
        nbit = cls.get_nth_bit(byte, 0)
        shifted = (byte >> 1) | bit * 128
        return nbit, shifted

    @classmethod
    def shift_byte_left(cls, byte):
        nbit = cls.get_nth_bit(byte, 7)
        shifted = (byte << 1) & 0xFF
        return nbit, shifted

    @classmethod
    def shift_byte_right(cls, byte):
        nbit = cls.get_nth_bit(byte, 0)
        shifted = byte >> 1
        return nbit, shifted

    @classmethod
    def shift_byte_right_arithmetic(cls, byte):
        nbit = cls.get_nth_bit(byte, 0)
        shifted = (byte >> 1) | (byte & 0b10000000)
        return nbit, shifted

    @staticmethod
    def set_nth_bit(byte, n):
        return byte | pow(2, n)

    @classmethod
    def res_nth_bit(cls, byte, n):
        return byte & (0xFF- (1 << n))

    @classmethod
    def swap_nibbles(cls, byte):
        n1, n2 = cls.nibblesfrom_bytes(byte)
        return (n2 << 4) | n1

    @staticmethod
    def get_pixel_2bpp(lo: int, hi: int, pixel_i: int) -> int:
        bit = 7 - pixel_i
        return (((hi >> bit) & 1) << 1) | ((lo >> bit) & 1)
    
    
    
    
BO = ByteOperator



def string_to_rgb(hexstr):
    if hexstr.startswith("#"):
        hexstr = hexstr[1:]

    return tuple(int(hexstr[i*2:(i+1)*2], 16) for i in range(0, 3))

    
    