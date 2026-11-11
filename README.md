# Hazelnut :chipmunk: <img src="https://upload.wikimedia.org/wikipedia/commons/f/f2/Nintendo_Game_Boy_Logo.svg?utm_source=commons.wikimedia.org&utm_campaign=index&utm_content=original" style="height: 1em; vertical-align: middle;"> and <img src="https://en.wikipedia.org/wiki/File:Game_Boy_Color_logo.svg" style="height: 1em; vertical-align: middle;"> emulator
Hazelnut is a [Game Boy](https://en.wikipedia.org/wiki/Game_Boy) and [Game Boy Color](https://en.wikipedia.org/wiki/Game_Boy_Color) emulator written solo with python and pygame, only for learning and fun.


<img width="420" height="379" alt="showcase" src="https://github.com/user-attachments/assets/52936142-2c03-49cf-af81-6f85109c6161" />


## Some Screenshots
<img width="179" height="317" alt="hmoon" src="https://github.com/user-attachments/assets/82d4ee27-fe66-4065-a0b4-ba51a99251d8" />
<img width="180" height="376" alt="magikarp" src="https://github.com/user-attachments/assets/43f9cc81-8fa7-4d8f-8061-2dc15b1db9e3" />
<img width="181" height="374" alt="chessmaster" src="https://github.com/user-attachments/assets/d18dc78b-27c9-4f82-bf03-f239c67b41e0" />

<img width="178" height="325" alt="metroid" src="https://github.com/user-attachments/assets/031d25ea-364b-405c-940d-695df845fcbd" />
<img width="181" height="320" alt="wario" src="https://github.com/user-attachments/assets/b5fd3a24-bde3-4681-a21f-e45fcfd8afc3" />


## Legal notice

hazelnut-gb-emu is an independent, non-commercial hobby project created
for educational and research purposes.

This project is not affiliated with, authorized by, sponsored by, or endorsed
by Nintendo Co., Ltd. or any of its subsidiaries.

Nintendo, Game Boy, Pokémon, Kirby, The Legend of Zelda, and other related
names and marks are trademarks or intellectual property of their respective
owners.

No copyrighted game ROMs, boot ROMs, firmware, encryption keys, or proprietary
game assets are distributed with this repository. Users are responsible for
providing any required game data from legally obtained sources.

Gameplay footage and screenshots are included solely to demonstrate emulator
compatibility. All rights to the depicted games and assets remain with their
respective owners.


## How to download and play

## The PyPy runtime

The [PyPy](https://pypy.org/) runtime is heavily recommended for this emulator, if you want consistent 
real GameBoy speed. You don't need to install it yourself though: automatic installation is supported, which you will be initially prompted to upon executing the package.

#### Clone the repo
```git clone https://github.com/atifcodesalot/hazelnut-gb-emu```

#### Install pygame
For unix generally:
```python3 -m pip install pygame```

on windows:
```py -m pip install pygame```


#### Run ROMS
On the repo root directory:
Unix (Darwin or Linux):
```python3 -m hazelnut_gb_emu```

Windows:

```py -m hazelnut_gb_emu```

First choose if you want to play Gameboy Color or gameboy by providing a `--color` or `-cgb` flag 
in the command line, or not if you want to play Gameboy only. Note: The gameboy color is backwards compatible with the gameboy roms as well.
Then choose if you want to download and use PyPy, by pressing y or n then enter,
afterwards choose a ROM file to play, simple.


## Info on the emulator, disclaimers

### Technical Stuff, skippable if you don't care :yum:
Hazelnut is instruction stepped for the Gameboy timers and its SM83 processor,
however PPU mode boundaries happen after long cpu and timer bursts, therefore it is effectively
a scanline mode stepped emulator. This model is good enough for almost all games in GameBoy (except one), but GameBoy Color is able to expose this limitation further with the double speed mode.

##### Double Speed Mode and why it is problematic for Hazelnut
Hazelnut executes CPU instructions between PPU modes. Double speed mode increases the CPU clock
of the GameBoy processor from approx. 4 MHz to 8. This doubles the cycles between PPU modes because
the actually PPU does not double its speed! Meaning more CPU bursts between mode boundaries: more inaccurate.
Because the real hardware runs every system: APU, PPU and CPU concurrently. I will possibly make
the emulator truly instruction stepped in the future so this issue will (hopefully) bite the dust.



### General Disclaimers
- As mentioned, this emulator is currently not clock or machine cycle accurate: it does not emulate GameBoy hardware in full accuraccy.
It is instead instruction stepped, due to this, you will experience bugs every now and then (expecially for GBC).
- It is functional enough to run almost all commercial games for the Gameboy, but GAmeBoy Color is not as stable due to the reasons mentioned above.
- MBC1, MBC2, MBC3 (with RTC registers) and MBC5 are implemented for bank switching (MBC6, MBC7 is next :yum:).
- It may run slower than the actual gameboy with [CPython](https://en.wikipedia.org/wiki/CPython) (60 fps normally), except if you use PyPy, then it can run x8 with ease.
- The APU unit is in development, hence no sound yet.

## Credits and AI usage
%99 of the code and the full CPU, PPU implementations for the Gameboy and Gameboy Color are written by me only. Rarely, some functions were refactored, enchanced by AI: no code was generated from scratch, or no agentic code was used.

AI was instead used extensively, only for; bug hunting, disassembly and optimization problems. 

## Known bugs
### GameBoy Color
- FIFA 2000 unplayable due to STAT line boundaries
- Pokemon Puzzle Challenge crashing after mode selection 
- Tomb Raider unplayable due to unknown reasons (likely due to double speed mode as well)


### GameBoy
- Robocop 2 stalls after boot due to a narrow ly=144 check for game startup,
might be fixed in the future.


## TODOs (from the most possible to insane):
- finish APU implementation
- Make the PPU instruction stepped as well
- Upgrade to clock cycle atomicity (very hard) 
