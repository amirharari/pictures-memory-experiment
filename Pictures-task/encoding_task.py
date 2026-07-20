#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Encoding Task – PsychoPy
=========================
Setup: enter Session (Baseline / Psilocybin) and Participant List (1–4).

The script derives the picture group, music/no-music subset, song, and
distractor subsets automatically from the participant list:

  List | Baseline | Psilocybin | Music sub | Baseline song | T1 dist | T2 dist
  -----+----------+------------+-----------+---------------+---------+--------
   1   | Group_1  | Group_2    | a         | Song 1        | c       | d
   2   | Group_1  | Group_2    | b         | Song 2        | d       | c
   3   | Group_2  | Group_1    | a         | Song 2        | d       | c
   4   | Group_2  | Group_1    | b         | Song 1        | c       | d

Block 1 (no music) : no-music encoding subset  (30 images)
Block 2 (with music): music encoding subset    (30 images)

Subsets c and d are distractors — NOT shown at encoding.

At the end of each session a JSON file is saved that records the T1/T2
image splits so the memory test can build the correct trial lists.

Test mode shows only 5 images per block for quick checks.
"""

import os
import glob
import json
import random
import csv
from datetime import datetime

from psychopy import visual, core, event, gui, sound, logging
from bidi.algorithm import get_display as bidi

# ── Paths ──────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
STIMULI_DIR = os.path.join(BASE_DIR, 'stimuli')
AUDIO_DIR   = os.path.join(BASE_DIR, 'audio')
DATA_DIR    = os.path.join(BASE_DIR, 'data')

# ── Timing & experiment constants ──────────────────
IMAGE_DURATION   = 2.0   # seconds each image is shown
WASHOUT_MIN      = 3.5   # minimum ISI duration (seconds)
WASHOUT_MAX      = 6.5   # maximum ISI duration (seconds)
QUESTION_PROB    = 0.20  # probability of incidental judgment question per trial
TEST_N_IMAGES    = 5     # images per block in test mode

BEGINNER_KEY     = '1'
PROFESSIONAL_KEY = '2'
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
GLOB_EXTENSIONS  = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tif', '*.tiff')

# ── Counterbalancing (5 factors) ───────────────────
# 1. G1/G2   – which picture group per session
# 2. a/b     – which encoding subset is music vs no-music
# 3. c/d     – which distractor subset goes to Test 1 vs Test 2
# 4. music_first – block order (True = music block first)
PARTICIPANT_LISTS = {
    1: {'Baseline': 'Group_1', 'Psilocybin': 'Group_2', 'music_subset': 'a', 't1_distractors': 'c', 't2_distractors': 'd', 'music_first': False},
    2: {'Baseline': 'Group_1', 'Psilocybin': 'Group_2', 'music_subset': 'b', 't1_distractors': 'd', 't2_distractors': 'c', 'music_first': True},
    3: {'Baseline': 'Group_2', 'Psilocybin': 'Group_1', 'music_subset': 'a', 't1_distractors': 'd', 't2_distractors': 'c', 'music_first': True},
    4: {'Baseline': 'Group_2', 'Psilocybin': 'Group_1', 'music_subset': 'b', 't1_distractors': 'c', 't2_distractors': 'd', 'music_first': False},
}

# Pool of songs for participant self-selection
ALL_SONGS = ['song_1.wav', 'song_2.wav', 'song_3.wav']   # WAV for PsychoPy compatibility


# ── Helpers ────────────────────────────────────────

def rtl(*lines):
    """Return bidi-correct Hebrew text, one line per argument."""
    return '\n'.join(bidi(ln) if ln else '' for ln in lines)


def load_images(dataset, subset):
    """Return a shuffled list of full image paths from one dataset/subset."""
    folder = os.path.join(STIMULI_DIR, dataset, subset)
    paths = []
    for ext in GLOB_EXTENSIONS:
        paths.extend(glob.glob(os.path.join(folder, ext)))
    if not paths:
        print(f'[WARNING] No images found in stimuli/{dataset}/{subset}')
    random.shuffle(paths)
    return paths


def list_images(dataset, subset):
    """Return sorted list of filenames (not full paths) for a subset."""
    folder = os.path.join(STIMULI_DIR, dataset, subset)
    return sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    )


# ── Rating screen ──────────────────────────────────

def _rate_1to5(question, low_label, high_label, msg_stim, win, global_clock):
    """Show a 1–5 Likert question; returns (rating: int, rt_s: float)."""
    # Split on newlines so bidi is applied per-line (not on one big chunk)
    q_lines = question.split('\n')
    text = rtl(
        *q_lines,
        '',
        '1 = ' + low_label,
        '5 = ' + high_label,
        '',
        'לחץ/י מספר בין 1 ל-5',
    )
    msg_stim.text = text
    msg_stim.draw()
    win.flip()
    t0   = global_clock.getTime()
    keys = event.waitKeys(keyList=['1', '2', '3', '4', '5', 'escape'])
    rt   = round(global_clock.getTime() - t0, 4)
    if 'escape' in keys:
        win.close()
        core.quit()
    return int(keys[0]), rt


# ── Music selection ────────────────────────────────

def _select_music(win, msg_stim, global_clock):
    """
    Interactive music selection: press 1/2/3 to preview, SPACE to confirm.
    Returns the filename of the chosen song.
    """
    songs       = ALL_SONGS
    n           = len(songs)
    chosen_idx  = None
    active_snd  = None

    def stop():
        nonlocal active_snd
        if active_snd is not None:
            try:
                active_snd.stop()
            except Exception:
                pass
            active_snd = None

    def play(idx):
        nonlocal active_snd
        stop()
        path = os.path.join(AUDIO_DIR, songs[idx])
        if os.path.exists(path):
            snd = sound.Sound(path, loops=-1)
            snd.play()
            active_snd = snd

    number_keys = [str(i + 1) for i in range(n)]

    while True:
        # Build instruction text
        header = ['בחר/י מוזיקה לחלק השני של הניסוי', '']
        options = []
        for i in range(n):
            marker = '  >>  ' if i == chosen_idx else '      '
            options.append('{}{} = קטע {}'.format(marker, i + 1, i + 1))
        footer = [
            '',
            'לחץ/י על מספר כדי להאזין.',
            'לחץ/י SPACE לאישור.' if chosen_idx is not None else 'בחר/י קטע לפני האישור.',
        ]
        msg_stim.text = rtl(*(header + options + footer))
        msg_stim.draw()
        win.flip()

        valid_keys = number_keys + ['space', 'escape']
        keys = event.waitKeys(keyList=valid_keys)

        if 'escape' in keys:
            stop()
            win.close()
            core.quit()

        if 'space' in keys:
            if chosen_idx is not None:
                stop()
                return songs[chosen_idx]
            # else ignore — must pick a song first
        else:
            for k in keys:
                if k in number_keys:
                    chosen_idx = int(k) - 1
                    play(chosen_idx)
                    break


# ── Main ───────────────────────────────────────────

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    logging.console.setLevel(logging.WARNING)

    # ── Setup dialog ──────────────────────────────
    exp_info = {
        'Participant ID':            '',
        'Session':                   ['Baseline', 'Psilocybin'],
        'Participant List (1-4)':    ['1', '2', '3', '4'],
        'Test mode (5 images only)': False,
    }
    dlg = gui.DlgFromDict(
        exp_info,
        title='Encoding Task – Setup',
        order=['Participant ID', 'Session',
               'Participant List (1-4)', 'Test mode (5 images only)'],
    )
    if not dlg.OK:
        core.quit()

    participant_id = exp_info['Participant ID']
    session        = exp_info['Session']
    list_num       = int(exp_info['Participant List (1-4)'])
    test_mode      = exp_info['Test mode (5 images only)']
    ts             = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ── Derive counterbalancing ────────────────────
    li               = PARTICIPANT_LISTS[list_num]
    dataset          = li[session]
    music_subset     = li['music_subset']
    no_music_subset  = 'b' if music_subset == 'a' else 'a'
    t1_distractors   = li['t1_distractors']
    t2_distractors   = li['t2_distractors']
    music_first      = li['music_first']
    song_filename    = None  # will be set after participant music selection

    music_images    = load_images(dataset, music_subset)
    no_music_images = load_images(dataset, no_music_subset)

    if test_mode:
        music_images    = music_images[:TEST_N_IMAGES]
        no_music_images = no_music_images[:TEST_N_IMAGES]

    # ── Window ────────────────────────────────────
    win = visual.Window(
        fullscr=True,
        size=[1920, 1080],
        color=[0.1, 0.1, 0.1],
        colorSpace='rgb',
        units='height',
        allowGUI=False,
        monitor='testMonitor',
    )
    win.mouseVisible = False

    # ── Stimuli ───────────────────────────────────
    img_stim = visual.ImageStim(win, size=0.80, interpolate=True)
    fixation = visual.TextStim(win, text='+', height=0.08, color='white', font='Arial')
    question_stim = visual.TextStim(
        win,
        text=rtl(
            'האם התמונה הזאת צוירה על ידי אומן מתחיל או מקצוען?',
            '',
            '1  =  מתחיל                    2  =  מקצוען',
        ),
        height=0.045, color='white', font='Arial',
        wrapWidth=1.4, alignText='center',
    )
    msg_stim = visual.TextStim(
        win, text='', height=0.045, color='white',
        font='Arial', wrapWidth=1.4, alignText='center',
    )

    global_clock = core.Clock()

    # ── Data file ─────────────────────────────────
    suffix    = '_TEST' if test_mode else ''
    data_file = os.path.join(
        DATA_DIR,
        f'encoding_{participant_id}_{session}_L{list_num}{suffix}_{ts}.csv',
    )
    csv_fields = [
        'participant_id', 'session', 'participant_list',
        'dataset', 'music_subset', 'no_music_subset',
        'song', 'test_mode',
        'block', 'trial', 'subset', 'image',
        'image_onset_s', 'washout_dur_s',
        'question_shown', 'response', 'rt_s',
    ]
    with open(data_file, 'w', newline='', encoding='utf-8-sig') as f:
        csv.DictWriter(f, fieldnames=csv_fields).writeheader()

    def save_trial(row):
        with open(data_file, 'a', newline='', encoding='utf-8-sig') as f:
            csv.DictWriter(f, fieldnames=csv_fields).writerow(row)

    def show_message(text):
        msg_stim.text = text
        msg_stim.draw()
        win.flip()
        keys = event.waitKeys(keyList=['space', 'escape'])
        if 'escape' in keys:
            win.close()
            core.quit()

    def run_block(images, block_num, music_path=None):
        music = None
        if music_path:
            if os.path.exists(music_path):
                music = sound.Sound(music_path, loops=-1)
                music.play()
            else:
                print(f'[WARNING] Music file not found: {music_path}')

        for trial_idx, img_path in enumerate(images):
            if event.getKeys(['escape']):
                if music:
                    music.stop()
                win.close()
                core.quit()

            # Show image
            img_stim.setImage(img_path)
            img_stim.draw()
            win.flip()
            image_onset = global_clock.getTime()
            core.wait(IMAGE_DURATION, hogCPUperiod=0.2)

            # Washout / ISI
            washout_dur   = random.uniform(WASHOUT_MIN, WASHOUT_MAX)
            show_question = random.random() < QUESTION_PROB
            response      = ''
            rt_s          = ''

            (question_stim if show_question else fixation).draw()
            win.flip()

            event.clearEvents()
            washout_onset = global_clock.getTime()
            timer         = core.CountdownTimer(washout_dur)
            resp_recorded = False

            while timer.getTime() > 0:
                if event.getKeys(['escape']):
                    if music:
                        music.stop()
                    win.close()
                    core.quit()

                if show_question and not resp_recorded:
                    keys = event.getKeys(
                        keyList=[BEGINNER_KEY, PROFESSIONAL_KEY],
                        timeStamped=global_clock,
                    )
                    if keys:
                        key_char, key_time = keys[0]
                        response      = 'beginner' if key_char == BEGINNER_KEY else 'professional'
                        rt_s          = round(key_time - washout_onset, 4)
                        resp_recorded = True
                        fixation.draw()
                        win.flip()

            if show_question and not resp_recorded:
                response = 'no_response'

            save_trial({
                'participant_id':   participant_id,
                'session':          session,
                'participant_list': list_num,
                'dataset':          dataset,
                'music_subset':     music_subset,
                'no_music_subset':  no_music_subset,
                'song':             song_filename,
                'test_mode':        int(test_mode),
                'block':            block_num,
                'trial':            trial_idx + 1,
                'subset':           os.path.basename(os.path.dirname(img_path)),
                'image':            os.path.basename(img_path),
                'image_onset_s':    round(image_onset, 4),
                'washout_dur_s':    round(washout_dur, 4),
                'question_shown':   int(show_question),
                'response':         response,
                'rt_s':             rt_s,
            })

        if music:
            music.stop()

    # ── Experiment flow ───────────────────────────
    show_message(rtl(
        'ברוך הבא לניסוי',
        '',
        'תראה/י סדרת תמונות.',
        'כל תמונה תוצג למשך 2 שניות.',
        '',
        'לאחר כל תמונה יופיע + על המסך,',
        'או שאלה קצרה. אם תופיע שאלה, לחץ/י:',
        '',
        '  1  =  מתחיל          2  =  מקצוען',
        '',
        'לחץ/י SPACE להתחלה',
    ))

    if music_first:
        # ── Music block first ──────────────────────
        song_filename = _select_music(win, msg_stim, global_clock)

        show_message(rtl(
            'החלק הראשון יתנהל עם המוזיקה שבחרת ברקע.',
            '',
            'לחץ/י SPACE להתחלה',
        ))
        song_path = os.path.join(AUDIO_DIR, song_filename)
        run_block(music_images, block_num=1, music_path=song_path)

        # ── Music ratings ──────────────────────────
        music_valence, music_valence_rt = _rate_1to5(
            'ולנס / אופי ההרגשה\n\n'
            'דרג/י את אופי ההרגשה שהקטע עורר בך:\n'
            'באיזו מידה ההרגשה הייתה חיובית (שמחה, נעימות)\n'
            'או שלילית (עצב, אי-נעימות)?',
            'שלילית מאוד', 'חיובית מאוד',
            msg_stim, win, global_clock,
        )
        music_arousal, music_arousal_rt = _rate_1to5(
            'עוררות רגשית\n\n'
            'דרג/י את רמת העוררות שהקטע עורר בך:\n'
            'באיזו מידה הרגשת מעורר/ת ודרוך/ה\n'
            'לעומת רגוע/ה ונינוח/ה?',
            'רגוע/ה מאוד', 'מעורר/ת מאוד',
            msg_stim, win, global_clock,
        )

        show_message(rtl(
            'כל הכבוד! סיימת את החלק הראשון.',
            '',
            'החלק השני יתנהל ללא מוזיקה.',
            'שאר ההוראות זהות.',
            '',
            'לחץ/י SPACE להמשך',
        ))
        run_block(no_music_images, block_num=2)

    else:
        # ── No-music block first ───────────────────
        run_block(no_music_images, block_num=1)

        song_filename = _select_music(win, msg_stim, global_clock)

        show_message(rtl(
            'כל הכבוד! סיימת את החלק הראשון.',
            '',
            'עכשיו יתחיל החלק השני – עם המוזיקה שבחרת ברקע.',
            'שאר ההוראות זהות.',
            '',
            'לחץ/י SPACE להמשך',
        ))
        song_path = os.path.join(AUDIO_DIR, song_filename)
        run_block(music_images, block_num=2, music_path=song_path)

        # ── Music ratings (right after music block) ─
        music_valence, music_valence_rt = _rate_1to5(
            'ולנס / אופי ההרגשה\n\n'
            'דרג/י את אופי ההרגשה שהקטע עורר בך:\n'
            'באיזו מידה ההרגשה הייתה חיובית (שמחה, נעימות)\n'
            'או שלילית (עצב, אי-נעימות)?',
            'שלילית מאוד', 'חיובית מאוד',
            msg_stim, win, global_clock,
        )
        music_arousal, music_arousal_rt = _rate_1to5(
            'עוררות רגשית\n\n'
            'דרג/י את רמת העוררות שהקטע עורר בך:\n'
            'באיזו מידה הרגשת מעורר/ת ודרוך/ה\n'
            'לעומת רגוע/ה ונינוח/ה?',
            'רגוע/ה מאוד', 'מעורר/ת מאוד',
            msg_stim, win, global_clock,
        )

    show_message(rtl(
        'הניסוי הסתיים!',
        '',
        'תודה רבה על השתתפותך.',
        '',
        'לחץ/י SPACE לסגירה',
    ))

    win.close()

    # ── Save session JSON for memory tests ────────
    # Randomly split each encoding subset 50/50 between Test 1 and Test 2
    music_imgs    = [os.path.basename(p) for p in music_images]
    no_music_imgs = [os.path.basename(p) for p in no_music_images]
    random.shuffle(music_imgs)
    random.shuffle(no_music_imgs)
    mid = len(music_imgs) // 2

    # Split T2 distractors 50/50 between the music and no-music blocks of Test 2
    t2_dist_all = list_images(dataset, t2_distractors)
    random.shuffle(t2_dist_all)
    dist_mid = len(t2_dist_all) // 2

    # Write music rating as a summary row in the CSV
    save_trial({
        'participant_id':   participant_id,
        'session':          session,
        'participant_list': list_num,
        'dataset':          dataset,
        'music_subset':     music_subset,
        'no_music_subset':  no_music_subset,
        'song':             song_filename,
        'test_mode':        int(test_mode),
        'block':            'music_rating',
        'trial':            '',
        'subset':           '',
        'image':            '',
        'image_onset_s':    '',
        'washout_dur_s':    '',
        'question_shown':   '',
        'response':         'valence:{} arousal:{}'.format(music_valence, music_arousal),
        'rt_s':             'valence_rt:{} arousal_rt:{}'.format(music_valence_rt, music_arousal_rt),
    })

    session_info = {
        'participant_id':         participant_id,
        'session':                session,
        'participant_list':       list_num,
        'dataset':                dataset,
        'music_subset':           music_subset,
        'no_music_subset':        no_music_subset,
        'music_first':            music_first,
        't1_distractor_subset':   t1_distractors,
        't2_distractor_subset':   t2_distractors,
        'session_song':           song_filename,
        'music_valence':          music_valence,
        'music_arousal':          music_arousal,
        'music_images_T1':        music_imgs[:mid],
        'music_images_T2':        music_imgs[mid:],
        'no_music_images_T1':     no_music_imgs[:mid],
        'no_music_images_T2':     no_music_imgs[mid:],
        'distractors_T2_music':   t2_dist_all[:dist_mid],
        'distractors_T2_no_music':t2_dist_all[dist_mid:],
    }

    json_path = os.path.join(
        DATA_DIR,
        f'session_{participant_id}_{session}_L{list_num}{suffix}_{ts}.json',
    )
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(session_info, f, indent=2, ensure_ascii=False)

    core.quit()


if __name__ == '__main__':
    main()
