# skeleton of the APU, not even close to being correct
# don't use it for playing
from .memory import GBMemoryController
import pygame
import numpy as np
from .auxiliary import BO

PCM_SAMPLE_RATE = 44100
MASTER_CLK = 0x400000
FRAME_SEQ = 0x10000
BUFFER_UPDATE_TIME = 0.1  # in seconds
BUFFER_SIZE = int(PCM_SAMPLE_RATE * BUFFER_UPDATE_TIME)

# mono sound for now
pygame.mixer.init(
    frequency=PCM_SAMPLE_RATE,
    size=8,
    channels=1,
    # dont allow any changes to the mixer (looking at you windows)
    allowedchanges=0,
)
#

SILENCE = 0x80


class GBPulseWave:
    duty_pattern = [
        [0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 1, 1, 1],
        [0, 1, 1, 1, 1, 1, 1, 0],
    ]

    def __init__(self, duty_cycle, period):
        self.duty_cycle = duty_cycle
        # in dots
        self.period = period
        # amplitude repetition
        self.amprep = self.period >> 3
        self.set_waveform()
        self.phase = 0

    def sample_for(self, cycles):
        ons = 0
        wave_remaining = self.period - self.phase
        if wave_remaining > cycles:
            rem = wave_remaining - cycles
            ons += ((self.waveform >> rem) & ((1 << cycles) - 1)).bit_count()
            self.phase += cycles
            return ons
        ons += (self.waveform & ((1 << wave_remaining) - 1)).bit_count()
        cycles_remaining = cycles - wave_remaining

        periods, period_rem = divmod(cycles_remaining, self.period)
        ons += periods * self.duty_time * self.period
        ons += (
            (self.waveform >> (self.period - period_rem)) & ((1 << period_rem) - 1)
        ).bit_count()
        self.phase = period_rem
        return ons

    def set_duty_time(self):
        self.duty_time = self.duty_cycle * 0.25 if self.duty_cycle else 0.125

    def set_waveform(self):
        repeats = [0, (1 << self.amprep) - 1]
        self.waveform = 0
        for bit in self.duty_pattern[self.duty_cycle]:
            self.waveform <<= self.amprep
            self.waveform |= repeats[bit]
        self.set_duty_time()

    def set_period(self, new_period):
        self.period = new_period
        self.amprep = self.period >> 3
        self.phase %= self.period
        self.set_waveform()

    def set_duty(self, new_duty_cycle):
        self.duty_cycle = new_duty_cycle
        self.set_waveform()


class GBPulseChannel:
    def __init__(self, memctl: GBMemoryController, num):
        self.memctl = memctl
        self.num = num
        self.pw = GBPulseWave(
            *[
                0,
            ]
            * 2
        )
        self.get_registers()
        self.get_period()
        self.get_volume()
        self.get_duty_cycle()
        self.ltimer = 0x100000  # length timer
        self.env_timer = 0  # envelope timer
        self.sample_accumulator = 0

        self.active = False

    def get_period(self):
        self.period_value = ((self.reg_hi_ctl.value & 0x07) << 8) \
            | self.reg_period_lo.value
        self.pw.set_period((2048 - self.period_value) << 5)

    def get_volume(self):
        self.volume = (self.reg_vol_env.value >> 4) & 0xF

    def set_volume(self, new_volume):
        self.volume = min(max(0, new_volume), 0xF)

    def get_duty_cycle(self):
        duty = (self.reg_duty_timer.value >> 6) & 0x3
        self.pw.set_duty(duty)

    def get_registers(self):
        offset = 5 * self.num
        self.reg_duty_timer = self.memctl.io_registers[0xFF11 + offset]
        self.reg_vol_env = self.memctl.io_registers[0xFF12 + offset]
        self.reg_period_lo = self.memctl.io_registers[0xFF13 + offset]
        self.reg_hi_ctl = self.memctl.io_registers[0xFF14 + offset]

    def accumulate_for(self, cycles):
        self.sample_accumulator += self.pw.sample_for(cycles) * self.volume

    # accumulation step for an inactive channel with DAC on
    # until the High Pass filter is implemented in the future
    def accumulate_silence(self, cycles):
        self.sample_accumulator += 7.5 * cycles

    def get_trigger(self):
        if self.reg_hi_ctl.value >> 7 & 1:
            self.trigger()

    def get_DAC(self):
        if not self.DAC_on():
            self.turn_off()

    def update(self):
        self.get_period()
        self.get_volume()
        self.get_duty_cycle()
        self.get_trigger()

    def trigger(self):
        if not self.DAC_on():
            return
        self.active = True
        master = self.memctl.io_registers[0xFF26].value
        self.memctl.io_registers[0xFF26].value = BO.set_nth_bit(master, self.num)
        # reset the length timer
        if self.ltimer == 0:
            self.ltimer = 0x100000
        self.env_timer = (self.reg_vol_env.value & 7) or 8
        self.pw.dots = 0

    def DAC_on(self):
        return self.reg_vol_env.value & 0xF8 != 0

    # does not turn the DAC off
    def turn_off(self):
        master = self.memctl.io_registers[0xFF26].value
        new_master = BO.res_nth_bit(master, self.num)
        self.memctl.io_registers[0xFF26].value = new_master
        self.active = False


class GBChannel1(GBPulseChannel):
    def __init__(self, memctl):
        super().__init__(memctl, num=0)
        # sweep register only for channel 1
        self.reg_sweep = self.memctl.io_registers[0xFF10]
        self.sweep_timer = 0
        #

    def get_sweep_timer(self):
        self.sweep_timer = self.reg_sweep.value >> 4 & 7 

    def update(self):
        super().update()
        self.get_sweep_timer()


class GBChannel2(GBPulseChannel):
    def __init__(self, memctl):
        super().__init__(memctl, num=1)


# voluntary waveform channel
class GBChannel3:
    def __init__(self, memctl):
        self.memctl = memctl
        self.get_registers()
        self.ltimer = 0x100000
        self.dots = 0
        self.phase = 0
        self.phase_rem = 0
        self.sample_accumulator = 0
        self.get_period_step()
        self.get_volume()
        self.active = False

        # 32 4 bit samples
        self.cached_wave = [0] * 32

    def cache_waveform(self):
        m = self.memctl
        for i in range(16):
            b = m.io_registers[0xFF30 + i].value
            self.cached_wave[2 * i] = (b >> 4 & 0xF) >> self.volshift
            self.cached_wave[2 * i + 1] = (b & 0xF) >> self.volshift

    def accumulate_for(self, cycles):
        self.dots += cycles

        # get the wrapped period
        periods, cycle_shift = divmod(cycles, self.period)

        norm_cycles = max(cycle_shift - self.phase_rem, 0)
        phase_shift, phase_mod = divmod(norm_cycles, self.amprep)

        cw = self.cached_wave
        if periods:
            wave_sum = sum(cw) * self.amprep
            self.sample_accumulator += wave_sum * periods

        # Complete waveforms only: phase state is unchanged
        if cycle_shift == 0:
            return

        # Still inside the current amplitude
        if 0 < self.phase_rem and cycle_shift < self.phase_rem:
            self.sample_accumulator += cw[self.phase] * cycle_shift
            self.phase_rem -= cycle_shift
            return

        if self.phase_rem > 0:
            # if the phase remainder is non-zero
            self.sample_accumulator += cw[self.phase] * min(self.phase_rem, cycle_shift)
            if cycle_shift >= self.phase_rem:
                self.phase += 1

        # after normalizing to phase start
        shifted_phase = self.phase + phase_shift
        if shifted_phase > 31:
            self.sample_accumulator += sum(cw[self.phase :]) * self.amprep
            remaining = shifted_phase - 32
            self.sample_accumulator += sum(cw[:remaining]) * self.amprep
        else:
            self.sample_accumulator += sum(cw[self.phase : shifted_phase]) * self.amprep

        self.phase = shifted_phase % 32
        self.sample_accumulator += cw[self.phase] * phase_mod
        self.phase_rem = self.amprep - phase_mod if phase_mod != 0 else 0

    def accumulate_silence(self, cycles):
        self.sample_accumulator += 7.5 * cycles

    def get_registers(self):
        self.reg_DAC_en = self.memctl.io_registers[0xFF1A]
        self.reg_timer = self.memctl.io_registers[0xFF1B]
        self.reg_volume = self.memctl.io_registers[0xFF1C]
        self.reg_period_lo = self.memctl.io_registers[0xFF1D]
        self.reg_hi_ctl = self.memctl.io_registers[0xFF1E]

    def get_period_step(self):
        P = ((self.reg_hi_ctl.value & 0x07) << 8) | self.reg_period_lo.value
        self.amprep = (2048 - P) << 1
        self.period = (2048 - P) << 6

    def get_volume(self):
        self.volume = (self.reg_volume.value >> 5) & 0x3
        self.volshift = max(self.volume - 1, 0)

        # update cached wave
        if self.volshift == 0:
            self.cached_wave = [0] * 32
            return

        for i in range(32):
            self.cached_wave[i] >>= self.volshift

    def get_trigger(self):
        if self.reg_hi_ctl.value >> 7 & 1:
            self.trigger()

    def get_DAC(self):
        if not self.DAC_on():
            self.turn_off()

    def update(self):
        self.get_period_step()
        self.get_volume()
        self.get_trigger()
        self.get_DAC()

    def trigger(self):
        if not self.DAC_on():
            return
        self.active = True
        master = self.memctl.io_registers[0xFF26].value
        self.memctl.io_registers[0xFF26].value = BO.set_nth_bit(master, 2)
        if self.ltimer == 0:
            self.ltimer = 0x100000

    def DAC_on(self):
        return self.reg_DAC_en.value >> 7 & 1

    def turn_off(self):
        master = self.memctl.io_registers[0xFF26].value
        new_master = BO.res_nth_bit(master, 2)
        self.memctl.io_registers[0xFF26].value = new_master
        self.active = False


class GBNoiseChannel:
    def __init__(self, memctl):
        self.memctl = memctl
        self.get_registers()
        self.get_volume()
        self.lfsr = 0
        self.sample_accumulator = 0

        self.internal_timer = 0
        self.env_timer = 0
        self.active = False

        self.shifted = 0

    def get_registers(self):
        self.reg_timer = self.memctl.io_registers[0xFF20]
        self.reg_vol_env = self.memctl.io_registers[0xFF21]
        self.reg_randomness = self.memctl.io_registers[0xFF22]
        self.reg_ctl = self.memctl.io_registers[0xFF23]

    def get_volume(self):
        self.volume = (self.reg_vol_env.value >> 4) & 0xF

    def set_volume(self, new_volume):
        self.volume = min(max(0, new_volume), 0xF)

    def shift(self, short_mode):
        # Tap bit 0 and 1
        feedback = ~(self.lfsr ^ (self.lfsr >> 1)) & 1
        # shift
        self.lfsr = (feedback << 14) | (self.lfsr >> 1)
        if short_mode:
            # tap bit 7 as well if short mode
            self.lfsr = (self.lfsr & ~0x40) | (feedback << 6)
        sample = self.lfsr & 1
        return sample * self.volume

    def get_shift_freq(self):
        rand_clk = self.reg_randomness.value
        clk_div = rand_clk & 7
        clk_div = clk_div if clk_div != 0 else 0.5
        clk_shift = (rand_clk >> 4) & 0xF
        self.shift_freq = 0x40000 / (clk_div * (1 << clk_shift))
        self.timer_period = int(MASTER_CLK // self.shift_freq)

    def accumulate_for(self, cycles):
        short_mode = self.reg_randomness.value >> 3 & 1
        init_rem = self.timer_period - self.internal_timer
        if init_rem >= cycles:
            self.sample_accumulator += self.shifted * cycles
            self.internal_timer = (self.internal_timer + cycles) % self.timer_period
            if init_rem == cycles:
                self.shifted = self.shift(short_mode)
            return
        else:
            self.sample_accumulator += self.shifted * init_rem
            self.shifted = self.shift(short_mode)
            
        cycles_rem = cycles - init_rem
        shift_periods, final_rem = divmod(cycles_rem, self.timer_period)
        for _ in range(shift_periods):
            self.sample_accumulator += self.shifted * self.timer_period
            self.shifted = self.shift(short_mode)
    
        self.sample_accumulator += self.shifted * final_rem
        self.internal_timer = final_rem

    def accumulate_silence(self, cycles):
        self.sample_accumulator += 7.5 * cycles

    def trigger(self):
        self.lfsr = 0
        self.env_timer = (self.reg_vol_env.value & 7) or 8
        self.active = True

    def DAC_on(self):
        return self.reg_vol_env.value & 0xF8 != 0

    def turn_off(self):
        master = self.memctl.io_registers[0xFF26].value
        new_master = BO.res_nth_bit(master, 3)
        self.memctl.io_registers[0xFF26].value = new_master
        self.active = False

    def get_DAC(self):
        if not self.DAC_on():
            self.turn_off()

    def update(self):
        self.get_volume()
        self.get_shift_freq()
        self.get_DAC()


class GbAPU:
    def __init__(self, memctl: GBMemoryController):
        # placeholder
        self.master_volume = 1
        #
        self.dots = 0
        self.memctl = memctl
        self.gb = self.memctl.gameboy
        self.reg_master = memctl.io_registers[0xFF26]
        self.reg_panning = memctl.io_registers[0xFF25]
        self.init_buffers()
        self.ch1 = GBChannel1(self.memctl)
        self.ch2 = GBChannel2(self.memctl)
        self.ch3 = GBChannel3(self.memctl)
        self.ch4 = GBNoiseChannel(self.memctl)
        self.gb_channels = [self.ch1, self.ch2, self.ch3, self.ch4]
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
            np.array([1] * self.buffer_size, dtype=np.uint8)
        )
        self.snd_portion2 = pygame.mixer.Sound(
            np.array([1] * self.buffer_size, dtype=np.uint8)
        )
        self.rbuffer1 = pygame.sndarray.samples(self.snd_portion1)
        self.rbuffer2 = pygame.sndarray.samples(self.snd_portion2)
        self.buffers = [self.rbuffer1, self.rbuffer2]
        self.pgchannel = pygame.mixer.Channel(0)

    def mix(self, ch1, ch2, ch3, ch4):
        mixed = (ch1 + ch2 + ch3 + ch4) / 4
        # convert to 8 bit unsigned audio
        return int(17 * mixed * self.master_volume) & 0xFF
        #

    def tick_channel_envelope(self, ch):
        env_ctl = ch.reg_vol_env.value
        env_dir = env_ctl >> 3 & 1
        ch.env_timer -= 1
        if ch.env_timer == 0:
            env_pace = env_ctl & 7
            if env_pace:
                if env_dir:
                    ch.set_volume(ch.volume + 1)
                else:
                    ch.set_volume(ch.volume - 1)
            # reset envelope timer to pace
            ch.env_timer = env_pace or 8

    def handle_envelope(self):
        self.tick_channel_envelope(self.ch1)
        self.tick_channel_envelope(self.ch2)
        self.tick_channel_envelope(self.ch4)

    # frequency sweep
    def handle_sweep(self):
        sweep_ctl = self.ch1.reg_sweep.value
        sweep_dir = sweep_ctl >> 3 & 1
        sweep_pace = sweep_ctl >> 4 & 7
        if sweep_pace == 0:
            # sweep iterations are disabled
            return
        self.ch1.sweep_timer -= 1
        step = sweep_ctl & 0x7
        dfreq = self.ch1.period_value >> step
        if self.ch1.sweep_timer == 0:
            # reset sweep timer
            self.ch1.sweep_timer = sweep_pace
            #
            if sweep_dir:
                self.ch1.period_value -= dfreq
            else:
                self.ch1.period_value += dfreq
        new_pval = self.ch1.period_value
        if new_pval > 0x7FF:
            # period overflow
            self.ch1.turn_off()
            return
        # update pulse channel period
        self.ch1.pw.set_period((2048 - new_pval) << 5)
        #
        self.ch1.reg_period_lo.value = new_pval & 0xFF
        val = self.ch1.reg_hi_ctl.value
        self.ch1.reg_hi_ctl.value = (val & 0xF8) | ((new_pval >> 8) & 0x07)

    def handle_buffer_boundary(self):
        if self.ring == self.buffer_size:
            # if not self.pgchannel.get_busy():
            #     print("UNDERRUN!!!")
            # if self.pgchannel.get_queue() is not None:
            #     print("OVERRUN!!!")
            self.pgchannel.queue(self.snd_portion1)

        elif self.ring == 0:
            # if not self.pgchannel.get_busy():
            #     print("UNDERRUN!!!")
            # if self.pgchannel.get_queue() is not None:
            #     print("OVERRUN!!!")
            self.pgchannel.queue(self.snd_portion2)

    def emit_PCM_sample(self, buffer):
        # average channel samples over 95 dots
        ch1avg = self.ch1.sample_accumulator / self.accm
        ch2avg = self.ch2.sample_accumulator / self.accm 
        ch3avg = self.ch3.sample_accumulator / self.accm 
        ch4avg = self.ch4.sample_accumulator / self.accm 
        #
        # reset accumulators
        self.ch1.sample_accumulator = 0
        self.ch2.sample_accumulator = 0
        self.ch3.sample_accumulator = 0
        self.ch4.sample_accumulator = 0
        #
        mixed = self.mix(ch1avg, ch2avg, ch3avg, ch4avg)
        self.buffers[buffer][self.ring % self.buffer_size] = mixed
        self.ring = (self.ring + 1) % (self.buffer_size * 2)

        self.handle_buffer_boundary()

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
            if self.ch1.ltimer != 0:
                self.ch1.ltimer -= 1
            else:
                self.ch1.turn_off()
        if self.ch2.reg_hi_ctl.value & 0x40:
            if self.ch2.ltimer != 0:
                self.ch2.ltimer -= 1
            else:
                self.ch2.turn_off()
        if self.ch3.reg_hi_ctl.value & 0x40:
            if self.ch3.ltimer != 0:
                self.ch3.ltimer -= 1
            else:
                self.ch3.turn_off()

    def accumulate_samples(self, cycles):
        if self.ch1.active:
            # channel 1 is active
            self.ch1.accumulate_for(cycles)
        # channel 1's DAC is off
        elif self.ch1.reg_vol_env.value & 0xF8 == 0:
            # accumulate analog silence
            self.ch1.accumulate_silence(cycles)

        if self.ch2.active:
            self.ch2.accumulate_for(cycles)
        elif self.ch2.reg_vol_env.value & 0xF8 == 0:
            self.ch2.accumulate_silence(cycles)

        if self.ch3.active:
            self.ch3.accumulate_for(cycles)
        elif self.ch3.reg_DAC_en.value >> 7 & 1 == 0:
            self.ch3.accumulate_silence(cycles)

        if self.ch4.active:
            self.ch4.accumulate_for(cycles)
        elif self.ch4.reg_vol_env.value & 0xF8 == 0:
            self.ch4.accumulate_silence(cycles)

    def triggers_edge(self, dots, period, elapsed):
        return dots // period != (dots + elapsed) // period

    def tick_cycles(self, cycles):
        elapsed = cycles
        old = self.dots
        while cycles > 0:
            dots_until_sample = self.accm - self.samples
            chunk = min(cycles, dots_until_sample)
            self.accumulate_samples(chunk)
            self.samples += chunk
            cycles -= chunk
            self.dots = (self.dots + chunk) % MASTER_CLK
            if self.samples == self.accm:
                buffer = self.ring // self.buffer_size
                self.emit_PCM_sample(buffer)
                self.samples = 0
        counter_trigger = self.triggers_edge(old, FRAME_SEQ >> 2, elapsed)
        sweep_trigger = self.triggers_edge(old, FRAME_SEQ >> 1, elapsed)
        envelope_trigger = self.triggers_edge(old, FRAME_SEQ, elapsed)
        if counter_trigger:
            self.handle_len_counters()
        if sweep_trigger:
            self.handle_sweep()
        if envelope_trigger:
            self.handle_envelope()
