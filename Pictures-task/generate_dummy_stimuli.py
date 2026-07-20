#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generate_dummy_stimuli.py
=========================
Creates placeholder images (PNG) and a background audio file (WAV)
for testing the encoding task and memory test.

Run once from the project root:
    python generate_dummy_stimuli.py
"""

import os
import math
import struct
import wave
import random
from PIL import Image, ImageDraw, ImageFont

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
STIMULI_DIR = os.path.join(BASE_DIR, 'stimuli')
AUDIO_DIR   = os.path.join(BASE_DIR, 'audio')

# 4 datasets × 4 subsets × 15 images = 240 images
DATASETS = ['X', 'Y', 'Z', 'W']
SUBSETS  = ['a', 'b', 'c', 'd']
N_IMAGES = 15   # images per subset

IMG_W, IMG_H = 512, 512

# Distinct background colours per dataset (RGB)
DATASET_COLOURS = {
    'X': [(200, 100, 100), (220,  80,  80), (180, 120, 100)],   # reds
    'Y': [(100, 160, 200), ( 80, 140, 220), (120, 180, 180)],   # blues
    'Z': [(100, 190, 110), ( 80, 170,  90), (120, 200, 130)],   # greens
    'W': [(200, 170,  80), (220, 150,  60), (180, 190, 100)],   # yellows
}

# Distinct accent colours per subset
SUBSET_ACCENT = {
    'a': (255, 255, 255),
    'b': (255, 220, 100),
    'c': (180, 255, 200),
    'd': (200, 200, 255),
}


def pick_bg(dataset, image_idx):
    colours = DATASET_COLOURS[dataset]
    base = colours[image_idx % len(colours)]
    # add slight random variation so every image looks a bit different
    r = min(255, max(0, base[0] + random.randint(-18, 18)))
    g = min(255, max(0, base[1] + random.randint(-18, 18)))
    b = min(255, max(0, base[2] + random.randint(-18, 18)))
    return (r, g, b)


def make_image(dataset, subset, idx):
    """Return a PIL Image: coloured background + text label + simple shapes."""
    random.seed(ord(dataset) * 1000 + ord(subset) * 100 + idx)  # reproducible

    bg_colour = pick_bg(dataset, idx)
    accent    = SUBSET_ACCENT[subset]

    img  = Image.new('RGB', (IMG_W, IMG_H), bg_colour)
    draw = ImageDraw.Draw(img)

    # --- decorative shapes ------------------------------------------------
    for _ in range(6):
        x0 = random.randint(20, IMG_W - 80)
        y0 = random.randint(20, IMG_H - 80)
        x1 = x0 + random.randint(40, 120)
        y1 = y0 + random.randint(40, 120)
        shape_col = (
            min(255, bg_colour[0] + random.randint(-40, 60)),
            min(255, bg_colour[1] + random.randint(-40, 60)),
            min(255, bg_colour[2] + random.randint(-40, 60)),
        )
        if random.random() > 0.5:
            draw.ellipse([x0, y0, x1, y1], fill=shape_col)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=shape_col)

    # --- border -----------------------------------------------------------
    border = 10
    draw.rectangle(
        [border, border, IMG_W - border, IMG_H - border],
        outline=accent, width=4,
    )

    # --- label text -------------------------------------------------------
    label     = f'DS {dataset}  /  subset {subset}  /  img {idx + 1:02d}'
    sub_label = f'PLACEHOLDER'

    # Use a basic font (fall back gracefully)
    try:
        font_big = ImageFont.truetype('arial.ttf', 32)
        font_sml = ImageFont.truetype('arial.ttf', 20)
    except IOError:
        font_big = ImageFont.load_default()
        font_sml = font_big

    # Centre text
    bbox = draw.textbbox((0, 0), label, font=font_big)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((IMG_W - tw) // 2, IMG_H // 2 - th - 12),
        label, fill=accent, font=font_big,
    )
    bbox2 = draw.textbbox((0, 0), sub_label, font=font_sml)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(
        ((IMG_W - tw2) // 2, IMG_H // 2 + 12),
        sub_label, fill=accent, font=font_sml,
    )

    return img


def make_audio(path, duration_s=10, sample_rate=44100):
    """Generate a simple multi-tone WAV file (not silent, clearly audible)."""
    n_samples  = int(sample_rate * duration_s)
    # Mix three sine waves for a pleasant chord
    freqs = [261.63, 329.63, 392.0]   # C4, E4, G4

    frames = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        value = sum(math.sin(2 * math.pi * f * t) for f in freqs)
        value /= len(freqs)           # normalise to [-1, 1]
        # Apply a slow fade-in and fade-out over 0.5 s
        fade = min(1.0, t / 0.5, (duration_s - t) / 0.5)
        sample = int(value * fade * 16000)
        frames += struct.pack('<h', sample)   # 16-bit signed little-endian

    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


# ══════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════
def main():
    total_images = len(DATASETS) * len(SUBSETS) * N_IMAGES
    print(f'\nGenerating {total_images} dummy images …')

    count = 0
    for ds in DATASETS:
        for subset in SUBSETS:
            folder = os.path.join(STIMULI_DIR, ds, subset)
            os.makedirs(folder, exist_ok=True)
            for idx in range(N_IMAGES):
                fname = f'{ds}_{subset}_{idx + 1:02d}.png'
                fpath = os.path.join(folder, fname)
                if not os.path.exists(fpath):
                    img = make_image(ds, subset, idx)
                    img.save(fpath, 'PNG')
                count += 1
                print(f'  [{count:>3}/{total_images}]  {fname}', end='\r')

    print(f'\n  OK  {total_images} images created in stimuli/')

    # Audio
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_path = os.path.join(AUDIO_DIR, 'background_music.wav')
    if not os.path.exists(audio_path):
        print('\nGenerating background_music.wav ...')
        make_audio(audio_path, duration_s=30)
        print('  OK  audio/background_music.wav created (30 s chord loop)')
    else:
        print('\n  --  audio/background_music.wav already exists, skipped.')

    print('\nDone! You can now run encoding_task.py or the memory test.\n')


if __name__ == '__main__':
    main()
