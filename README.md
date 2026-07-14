# hazelnut gameboy emulator
This is a gameboy emulator written with python and pygame.
![Gameplay showcase](showcases/showcase.gif)


## How to download and play

#### Clone the repo
```git clone https://github.com/atifcodesalot/hazelnut-gb-emu```

#### Install pygame
For unix generally:
```python3 -m pip install pygame```

on windows:
```py -m pip install pygame```


#### Run ROMS
On the repo root directory:
Unix:
```python3 -m hazelnut_gb_emu [Path to the rom file]```

Windows:

```py -m hazelnut_gb_emu [Path to the rom file]```


## Info on the emulator, disclaimers

- This emulator is currently not clock or machine cycle accurate: it does not emulate GameBoy hardware in full accuraccy. Due to this, you are likely to experience bugs every now and then.
- Due to the point above, it fails tests that expect full accurate hardware behaviour.
- It is in no way complete, just functional enough to run most commercial games.
- Only MBC1 and MBC3 are implemented for bank switching.
- It runs slower than the actual gameboy most of the time
- The APU unit is not implemented yet, hence no sound.
- the STOP instruction isn't implemented yet.
- Serial transfer is not implemented yet, resulting in bugs in Alleyway for example.

## Known bugs

- Alleyway serial bug
- Street Fighter 2 periodically rendering giberrish due to PPU and CPU sync problems.
