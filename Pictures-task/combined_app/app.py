#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Combined Web App – Encoding Task + Memory Test
===============================================
Single Flask server on port 5000.
  /encoding/  →  encoding task
  /memory/    →  memory test
  /           →  landing page

Sessions are stored server-side (filesystem) via Flask-Session,
so large image lists never hit the 4 KB cookie limit.
"""

import os
import random
import csv
from datetime import datetime
from functools import wraps

from urllib.parse import quote

from flask import (
    Flask, render_template, request,
    session, jsonify, redirect, url_for, send_from_directory,
)
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'combined_task_2026_secret'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '.flask_sessions')
app.config['SESSION_PERMANENT'] = False
Session(app)

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STIMULI_DIR = os.path.join(BASE_DIR, 'stimuli')
AUDIO_DIR   = os.path.join(BASE_DIR, 'audio')
DATA_DIR    = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
ALL_SONGS        = ['song_1.mp3', 'song_2.mp3', 'song_3.mp3']

PARTICIPANT_LISTS = {
    1: {'Baseline': 'Group_1', 'Psilocybin': 'Group_2',
        'music_subset': 'a', 't1_distractors': 'c', 't2_distractors': 'd', 'music_first': False},
    2: {'Baseline': 'Group_1', 'Psilocybin': 'Group_2',
        'music_subset': 'b', 't1_distractors': 'd', 't2_distractors': 'c', 'music_first': True},
    3: {'Baseline': 'Group_2', 'Psilocybin': 'Group_1',
        'music_subset': 'a', 't1_distractors': 'd', 't2_distractors': 'c', 'music_first': True},
    4: {'Baseline': 'Group_2', 'Psilocybin': 'Group_1',
        'music_subset': 'b', 't1_distractors': 'c', 't2_distractors': 'd', 'music_first': False},
}

ENC_IMAGE_DURATION_MS = 2000
ENC_ISI_MIN_MS        = 3500
ENC_ISI_MAX_MS        = 6500
ENC_QUESTION_PROB     = 0.20
ENC_TEST_N_IMAGES     = 5

MEM_TEST_N_PER_SOURCE = 5

ENC_CSV_FIELDS = [
    'participant_id', 'session', 'participant_list', 'dataset',
    'music_subset', 'no_music_subset', 'song', 'test_mode', 'music_first',
    'block', 'trial', 'subset', 'image_filename',
    'image_onset_ms', 'isi_dur_ms', 'question_shown', 'response', 'rt_ms',
]

MEM_CSV_FIELDS = [
    'participant_id', 'session', 'participant_list', 'dataset',
    'music_subset', 'session_song', 'test_mode',
    'block', 'trial',
    'image_filename', 'subset', 'encoding_condition',
    'ground_truth', 'music_context',
    'recognition_response', 'certainty',
    'image_valence', 'image_arousal',
    'rt_recognition_ms', 'rt_certainty_ms',
    'rt_valence_ms', 'rt_arousal_ms',
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def stimuli_url(dataset, subset, filename):
    return '/stimuli/{}/{}/{}'.format(dataset, subset, quote(filename))


def list_images(dataset, subset, shuffle=True):
    folder = os.path.join(STIMULI_DIR, dataset, subset)
    if not os.path.isdir(folder):
        return []
    files = sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    )
    if shuffle:
        random.shuffle(files)
    return files


def open_csv(path, mode):
    return open(path, mode, newline='', encoding='utf-8-sig')


def write_csv_header(path, fields):
    with open_csv(path, 'w') as f:
        csv.DictWriter(f, fieldnames=fields).writeheader()


def append_csv_row(path, fields, row):
    with open_csv(path, 'a') as f:
        csv.DictWriter(f, fieldnames=fields).writerow(row)


def require_enc(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'enc_participant_id' not in session:
            return redirect(url_for('enc_index'))
        return fn(*args, **kwargs)
    return wrapper


def require_mem(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'mem_participant_id' not in session:
            return redirect(url_for('mem_index'))
        return fn(*args, **kwargs)
    return wrapper


def require_mem_trials(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'mem_images' not in session:
            return redirect(url_for('mem_index'))
        return fn(*args, **kwargs)
    return wrapper


# ── Landing page ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── Shared file routes ────────────────────────────────────────────────────────

@app.route('/stimuli/<path:filepath>')
def serve_stimuli(filepath):
    return send_from_directory(STIMULI_DIR, filepath)


@app.route('/audio/<filename>')
def serve_audio(filename):
    ext  = os.path.splitext(filename)[1].lower()
    mime = 'audio/mpeg' if ext == '.mp3' else 'audio/wav'
    return send_from_directory(AUDIO_DIR, filename, mimetype=mime)


# ══════════════════════════════════════════════════════════════════════════════
# ENCODING TASK  (/encoding/*)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/encoding/')
def enc_index():
    return render_template('encoding/setup.html')


@app.route('/encoding/start', methods=['POST'])
def enc_start():
    f         = request.form
    pid       = f['participant_id'].strip()
    sess      = f['session']
    list_num  = int(f['participant_list'])
    test_mode = f.get('test_mode') == 'on'
    song      = f.get('chosen_song', 'song_1.mp3')

    li           = PARTICIPANT_LISTS[list_num]
    dataset      = li[sess]
    music_sub    = li['music_subset']
    no_music_sub = 'b' if music_sub == 'a' else 'a'
    music_first  = li['music_first']

    music_imgs    = list_images(dataset, music_sub)
    no_music_imgs = list_images(dataset, no_music_sub)

    if test_mode:
        music_imgs    = music_imgs[:ENC_TEST_N_IMAGES]
        no_music_imgs = no_music_imgs[:ENC_TEST_N_IMAGES]

    if music_first:
        b1_imgs, b1_sub = music_imgs,    music_sub
        b2_imgs, b2_sub = no_music_imgs, no_music_sub
    else:
        b1_imgs, b1_sub = no_music_imgs, no_music_sub
        b2_imgs, b2_sub = music_imgs,    music_sub

    ts        = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix    = '_TEST' if test_mode else ''
    data_file = 'encoding_web_{}_{}_{}_L{}_{}.csv'.format(pid, sess, suffix, list_num, ts)
    write_csv_header(os.path.join(DATA_DIR, data_file), ENC_CSV_FIELDS)

    session['enc_participant_id']   = pid
    session['enc_sess']             = sess
    session['enc_participant_list'] = list_num
    session['enc_dataset']          = dataset
    session['enc_music_subset']     = music_sub
    session['enc_no_music_subset']  = no_music_sub
    session['enc_music_first']      = music_first
    session['enc_test_mode']        = test_mode
    session['enc_song']             = song
    session['enc_data_file']        = data_file
    session['enc_block']            = 1
    session['enc_current_trial']    = 0
    session['enc_block1'] = [{'filename': fn, 'subset': b1_sub, 'dataset': dataset} for fn in b1_imgs]
    session['enc_block2'] = [{'filename': fn, 'subset': b2_sub, 'dataset': dataset} for fn in b2_imgs]
    return redirect(url_for('enc_instructions'))


@app.route('/encoding/instructions')
@require_enc
def enc_instructions():
    return render_template('encoding/instructions.html',
                           music_first=session['enc_music_first'])


@app.route('/encoding/begin_block')
@require_enc
def enc_begin_block():
    session['enc_current_trial'] = 0
    return redirect(url_for('enc_task'))


@app.route('/encoding/task')
@require_enc
def enc_task():
    blk      = session['enc_block']
    imgs     = session['enc_block{}'.format(blk)]
    is_music = (blk == 1 and session['enc_music_first']) or \
               (blk == 2 and not session['enc_music_first'])
    song_url = '/audio/' + session['enc_song'] if is_music and session['enc_song'] else ''
    return render_template(
        'encoding/task.html',
        total=len(imgs),
        song_url=song_url,
        image_duration_ms=ENC_IMAGE_DURATION_MS,
    )


@app.route('/encoding/api/next_trial')
@require_enc
def enc_next_trial():
    blk  = session['enc_block']
    idx  = session['enc_current_trial']
    imgs = session['enc_block{}'.format(blk)]

    if idx >= len(imgs):
        return jsonify({'done': True})

    isi_ms = random.randint(ENC_ISI_MIN_MS, ENC_ISI_MAX_MS)
    show_q = random.random() < ENC_QUESTION_PROB
    return jsonify({
        'done':          False,
        'trial_idx':     idx,
        'trial':         idx + 1,
        'total':         len(imgs),
        'image_url':     stimuli_url(imgs[idx]['dataset'], imgs[idx]['subset'], imgs[idx]['filename']),
        'isi_ms':        isi_ms,
        'show_question': show_q,
    })


@app.route('/encoding/api/save_trial', methods=['POST'])
@require_enc
def enc_save_trial():
    data = request.get_json()
    blk  = session['enc_block']
    idx  = data['trial_idx']
    imgs = session['enc_block{}'.format(blk)]

    if idx < len(imgs):
        img = imgs[idx]
        append_csv_row(
            os.path.join(DATA_DIR, session['enc_data_file']),
            ENC_CSV_FIELDS,
            {
                'participant_id':   session['enc_participant_id'],
                'session':          session['enc_sess'],
                'participant_list': session['enc_participant_list'],
                'dataset':          session['enc_dataset'],
                'music_subset':     session['enc_music_subset'],
                'no_music_subset':  session['enc_no_music_subset'],
                'song':             session['enc_song'],
                'test_mode':        int(session['enc_test_mode']),
                'music_first':      int(session['enc_music_first']),
                'block':            blk,
                'trial':            idx + 1,
                'subset':           img['subset'],
                'image_filename':   img['filename'],
                'image_onset_ms':   data.get('image_onset_ms', ''),
                'isi_dur_ms':       data.get('isi_dur_ms', ''),
                'question_shown':   int(data.get('question_shown', False)),
                'response':         data.get('response', ''),
                'rt_ms':            data.get('rt_ms', ''),
            },
        )

    next_idx = idx + 1
    session['enc_current_trial'] = next_idx
    return jsonify({'done': next_idx >= len(imgs)})


@app.route('/encoding/block_done', methods=['POST'])
@require_enc
def enc_block_done():
    blk = session['enc_block']
    mf  = session['enc_music_first']

    if blk == 1:
        if mf:
            return jsonify({'next': 'music_rating'})
        else:
            session['enc_block'] = 2
            return jsonify({'next': 'begin_block'})
    else:
        if not mf:
            return jsonify({'next': 'music_rating'})
        else:
            return jsonify({'next': 'done'})


@app.route('/encoding/music_rating')
@require_enc
def enc_music_rating():
    return render_template('encoding/music_rating.html')


@app.route('/encoding/save_music_rating', methods=['POST'])
@require_enc
def enc_save_music_rating():
    valence = request.form.get('valence', '')
    arousal = request.form.get('arousal', '')

    append_csv_row(
        os.path.join(DATA_DIR, session['enc_data_file']),
        ENC_CSV_FIELDS,
        {
            'participant_id':   session['enc_participant_id'],
            'session':          session['enc_sess'],
            'participant_list': session['enc_participant_list'],
            'dataset':          session['enc_dataset'],
            'music_subset':     session['enc_music_subset'],
            'no_music_subset':  session['enc_no_music_subset'],
            'song':             session['enc_song'],
            'test_mode':        int(session['enc_test_mode']),
            'music_first':      int(session['enc_music_first']),
            'block':            'music_rating',
            'trial':            '', 'subset': '', 'image_filename': '',
            'image_onset_ms':   '', 'isi_dur_ms': '', 'question_shown': '',
            'response':         'valence:{} arousal:{}'.format(valence, arousal),
            'rt_ms':            '',
        },
    )

    if session['enc_block'] == 1 and session['enc_music_first']:
        session['enc_block']         = 2
        session['enc_current_trial'] = 0
        return redirect(url_for('enc_task'))
    return redirect(url_for('enc_done'))


@app.route('/encoding/done')
@require_enc
def enc_done():
    return render_template('encoding/done.html',
                           participant_id=session.get('enc_participant_id', ''),
                           sess=session.get('enc_sess', ''))


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY TEST  (/memory/*)
# ══════════════════════════════════════════════════════════════════════════════

def _mem_build_trials(li, dataset, test_mode):
    """
    Single retrieval test, 120 trials across 2 blocks:
      Block 1 (music ON):  15 music-encoded + 15 no-music-encoded + 30 distractors
      Block 2 (music OFF): 15 music-encoded + 15 no-music-encoded + 30 distractors
    """
    music_sub    = li['music_subset']
    no_music_sub = 'b' if music_sub == 'a' else 'a'
    dist1_sub    = li['t1_distractors']   # 30 distractors for music block
    dist2_sub    = li['t2_distractors']   # 30 distractors for no-music block

    # Shuffle encoding images; split 50/50 across the two blocks
    music_files    = list_images(dataset, music_sub)
    no_music_files = list_images(dataset, no_music_sub)
    mid_m  = len(music_files) // 2
    mid_nm = len(no_music_files) // 2

    def trial(filename, subset, seen, music, block, enc_cond):
        return {
            'filename':           filename,
            'subset':             subset,
            'dataset':            dataset,
            'url':                stimuli_url(dataset, subset, filename),
            'seen':               seen,
            'music':              music,
            'block':              block,
            'encoding_condition': enc_cond,
        }

    # Block 1 – music ON
    block1 = []
    for f in music_files[:mid_m]:
        block1.append(trial(f, music_sub,    True,  True, 1, 'music'))
    for f in no_music_files[:mid_nm]:
        block1.append(trial(f, no_music_sub, True,  True, 1, 'no_music'))
    for f in list_images(dataset, dist1_sub):
        block1.append(trial(f, dist1_sub,    False, True, 1, 'new'))

    # Block 2 – music OFF
    block2 = []
    for f in music_files[mid_m:]:
        block2.append(trial(f, music_sub,    True,  False, 2, 'music'))
    for f in no_music_files[mid_nm:]:
        block2.append(trial(f, no_music_sub, True,  False, 2, 'no_music'))
    for f in list_images(dataset, dist2_sub):
        block2.append(trial(f, dist2_sub,    False, False, 2, 'new'))

    if test_mode:
        for blk in [block1, block2]:
            seen = [t for t in blk if t['seen']]
            new  = [t for t in blk if not t['seen']]
            random.shuffle(seen); random.shuffle(new)
            blk[:] = seen[:MEM_TEST_N_PER_SOURCE] + new[:MEM_TEST_N_PER_SOURCE]

    random.shuffle(block1)
    random.shuffle(block2)
    return block1 + block2


@app.route('/memory/')
def mem_index():
    return render_template('memory/setup.html')


@app.route('/memory/start', methods=['POST'])
def mem_start():
    f              = request.form
    participant_id = f['participant_id'].strip()
    sess           = f['session']
    list_num       = int(f['participant_list'])
    test_mode      = f.get('test_mode') == 'on'
    song           = f.get('chosen_song', 'song_1.mp3')

    li      = PARTICIPANT_LISTS[list_num]
    dataset = li[sess]

    ts        = datetime.now().strftime('%Y%m%d_%H%M%S')
    data_file = 'memory_{}_{}_L{}_{}.csv'.format(participant_id, sess, list_num, ts)

    trials = _mem_build_trials(li, dataset, test_mode)
    write_csv_header(os.path.join(DATA_DIR, data_file), MEM_CSV_FIELDS)

    session['mem_participant_id']   = participant_id
    session['mem_sess']             = sess
    session['mem_participant_list'] = list_num
    session['mem_dataset']          = dataset
    session['mem_music_subset']     = li['music_subset']
    session['mem_session_song']     = song
    session['mem_test_mode']        = test_mode
    session['mem_data_file']        = data_file
    session['mem_images']           = trials
    session['mem_current_trial']    = 0
    return redirect(url_for('mem_instructions'))


@app.route('/memory/instructions')
@require_mem_trials
def mem_instructions():
    return render_template('memory/instructions.html')


@app.route('/memory/task')
@require_mem_trials
def mem_task():
    song_url = '/audio/' + session['mem_session_song'] if session['mem_session_song'] else ''
    return render_template(
        'memory/task.html',
        total=len(session['mem_images']),
        song_url=song_url,
    )


@app.route('/memory/api/next_image')
@require_mem_trials
def mem_next_image():
    idx    = session['mem_current_trial']
    images = session['mem_images']
    if idx >= len(images):
        return jsonify({'done': True})

    img      = images[idx]
    prev_blk = images[idx - 1]['block'] if idx > 0 else img['block']
    return jsonify({
        'done':          False,
        'trial_idx':     idx,
        'trial':         idx + 1,
        'total':         len(images),
        'image_url':     img['url'],
        'music':         img['music'],
        'block':         img['block'],
        'block_changed': img['block'] != prev_blk,
    })


@app.route('/memory/api/save_response', methods=['POST'])
@require_mem_trials
def mem_save_response():
    data   = request.get_json()
    idx    = data['trial_idx']
    images = session['mem_images']
    if idx < len(images):
        img = images[idx]
        append_csv_row(
            os.path.join(DATA_DIR, session['mem_data_file']),
            MEM_CSV_FIELDS,
            {
                'participant_id':       session['mem_participant_id'],
                'session':              session['mem_sess'],
                'participant_list':     session['mem_participant_list'],
                'dataset':              session['mem_dataset'],
            'music_subset':         session['mem_music_subset'],
            'session_song':         session['mem_session_song'],
            'test_mode':            int(session['mem_test_mode']),
            'block':                img['block'],
                'trial':                idx + 1,
                'image_filename':       img['filename'],
                'subset':               img['subset'],
                'encoding_condition':   img['encoding_condition'],
                'ground_truth':         'seen' if img['seen'] else 'new',
                'music_context':        img['music'],
                'recognition_response': data.get('recognition', ''),
                'certainty':            data.get('certainty', ''),
                'image_valence':        data.get('image_valence', ''),
                'image_arousal':        data.get('image_arousal', ''),
                'rt_recognition_ms':    data.get('rt_recognition_ms', ''),
                'rt_certainty_ms':      data.get('rt_certainty_ms', ''),
                'rt_valence_ms':        data.get('rt_valence_ms', ''),
                'rt_arousal_ms':        data.get('rt_arousal_ms', ''),
            },
        )

    next_idx = idx + 1
    session['mem_current_trial'] = next_idx
    return jsonify({'done': next_idx >= len(images)})


@app.route('/memory/done')
def mem_done():
    return render_template(
        'memory/done.html',
        participant_id=session.get('mem_participant_id', ''),
        total=len(session.get('mem_images', [])),
    )


if __name__ == '__main__':
    print('\n  Encoding + Memory running at  http://localhost:5000\n')
    print('  Encoding task: http://localhost:5000/encoding/')
    print('  Memory test:   http://localhost:5000/memory/\n')
    app.run(debug=False, host='0.0.0.0', port=5000)
