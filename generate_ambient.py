"""生成一段 60 秒可循环的冥想环境音"""
import wave
import struct
import math
import os

SAMPLE_RATE = 44100
DURATION = 60
NUM_SAMPLES = SAMPLE_RATE * DURATION

def sine(freq, t, amp=1.0):
    return amp * math.sin(2 * math.pi * freq * t)

def generate():
    samples = []
    for i in range(NUM_SAMPLES):
        t = i / SAMPLE_RATE

        # 基础音：低沉的 C3 (130 Hz) 和弦垫
        pad1 = sine(130.81, t, 0.08)
        pad2 = sine(196.00, t, 0.05)   # G3
        pad3 = sine(261.63, t, 0.04)   # C4

        # 缓慢颤动的高音泛音
        shimmer1 = sine(523.25, t, 0.02 * (0.5 + 0.5 * math.sin(t * 0.3)))
        shimmer2 = sine(659.25, t, 0.015 * (0.5 + 0.5 * math.sin(t * 0.2 + 1.0)))

        # 非常缓慢的音量呼吸感
        breath = 0.7 + 0.3 * math.sin(t * 2 * math.pi / 16)

        # 轻微的去谐，产生自然的"活"感
        detune = sine(131.5, t, 0.04) + sine(195.2, t, 0.03)

        sample = (pad1 + pad2 + pad3 + shimmer1 + shimmer2 + detune) * breath

        # 淡入淡出（前后 3 秒）
        fade_samples = SAMPLE_RATE * 3
        if i < fade_samples:
            sample *= i / fade_samples
        elif i > NUM_SAMPLES - fade_samples:
            sample *= (NUM_SAMPLES - i) / fade_samples

        sample = max(-1.0, min(1.0, sample))
        samples.append(int(sample * 32767))

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ambient.wav')
    with wave.open(out_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for s in samples:
            wf.writeframes(struct.pack('<h', s))

    print(f'saved: {out_path} ({DURATION}s)')

generate()
