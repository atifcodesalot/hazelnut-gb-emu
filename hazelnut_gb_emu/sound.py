



# skeleton of the APU, not even close to being correct
# don't use it for playing




from .memory import GBMemoryController
import pygame
import numpy as np
from .auxiliary import BO


PCM_SAMPLE_RATE = 44100
MASTER_CLK = 4194304

BUFFER_UPDATE_TIME = 0.01  # in seconds
BUFFER_SIZE = int(PCM_SAMPLE_RATE * BUFFER_UPDATE_TIME)


# mono sound
pygame.mixer.init(frequency=PCM_SAMPLE_RATE, size=8, channels=1)
#


SILENCE = 0x80


class GBPulseWave:
    duty_pattern = [
        [0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 1, 1, 1],
        [0, 1, 1, 1, 1, 1, 1, 0]
    ]

    def __init__(self, duty_cycle, period, volume):
        self.duty_cycle = duty_cycle
        self.volume = volume
        # in dots
        self.period = period
        #
        self.step = self.period // 8
        self.set_waveform()
        self.dots = 0

    def sample_for(self, dots_elapsed):
        ons = 0

        remaining = self.period - self.dots
        if remaining > dots_elapsed:
            ons += sum(self.waveform[self.dots: self.dots + dots_elapsed])
            self.dots += dots_elapsed
            return ons
        ons += sum(self.waveform[self.dots:])
        dots_elapsed -= remaining
        elapsed_periods = dots_elapsed // self.period
        ons += elapsed_periods * self.duty_time * self.period
        ons += sum(self.waveform[:dots_elapsed % self.period])

        self.dots = dots_elapsed % self.period

        return ons

    def set_duty_time(self):
        self.duty_time = self.duty_cycle * 0.25 if self.duty_cycle else 0.125

    def set_waveform(self):
        self.waveform = [b for b in self.duty_pattern[self.duty_cycle]
                         for _ in range(self.step)]
        self.set_duty_time()

    def set_period(self, new_period):
        self.period = new_period
        self.step = self.period // 8
        self.set_waveform()

    def set_duty(self, new_duty_cycle):
        self.duty_cycle = new_duty_cycle
        self.set_waveform()

    def set_volume(self, new_volume):
        # clamp to 4 bit
        self.volume = (new_volume) & 0xF


class GBPulseChannel:
    def __init__(self, memctl: GBMemoryController, num):
        self.memctl = memctl
        self.num = num
        self.pw = GBPulseWave(*[0,]*3)
        self.get_registers()
        self.get_period()
        self.get_volume()
        self.get_duty_cycle()

        self.ltimer = 0x100000  # length timer
        self.env_timer = 0  # envelope timer
        self.sample_accumulator = 0

        self.disabled = True

    def get_period(self):
        P = ((self.reg_hi_ctl.value & 0x07) << 8) | self.reg_period_lo.value
        self.pw.set_period((2048 - P) << 5)

    def get_volume(self):
        self.pw.set_volume((self.reg_vol_env.value >> 4) & 0xF)

    def get_duty_cycle(self):
        duty = (self.reg_duty_timer.value >> 6) & 0x3
        self.pw.set_duty(duty)

    def get_env(self):
        pass

    def get_length_timer(self):
        pass

    def get_registers(self):
        offset = 5 * self.num
        self.reg_duty_timer = self.memctl.io_registers[0xFF11 + offset]
        self.reg_vol_env = self.memctl.io_registers[0xFF12 + offset]
        self.reg_period_lo = self.memctl.io_registers[0xFF13 + offset]
        self.reg_hi_ctl = self.memctl.io_registers[0xFF14 + offset]

    def accumulate_for(self, cycles):
        self.sample_accumulator += \
            self.pw.sample_for(cycles) * self.pw.volume

    # accumulation step for an inactive channel with DAC on
    # until the High Pass filter is implemented in the future
    def accumulate_silence(self, cycles):
        self.sample_accumulator += 7.5 * cycles

    def update(self):
        self.get_period()
        self.get_volume()
        self.get_duty_cycle()

    def trigger(self):
        self.disabled = False
        master = self.memctl.io_registers[0xFF26].value
        self.memctl.io_registers[0xFF26].value = BO.set_nth_bit(
            master, self.num)
        # reset the length timer
        if self.ltimer == 0:
            self.ltimer = 0x100000
        self.pw.dots = 0

    def DAC_on(self):
        return self.reg_vol_env.value & 0xF8 != 0

    # does not turn the DAC off
    def turn_off(self):
        master = self.memctl.io_registers[0xFF26].value
        new_master = BO.res_nth_bit(master, self.num)
        self.memctl.io_registers[0xFF26].value = new_master
        self.disabled = True


class GBChannel1(GBPulseChannel):
    def __init__(self, memctl):
        super().__init__(memctl, num=0)
        # sweep register only for channel 1
        self.reg_sweep = self.memctl.io_registers[0xFF10]
        #


class GBChannel2(GBPulseChannel):
    def __init__(self, memctl):
        super().__init__(memctl, num=1)


# voluntary waveform channel
class GBChannel3():
    def __init__(self, memctl):
        self.memctl = memctl
        self.get_registers()

        self.ltimer = 0x100000

        self.phase = 0
        self.ram_i = 0
        self.sample_accumulator = 0
        self.get_period_step()
        self.get_volume()

        self.disabled = False

    def read_waveRAM(self):
        # get the correct nible from wave ram
        # wave ram starts fro 0xFF30
        sample = self.memctl.io_registers[0xFF30 + self.ram_i // 2].value
        return sample & 0xF if self.ram_i % 2 else (sample >> 4) & 0xF

    def tick(self):
        sample = self.read_waveRAM()
        # adjust volume
        if self.volume:
            sample >>= self.volume - 1
        else:
            sample = 0
        #
        self.sample_accumulator += sample
        # adjust counters
        self.phase = (self.phase + 1) % self.period
        self.ram_i = self.phase // self.step
        #

    def accumulate_for(self, cycles):
        for _ in range(cycles):
            self.tick()

    def accumulate_silence(self):
        self.sample_accumulator += 7.5

    def get_registers(self):
        self.reg_DAC_en = self.memctl.io_registers[0xFF1A]
        self.reg_timer = self.memctl.io_registers[0xFF1B]
        self.reg_volume = self.memctl.io_registers[0xFF1C]
        self.reg_period_lo = self.memctl.io_registers[0xFF1D]
        self.reg_hi_ctl = self.memctl.io_registers[0xFF1E]

    def get_period_step(self):
        P = ((self.reg_hi_ctl.value & 0x07) << 8) | self.reg_period_lo.value
        self.step = (2048 - P) * 2
        self.period = (2048 - P) << 6

    def get_volume(self):
        self.volume = ((self.reg_volume.value >> 5) & 0x3)

    def update(self):
        self.get_period_step()
        self.get_volume()

    def trigger(self):
        master = self.memctl.io_registers[0xFF26].value
        self.memctl.io_registers[0xFF26].value = BO.set_nth_bit(
            master, 2)

        if self.ltimer == 0:
            self.ltimer = 0x100000

    def DAC_on(self):
        return self.reg_DAC_en.value >> 7 & 1

    def turn_off(self):
        master = self.memctl.io_registers[0xFF26].value
        new_master = BO.res_nth_bit(master, 2)
        self.memctl.io_registers[0xFF26].value = new_master
        self.disabled = True


class GBNoiseChannel():
    def __init__(self, memctl):
        self.memctl = memctl
        self.get_registers()
        self.get_volume()
        self.lfsr = 0
        self.sample_accumulator = 0
        self.silent = 0

    def get_registers(self):
        self.reg_timer = self.memctl.io_registers[0xFF20]
        self.reg_vol_env = self.memctl.io_registers[0xFF21]
        self.reg_randomness = self.memctl.io_registers[0xFF22]
        self.reg_ctl = self.memctl.io_registers[0xFF23]

    def get_volume(self):
        self.volume = (self.reg_vol_env.value >> 4) & 0xF

    def shift(self):
        # Tap bit 0 and 1
        new_hi = ~ ((self.lfsr & 1) ^ ((self.lfsr >> 1) & 1) & 1)
        self.lfsr = new_hi | (self.lsfr >> 1)
        # get the new LSB
        self.silent = self.self.lsfr & 1

    def accumulate_silence(self):
        self.sample_accumulator += 7.5

    def tick(self):
        self.sample_accumulator += self.silent * self.volume

    def trigger(self):
        self.lsfr = 0x7FFF

    def DAC_on(self):
        return self.reg_vol_env.value & 0xF8 != 0


class GbAPU:
    def __init__(self, memctl: GBMemoryController, gb):
        # placeholder
        self.master_volume = 1
        #
        self.dots = 0
        self.gb = gb
        self.memctl = memctl
        self.reg_master = memctl.io_registers[0xFF26]
        self.reg_panning = memctl.io_registers[0xFF25]

        self.init_buffers()

        self.ch1 = GBChannel1(self.memctl)
        self.ch2 = GBChannel2(self.memctl)
        self.ch3 = GBChannel3(self.memctl)
        self.ch4 = GBNoiseChannel(self.memctl)
        # todo: add the noise channel

        self.gb_channels = [self.ch1, self.ch2, self.ch3]

        self.samples_sec = 0
        self.samples = 0
        self.ring = 0
        self.accm = 95

        self.queued = False

    def audio_on(self):
        return (self.reg_master.value >> 7) & 1

    def get_active(self):
        active = self.reg_master.value & 0x0F
        return active

    def init_buffers(self):
        self.buffer_size = int(PCM_SAMPLE_RATE * BUFFER_UPDATE_TIME)
        self.snd_portion1 = pygame.mixer.Sound(
            np.array([SILENCE] * self.buffer_size, dtype=np.uint8))
        self.snd_portion2 = pygame.mixer.Sound(
            np.array([SILENCE] * self.buffer_size, dtype=np.uint8))
        self.rbuffer1 = pygame.sndarray.samples(self.snd_portion1)
        self.rbuffer2 = pygame.sndarray.samples(self.snd_portion2)
        self.buffers = [self.rbuffer1, self.rbuffer2]
        self.pgchannel = pygame.mixer.Channel(0)

    def mix(self, ch1, ch2, ch3, ch4):
        mixed = (ch1 + ch2 + ch3 + ch4) / 4
        # convert to 8 bit unsigned audio
        return 17 * mixed * self.master_volume
        #

    def handle_envelope(self):
        pass

    def handle_sweep(self):
        sweep_ctl = self.ch1.reg_sweep.value
        _dir = (sweep_ctl >> 3) & 1
        step = sweep_ctl & 0x7
        new_period = self.ch1.pw.period >> step if _dir else self.ch1.pw.period << step
        self.ch1.reg_period_lo.value = new_period & 0xFF
        val = self.ch1.reg_hi_ctl.value
        self.ch1.reg_hi_ctl.value = (val & 0xF8) | ((new_period >> 8) & 0x07)

    def emit_PCM_sample(self, buffer):
        # average channel samples over 95 dots
        ch1avg = self.ch1.sample_accumulator / self.accm if self.ch1.DAC_on() else 0
        ch2avg = self.ch2.sample_accumulator / self.accm if self.ch2.DAC_on() else 0
        ch3avg = self.ch3.sample_accumulator / self.accm if self.ch3.DAC_on() else 0
        ch4avg = self.ch4.sample_accumulator / self.accm if self.ch4.DAC_on() else 0
        #

        # reset accumulators
        self.ch1.sample_accumulator = 0
        self.ch2.sample_accumulator = 0
        self.ch3.sample_accumulator = 0
        self.ch4.sample_accumulator = 0
        #

        mixed = self.mix(ch1avg, ch2avg, ch3avg, 0)
        self.buffers[buffer][self.ring % self.buffer_size] = mixed
        self.ring = (self.ring + 1) % (self.buffer_size * 2)
        if self.ring == self.buffer_size:
            self.pgchannel.queue(self.snd_portion1)
        elif self.ring == 0:
            self.pgchannel.queue(self.snd_portion2)
        self.samples_sec += 1
        
        if self.samples_sec == PCM_SAMPLE_RATE:
            self.samples_sec = 0
            self.dots = 0
            self.accm = MASTER_CLK // PCM_SAMPLE_RATE
            return
        remaining_pcm = PCM_SAMPLE_RATE - self.samples_sec
        remaining_cycles = MASTER_CLK - self.dots
        self.accm = remaining_cycles // remaining_pcm
        
    def handle_len_counters(self):
        if self.ch1.reg_hi_ctl.value & 0x40:
            # channel 1 length counter enabled
            if not self.ch1.ltimer != 0:
                self.ch1.ltimer -= 1
            else:
                self.ch1.turn_off()
        if self.ch2.reg_hi_ctl.value & 0x40:
            if not self.ch2.ltimer != 0:
                self.ch2.ltimer -= 1
            else:
                self.ch2.turn_off()
        if self.ch3.reg_hi_ctl.value & 0x40:
            if not self.ch3.ltimer != 0:
                self.ch3.ltimer -= 1
            else:
                self.ch3.turn_off()

    def accumulate_samples(self, active, cycles):
        # force channels for now
        if True:  # active & 1:
            # channel 1 is active
            self.ch1.accumulate_for(cycles)
        else:
            self.ch1.accumulate_silence(cycles)
        if True:  # (active >> 1) & 1:
            self.ch2.accumulate_for(cycles)
        else:
            self.ch2.accumulate_silence(cycles)
        if True:  # (active >> 2) & 1:
            self.ch3.accumulate_for(cycles)
        else:
            self.ch3.accumulate_silence()
        # if (active >> 3) & 1:
        #     # channel 4 is active
        #     self.ch4.tick()
        # else:
        #     self.ch4.accumulate_silence()

    def triggers_edge(self, dots, period, elapsed):
        return dots // period != (dots + elapsed) // period

    def tick_cycles(self, cycles):
        active = self.get_active()
        elapsed = cycles
        old = self.dots

        while cycles > 0:
            dots_until_sample = self.accm - self.samples
            chunk = min(cycles, dots_until_sample)

            self.accumulate_samples(active, chunk)

            self.samples += chunk
            cycles -= chunk

            self.dots = (self.dots + chunk) % MASTER_CLK

            if self.samples == self.accm:
                buffer = self.ring // self.buffer_size
                self.emit_PCM_sample(buffer)
                self.samples = 0

        counter_trigger = self.triggers_edge(old, 0x4000, elapsed)
        sweep_trigger = self.triggers_edge(old, 0x8000, elapsed)
        envelope_trigger = self.triggers_edge(old, 0xFFFF + 1, elapsed)

        if counter_trigger:
            self.handle_len_counters()

        if sweep_trigger:
            self.handle_sweep()

        if envelope_trigger:
            self.handle_envelope()
