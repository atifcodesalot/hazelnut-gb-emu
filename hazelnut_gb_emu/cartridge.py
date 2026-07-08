

from ast import Interactive
from dataclasses import dataclass


NINTENDO_LOGO = bytearray.fromhex(
    """
    CE ED 66 66 CC 0D 00 0B 03 73 00 83 00 0C 00 0D
    00 08 11 1F 88 89 00 0E DC CC 6E E6 DD DD D9 99
    BB BB 67 63 6E 0E EC CC DD DC 99 9F BB B9 33 3E
    """
)

NEW_LICENSEE_CODES = {
    0x00: None,
    0x01: "Nintendo Research & Development 1",
    0x08: "Capcom",
    0x13: "EA (Electronic Arts)",
    0x18: "Hudson Soft",
    0x19: "B-AI",
    0x14: "KSS",
    0x16: "Planning Office WADA",
    0x18: "PCM Complete",
    0x19: "San-X",
    0x1C: "Kemco",
    0x1D: "SETA Corporation",
    0x1E: "Viacom",
    0x1F: "Nintendo",
    0x20: "Bandai",
    0x21: "Ocean Software/Acclaim Entertainment",
    0x22: "Konami",
    0x23: "HectorSoft",
    0x25: "Taito",
    0x26: "Hudson Soft",
    0x27: "Banpresto",
    0x29: "Ubi Soft1",
    0x2A: "Atlus",
    0x2C: "Malibu Interactive",
    0x2E: "Angel",
    0x2F: "Bullet-Proof Software",
    0x30: "Viacom",
    0x31: "Irem",
    0x32: "Absolute",
    0x33: "Acclaim Entertainment",
    0x34: "Activision",
    0x35: "Sammy USA Corporation",
    0x36: "Konami",
    0x37: "Hi Tech Expressions",
    0x38: "LJN",
    0x39: "Matchbox",
    0x3A: "Mattel",
    0x3B: "Milton Bradley Company",
    0x3C: "Titus Interactive",
    0x3D: "Virgin Games Ltd.",
    0x40: "Lucasfilm Games",
    0x43: "Ocean Software",
    0x45: "EA (Electronic Arts)",
    0x46: "Infogrames",
    0x47: "Interplay Entertainment",
    0x48: "Broderbund",
    0x49: "Sculptured Software",
    0x4B: "The Sales Curve Limited",
    0x4E: "THQ",
    0x4F: "Accolade",
    0x50: "Misawa Entertainment",
    0x53: "LOZC G.",
    0x56: "Tokuma Shoten",
    0x57: "Tsukuda Original",
    0x5B: "Chunsoft Co.9",
    0x5C: "Video System",
    0x5D: "Ocean Software/Acclaim Entertainment",
    0x5F: "Varie",
    0x60: "Yonezawa10/S’Pal",
    0x61: "Kaneko",
    0x63: "Pack-In-Video",
    0x68: "Bottom Up",
    0x61: "Konami (Yu-Gi-Oh!)",
    0x4C: "MTO",
    0x44: "Kodansha"
}

OLD_LICENSEE_CODES = {
    0x00: None,
    0x01: "Nintendo",
    0x08: "Capcom",
    0x09: "HOT-B",
    0x0A: "Jaleco",
    0x0B: "Coconuts Japan",
    0x0C: "Elite Systems",
    0x13: "EA (Electronic Arts)",
    0x18: "Hudson Soft",
    0x19: "ITC Entertainment",
    0x1A: "Yanoman",
    0x1D: "Japan Clary",
    0x1F: "Virgin Games Ltd.",
    0x24: "PCM Complete",
    0x25: "San-X",
    0x28: "Kemco",
    0x29: "SETA Corporation",
    0x30: "Infogrames",
    0x31: "Nintendo",
    0x32: "Bandai",
    0x33: None,
    0x34: "Konami",
    0x35: "HectorSoft",
    0x38: "Capcom",
    0x39: "Banpresto",
    0x3C: "Entertainment Interactive (stub)",
    0x3E: "Gremlin",
    0x41: "Ubi Soft1",
    0x42: "Atlus",
    0x44: "Malibu Interactive",
    0x46: "Angel",
    0x47: "Spectrum HoloByte",
    0x49: "Irem",
    0x4A: "Virgin Games Ltd.",
    0x4D: "Malibu Interactive",
    0x4F: "U.S. Gold",
    0x50: "Absolute",
    0x51: "Acclaim Entertainment",
    0x52: "Activision",
    0x53: "Sammy USA Corporation",
    0x54: "GameTek",
    0x55: "Park Place",
    0x56: "LJN",
    0x57: "Matchbox",
    0x59: "Milton Bradley Company",
    0x5A: "Mindscape",
    0x5B: "Romstar",
    0x5C: "Naxat Soft",
    0x5D: "Tradewest",
    0x60: "Titus Interactive",
    0x61: "Virgin Games Ltd.",
    0x67: "Ocean Software",
    0x69: "EA (Electronic Arts)",
    0x6E: "Elite Systems",
    0x6F: "Electro Brain",
    0x70: "Infogrames",
    0x71: "Interplay Entertainment",
    0x72: "Broderbund",
    0x73: "Sculptured Software",
    0x75: "The Sales Curve Limited",
    0x78: "THQ",
    0x79: "Accolade",
    0x7A: "Triffix Entertainment",
    0x7C: "MicroProse",
    0x7F: "Kemco",
    0x80: "Misawa Entertainment",
    0x83: "LOZC G.",
    0x86: "Tokuma Shoten",
    0x8B: "Bullet-Proof Software",
    0x8C: "Vic Tokai Corp.",
    0x8E: "Ape Inc.",
    0x8F: "I’Max",
    0x91: "Chunsoft Co.",
    0x92: "Video System",
    0x93: "Tsubaraya Productions",
    0x95: "Varie",
    0x96: "Yonezawa10/S’Pal",
    0x97: "Kemco",
    0x99: "Arc",
    0x9A: "Nihon Bussan",
    0x9B: "Tecmo",
    0x9C: "Imagineer",
    0x9D: "Banpresto",
    0x9F: "Nova",
    0xA1: "Hori Electric",
    0xA2: "Bandai",
    0xA4: "Konami",
    0xA6: "Kawada",
    0xA7: "Takara",
    0xA9: "Technos Japan",
    0xAA: "Broderbund",
    0xAC: "Toei Animation",
    0xAD: "Toho",
    0xAF: "Namco",
    0xB0: "Acclaim Entertainment",
    0xB1: "ASCII Corporation or Nexsoft",
    0xB2: "Bandai",
    0xB4: "Square Enix",
    0xB6: "HAL Laboratory",
    0xB7: "SNK",
    0xB9: "Pony Canyon",
    0xBA: "Culture Brain",
    0xBB: "Sunsoft",
    0xBD: "Sony Imagesoft",
    0xBF: "Sammy Corporation",
    0xC0: "Taito",
    0xC2: "Kemco",
    0xC3: "Square",
    0xC4: "Tokuma Shoten",
    0xC5: "Data East",
    0xC6: "Tonkin House",
    0xC8: "Koei",
    0xC9: "UFL",
    0xCA: "Ultra Games",
    0xCB: "VAP, Inc.",
    0xCC: "Use Corporation",
    0xCD: "Meldac",
    0xCE: "Pony Canyon",
    0xCF: "Angel",
    0xD0: "Taito",
    0xD1: "SOFEL (Software Engineering Lab)",
    0xD2: "Quest",
    0xD3: "Sigma Enterprises",
    0xD4: "ASK Kodansha Co.",
    0xD6: "Naxat Soft",
    0xD7: "Copya System",
    0xD9: "Banpresto",
    0xDA: "Tomy",
    0xDB: "LJN",
    0xDD: "Nippon Computer Systems",
    0xDE: "Human Ent.",
    0xDF: "Altron",
    0xE0: "Jaleco",
    0xE1: "Towa Chiki",
    0xE2: "Yutaka # Needs more info",
    0xE3: "Varie",
    0xE5: "Epoch",
    0xE7: "Athena",
    0xE8: "Asmik Ace Entertainment",
    0xE9: "Natsume",
    0xEA: "King Records",
    0xEB: "Atlus",
    0xEC: "Epic/Sony Records",
    0xEE: "IGS",
    0xF0: "A Wave",
    0xF3: "Extreme Entertainment",
    0xFF: "LJ"
}


CARTRIDGE_TYPES = {
    0x00: "ROM ONLY",
    0x01: "MBC1",
    0x02: "MBC1+RAM",
    0x03: "MBC1+RAM+BATTERY",
    0x05: "MBC2",
    0x06: "MBC2+BATTERY",
    0x08: "ROM+RAM 11",
    0x09: "ROM+RAM+BATTERY 11",
    0x0B: "MMM01",
    0x0C: "MMM01+RAM",
    0x0D: "MMM01+RAM+BATTERY",
    0x0F: "MBC3+TIMER+BATTERY",
    0x10: "MBC3+TIMER+RAM+BATTERY 12",
    0x11: "MBC3",
    0x12: "MBC3+RAM 12",
    0x13: "MBC3+RAM+BATTERY 12",
    0x19: "MBC5",
    0x1A: "MBC5+RAM",
    0x1B: "MBC5+RAM+BATTERY",
    0x1C: "MBC5+RUMBLE",
    0x1D: "MBC5+RUMBLE+RAM",
    0x1E: "MBC5+RUMBLE+RAM+BATTERY",
    0x20: "MBC6",
    0x22: "MBC7+SENSOR+RUMBLE+RAM+BATTERY",
    0xFC: "POCKET CAMERA",
    0xFD: "BANDAI TAMA5",
    0xFE: "HuC3",
    0xFF: "HuC1+RAM+BATTERY"
}


@dataclass
class Cartridge:
    type: int
    type_name: str
    header_checksum: bool
    nintendo_logo: bool
    title: str
    version: int
    manufacturer_code: int
    licensee: str
    rom_size: int
    rom_banks: int
    ram_size: int
    ram_banks: int
    destination_code: int
    destination: str
    content: bytearray


class CartridgeReader:
    ranges_content = {
        "nintendo_logo": (0x104, 0x133),
        "title": (0x134, 0x143),
        "manufacturer_code": (0x13F, 0x142),
        "CGB_flag": (0x143, 0x143),
        "new_licensee_code": (0x144, 0x145),
        "SGB_flag": (0x146, 0x146),
        "type": (0x147, 0x147),
        "old_licensee_code": (0x14B, 0x14B),
        "rom_size": (0x148, 0x148),
        "ram_size": (0x149, 0x149),
        "destination_code": (0x14A, 0x14A),
        "mask_rom_version_number": (0x14C, 0x14C),
        "header_checksum": (0x14D, 0x14D),
        "global_checksum": (0x14E, 0x14F)
    }

    def __init__(self, filename):
        self.file = open(filename, "rb")

    def read(self):
        self.content = bytearray(self.file.read())

    def get_fields(self):
        for field in self.ranges_content:
            _range = self.ranges_content[field]
            start, end = _range
            self.__dict__[field] = self.content[start: end+1]

    def check_logo(self):
        return self.nintendo_logo == NINTENDO_LOGO

    def handle_title(self):
        # get rid of null bytes
        stripped_title = self.title.replace(b'\x00', b'')
        if stripped_title.isascii():
            return stripped_title.decode("ASCII")
        return stripped_title

    def handle_licensee(self):
        olc = self.old_licensee_code[0]
        nlc = self.new_licensee_code[0]
        if olc == 0x33:
            licensee = NEW_LICENSEE_CODES.get(nlc, "Unknown")
        else:
            licensee = OLD_LICENSEE_CODES.get(olc, "Unknown")
        return licensee

    def handle_destination(self):
        code = self.destination_code[0]
        if code == 0x01:
            return "Overseas only"
        elif code == 0x00:
            return "Japan (and possibly overseas)"
        else:
            return "Unknown"

    def handle_rom_size(self):
        return 2**15 * (1 << self.rom_size[0])

    def handle_ram_size(self):
        raw = self.ram_size[0]
        if raw == 0x00:
            return 0
        elif raw == 0x01:
            return 0
        elif raw == 0x02:
            return 2**10 * 8
        elif raw == 0x03:
            return 2**10 * 32
        elif raw == 0x04:
            return 2**10 * 128
        elif raw == 0x05:
            return 2**10 * 64

    # the boot rom will do this checksum, python alternative
    def compute_header_checksum(self):
        checksum = 0
        for a in range(0x0134, 0x014C+1):
            checksum = (checksum - self.content[a] - 1) & 0xFF
        return checksum

    def _header_checksum(self) -> bool:
        return self.header_checksum[0] \
            == self.compute_header_checksum()

    def handle_rom_banks(self, rom_num):
        num_banks = dict((num, pow(2, num + 1)) for num in range(0, 9))
        num_banks.update({0x52: 72, 0x53: 80, 0x54: 96})
        return num_banks.get(rom_num, 0)

    def handle_ram_banks(self, ram_num):
        num_banks = {
            0x00: 0,
            0x01: 0,
            0x02: 1,
            0x03: 4,
            0x04: 16,
            0x05: 8
        }
        return num_banks.get(ram_num, 0)

    def get_cartridge(self) -> Cartridge:
        self.read()
        self.get_fields()
        cartridge = Cartridge(type=self.type[0],
                              type_name=CARTRIDGE_TYPES[self.type[0]],
                              header_checksum=self._header_checksum(),
                              nintendo_logo=self.check_logo(),
                              title=self.handle_title(),
                              version=self.mask_rom_version_number[0],
                              manufacturer_code=self.manufacturer_code,
                              licensee=self.handle_licensee(),
                              rom_size=self.handle_rom_size(),
                              rom_banks=self.handle_rom_banks(
                                  self.rom_size[0]),
                              ram_size=self.handle_ram_size(),
                              ram_banks=self.handle_ram_banks(
                                  self.ram_size[0]),
                              destination_code=self.destination_code[0],
                              destination=self.handle_destination(),
                              content=self.content)
        return cartridge


def identify():
    import sys
    # read a cartridge and get type data
    reader = CartridgeReader(sys.argv[1])
    c = reader.get_cartridge()
    print(f"""
    Cartridge type: {c.type_name} (0x{c.type:02X})
    Title: {c.title}
    By: {c.manufacturer_code}
    Licensee: {c.licensee}
    Version: {c.version}
    ROM size: {c.rom_size} bytes ({c.rom_banks} banks)
    RAM size: {c.ram_size} bytes
    Destination: {c.destination} (0x{c.destination_code:02X})
    Content length: {len(c.content)} bytes
    Valid Nintendo logo and header checksum: {c.nintendo_logo and c.header_checksum}
          """)


if __name__ == "__main__":
    identify()
