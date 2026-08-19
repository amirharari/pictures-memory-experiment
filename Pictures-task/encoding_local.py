#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Encoding Task – Local PsychoPy Version
=======================================
Mirrors the web-based encoding task exactly:
  - Same participant lists / group / subset logic
  - Same timing: 4 s image, 3.5–6.5 s ISI, 20 % question probability
  - Same question: "האם יש בתמונה תחושה של תנועה?" (1=yes / 2=no)
  - Same two-block structure with background music on one block
  - Music rating (valence + arousal 1-5) after the music block
  - Saves CSV with identical fields to the web version

Requirements:  psychopy  (includes Pillow)
Run:           python encoding_local.py
               — or open in PsychoPy Builder and run via the IDE
"""

import os
import csv
import json
import random
import threading
import sys
from datetime import datetime

import numpy as np
from psychopy import visual, core, event, gui

# ── Audio backend (sounddevice+soundfile preferred, pyo fallback) ──────────────
_HAVE_SD = _HAVE_SF = _HAVE_PYO = False
try:
    import sounddevice as sd;   _HAVE_SD = True
except Exception: pass
try:
    import soundfile as sf;     _HAVE_SF = True
except Exception: pass
try:
    from pyo import Server, SfPlayer; _HAVE_PYO = True
except Exception: pass


class AudioPlayer:
    """Background looping audio player – sounddevice+soundfile or pyo fallback."""

    def __init__(self):
        self._stop    = threading.Event()
        self._thread  = None
        self._pyo_srv = None
        self._pyo_pl  = None
        if _HAVE_SD and _HAVE_SF:
            self.backend = 'sd'
        elif _HAVE_PYO:
            self.backend = 'pyo'
        else:
            self.backend = None
        print('Audio backend:', self.backend)

    def start(self, path):
        """Load file and begin looping playback in a daemon thread."""
        if self.backend is None:
            print('WARNING: no audio backend – music will be silent')
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(path,), daemon=True)
        self._thread.start()

    def _loop(self, path):
        if self.backend == 'sd':
            try:
                import time
                data, sr = sf.read(path, dtype='float32')
                if data.ndim == 1:                         # mono → stereo
                    data = np.column_stack([data, data])
                data = data * (10.0 ** (5.0 / 20.0))      # +5 dB gain
                duration = len(data) / sr
                print('Audio loaded: {:.1f}s, sr={}'.format(duration, sr))
                while not self._stop.is_set():
                    sd.play(data, sr)
                    t0 = time.time()
                    while time.time() - t0 < duration:
                        if self._stop.is_set():
                            sd.stop(); return
                        time.sleep(0.05)
                sd.stop()
            except Exception as e:
                print('Audio error:', e)

        elif self.backend == 'pyo':
            try:
                if self._pyo_srv is None:
                    self._pyo_srv = Server().boot()
                    self._pyo_srv.start()
                gain = 10.0 ** (5.0 / 20.0)
                self._pyo_pl = SfPlayer(path, loop=True, mul=gain).out()
                while not self._stop.is_set():
                    core.wait(0.1)
                self._pyo_pl.stop()
            except Exception as e:
                print('Pyo error:', e)

    def stop(self):
        self._stop.set()
        if self.backend == 'sd':
            try: sd.stop()
            except Exception: pass
        if self._thread:
            self._thread.join(timeout=2)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
STIMULI_DIR = os.path.join(BASE_DIR, 'stimuli')
AUDIO_DIR   = os.path.join(BASE_DIR, 'audio')
DATA_DIR    = os.path.join(BASE_DIR, 'data')
DESIGN_DIR  = os.path.join(BASE_DIR, 'designs')
os.makedirs(DATA_DIR,   exist_ok=True)
os.makedirs(DESIGN_DIR, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
IMAGE_EXTS    = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
IMG_DURATION  = 4.0    # seconds
ISI_MIN       = 3.5    # seconds
ISI_MAX       = 7.0    # seconds
QUESTION_PROB = 0.20   # probability per trial
TEST_N        = 5      # images per block in test-mode

PARTICIPANT_LISTS = {
    1: {'Baseline': 'Group_1', 'Psilocybin': 'Group_2',
        'music_subset': 'a', 'music_first': False},
    2: {'Baseline': 'Group_1', 'Psilocybin': 'Group_2',
        'music_subset': 'b', 'music_first': True},
    3: {'Baseline': 'Group_2', 'Psilocybin': 'Group_1',
        'music_subset': 'a', 'music_first': True},
    4: {'Baseline': 'Group_2', 'Psilocybin': 'Group_1',
        'music_subset': 'b', 'music_first': False},
}

CSV_FIELDS = [
    'participant_id', 'session', 'participant_list', 'dataset',
    'music_subset', 'no_music_subset', 'song', 'test_mode', 'music_first',
    'block', 'trial', 'subset', 'image_filename',
    'image_onset_ms', 'isi_dur_ms', 'question_shown', 'response', 'rt_ms',
]

# ── Setup dialog ──────────────────────────────────────────────────────────────
dlg = gui.Dlg(title='Encoding Task – Setup')
dlg.addField('Participant ID:',          '')
dlg.addField('Session:',                 choices=['Baseline', 'Psilocybin'])
dlg.addField('List (1–4):',              choices=['1', '2', '3', '4'])
dlg.addField('Song:',                    choices=['song_1.wav', 'song_2.wav', 'song_3.wav'])
dlg.addField('Test mode (5 images):',    False)
vals = dlg.show()
if not dlg.OK:
    core.quit()

pid       = str(vals[0]).strip()
sess      = vals[1]
list_num  = int(vals[2])
song      = vals[3]
test_mode = bool(vals[4])

if not pid:
    raise SystemExit('No participant ID entered.')

# ── List / counterbalancing logic ─────────────────────────────────────────────
li           = PARTICIPANT_LISTS[list_num]
dataset      = li[sess]
music_sub    = li['music_subset']
no_music_sub = 'b' if music_sub == 'a' else 'a'
music_first  = li['music_first']

def all_images(dset, sub):
    folder = os.path.join(STIMULI_DIR, dset, sub)
    return sorted(f for f in os.listdir(folder)
                  if os.path.splitext(f)[1].lower() in IMAGE_EXTS)

def make_design(dset, msub, nmsub, n_test=None):
    """Generate and return a design dict with fixed image order + ISI per trial."""
    m_imgs  = all_images(dset, msub);  random.shuffle(m_imgs)
    nm_imgs = all_images(dset, nmsub); random.shuffle(nm_imgs)
    if n_test:
        m_imgs  = m_imgs[:n_test]
        nm_imgs = nm_imgs[:n_test]

    def trials(imgs, sub):
        return [{'filename': f, 'subset': sub,
                 'isi': round(random.uniform(ISI_MIN, ISI_MAX), 3),
                 'show_question': random.random() < QUESTION_PROB}
                for f in imgs]

    return {
        'music_trials':    trials(m_imgs,  msub),
        'no_music_trials': trials(nm_imgs, nmsub),
    }

# ── Load or create fixed design for this list ─────────────────────────────────
design_key  = 'design_L{}_{}{}.json'.format(list_num, dataset,
                                             '_TEST' if test_mode else '')
design_path = os.path.join(DESIGN_DIR, design_key)

if os.path.exists(design_path):
    with open(design_path, encoding='utf-8') as f:
        design = json.load(f)
    print('Loaded existing design:', design_key)
else:
    design = make_design(dataset, music_sub, no_music_sub,
                         n_test=TEST_N if test_mode else None)
    with open(design_path, 'w', encoding='utf-8') as f:
        json.dump(design, f, indent=2, ensure_ascii=False)
    print('Created new design:', design_key)

music_trials    = design['music_trials']
no_music_trials = design['no_music_trials']

if music_first:
    b1_trials, b1_sub, b1_music = music_trials,    music_sub,    True
    b2_trials, b2_sub, b2_music = no_music_trials, no_music_sub, False
else:
    b1_trials, b1_sub, b1_music = no_music_trials, no_music_sub, False
    b2_trials, b2_sub, b2_music = music_trials,    music_sub,    True

# ── CSV output ────────────────────────────────────────────────────────────────
ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
sfx      = '_TEST' if test_mode else ''
csv_path = os.path.join(DATA_DIR,
    'encoding_local_{}_{}{}_L{}_{}.csv'.format(pid, sess, sfx, list_num, ts))

with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()

BASE_ROW = dict(
    participant_id   = pid,
    session          = sess,
    participant_list = list_num,
    dataset          = dataset,
    music_subset     = music_sub,
    no_music_subset  = no_music_sub,
    song             = song,
    test_mode        = int(test_mode),
    music_first      = int(music_first),
)

def save_row(extra):
    row = {**BASE_ROW, **extra}
    with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(
            {k: row.get(k, '') for k in CSV_FIELDS})

# ── PsychoPy window & stimuli ─────────────────────────────────────────────────
win = visual.Window(
    fullscr  = True,
    color    = 'black',
    units    = 'height',
    allowGUI = False,
    winType  = 'pyglet',
)
ASPECT = win.size[0] / win.size[1]  # e.g. 1.778 for 16:9

FONT     = 'Arial'
fixation = visual.TextStim(win, text='+', color='white', height=0.08, font=FONT)
txt_stim = visual.TextStim(win, text='', color='white', height=0.034,
                            wrapWidth=1.4, font=FONT,
                            alignText='center', anchorHoriz='center', anchorVert='center',
                            languageStyle='RTL')
progress = visual.TextStim(win, text='', color='#777777', height=0.025, font=FONT,
                            pos=(0, 0.47), anchorHoriz='center')
img_stim = visual.ImageStim(win, units='height')

def fit_and_load(path):
    """Load image into img_stim and scale it to fit within the screen."""
    from PIL import Image as PILImage
    im  = PILImage.open(path)
    iw, ih = im.size
    ar  = iw / ih
    max_h = 0.84
    max_w = max_h * ASPECT
    if ar >= max_w / max_h:        # wider than allowed → constrain width
        w = max_w; h = max_w / ar
    else:                          # taller → constrain height
        h = max_h; w = max_h * ar
    img_stim.setImage(path)
    img_stim.size = (w, h)

# ── Navigation helpers ────────────────────────────────────────────────────────
def wait_key(keys=None):
    """Wait for one of `keys` (or escape to quit). Return the key pressed."""
    if keys is None:
        keys = ['space', 'return']
    event.clearEvents()
    pressed = event.waitKeys(keyList=keys + ['escape'])
    if pressed and 'escape' in pressed:
        win.close(); core.quit()
    return pressed[0] if pressed else None

def show_page(text, keys=None):
    """Render `text` full-screen and wait for a keypress. Returns key."""
    txt_stim.text = text
    txt_stim.draw()
    win.flip()
    return wait_key(keys)

# ── Wait for scanner trigger (key '5') ───────────────────────────────────────
txt_stim.text = 'ממתין למגנט...'
txt_stim.draw()
win.flip()

event.clearEvents()
keys = event.waitKeys(keyList=['5', 'escape'])
if 'escape' in keys:
    win.close(); core.quit()

# Brief fixation before first trial
fixation.draw()
win.flip()
core.wait(0.5)

# ── Block runner ──────────────────────────────────────────────────────────────
def run_block(block_num, trials, subset, is_music):
    player = AudioPlayer() if is_music else None

    # No start screen in MRI version — go straight in
    fixation.draw()
    win.flip()
    core.wait(0.5)

    # start music only when task begins (mirrors web: music starts on first trial)
    if player:
        player.start(os.path.join(AUDIO_DIR, song))

    global_clock = core.Clock()

    for ti, trial in enumerate(trials):
        fname   = trial['filename']
        isi_dur = trial['isi']
        show_q  = trial['show_question']
        event.clearEvents()

        img_path = os.path.join(STIMULI_DIR, dataset, subset, fname)
        try:
            fit_and_load(img_path)
        except Exception:
            img_stim.setImage(img_path)
            img_stim.size = (1.2, 0.80)

        # ── Show image for IMG_DURATION ──────────────────────────────────────
        img_stim.draw()
        t_onset = global_clock.getTime()
        win.flip()
        core.wait(IMG_DURATION)

        # ── ISI ───────────────────────────────────────────────────────────────
        response = ''
        rt_ms    = ''

        if show_q:
            # Show question for the full ISI (response can come any time)
            txt_stim.text = ('האם יש בתמונה תחושה של תנועה?\n\n'
                             '   4 = כן                    1 = לא')
            txt_stim.draw()
            q_clock = core.Clock()
            win.flip()

            keys = event.waitKeys(
                maxWait     = isi_dur,
                keyList     = ['1', '4', 'escape'],
                timeStamped = q_clock,
            )
            if keys:
                k, rt = keys[0]
                if k == 'escape':
                    if player: player.stop()
                    win.close(); core.quit()
                response = 'yes' if k == '4' else 'no'
                # RT is measured from image onset to match web version
                rt_ms = int((t_onset + IMG_DURATION + rt) * 1000)
                leftover = max(0.0, isi_dur - rt)
            else:
                response = 'no_response'
                leftover = 0.0

            # Fill remaining ISI with fixation
            if leftover > 0.05:
                fixation.draw()
                win.flip()
                core.wait(leftover)
        else:
            fixation.draw()
            win.flip()
            core.wait(isi_dur)

        # escape check even without question
        if event.getKeys(['escape']):
            if player: player.stop()
            win.close(); core.quit()

        # ── Save trial ────────────────────────────────────────────────────────
        save_row({
            'block':          block_num,
            'trial':          ti + 1,
            'subset':         subset,
            'image_filename': fname,
            'image_onset_ms': int(t_onset * 1000),
            'isi_dur_ms':     int(isi_dur * 1000),
            'question_shown': int(show_q),
            'response':       response,
            'rt_ms':          rt_ms,
        })

    if player:
        player.stop()

# ── Music rating (valence + arousal 1–5) ──────────────────────────────────────
def do_music_rating():
    valence = show_page(
        'דירוג המוזיקה\n\n'
        'עד כמה המוזיקה הרגישה שלילית או חיובית?\n\n'
        '   1 = שלילית מאוד\n'
        '   2 = שלילית\n'
        '   3 = נייטרלית\n'
        '   4 = חיובית\n'
        '   5 = חיובית מאוד',
        keys=['1', '2', '3', '4', '5'],
    )
    arousal = show_page(
        'דירוג המוזיקה\n\n'
        'עד כמה המוזיקה הייתה מרגיעה או מעוררת?\n\n'
        '   1 = מרגיעה מאוד\n'
        '   2 = מרגיעה\n'
        '   3 = נייטרלית\n'
        '   4 = מעוררת\n'
        '   5 = מעוררת מאוד',
        keys=['1', '2', '3', '4', '5'],
    )
    save_row({
        'block':    'music_rating',
        'response': 'valence:{} arousal:{}'.format(valence, arousal),
    })

# ── Main sequence ─────────────────────────────────────────────────────────────
run_block(1, b1_trials, b1_sub, b1_music)
if b1_music:
    do_music_rating()

# Brief fixation between blocks
fixation.draw()
win.flip()
core.wait(2.0)

run_block(2, b2_trials, b2_sub, b2_music)
if b2_music:
    do_music_rating()

show_page('תודה רבה!\n\nסיימת את המטלה.\n\n[ SPACE לסיום ]')

win.close()
core.quit()
