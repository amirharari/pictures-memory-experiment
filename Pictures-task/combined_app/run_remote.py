#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Combined App Remote Launcher  (ngrok Tunnel)
============================================
Starts encoding + memory test on port 5000, then opens one ngrok tunnel.

Usage:  python run_remote.py   (or double-click START_REMOTE.bat)

One URL covers both tasks:
  <URL>/         landing page
  <URL>/encoding/  encoding task
  <URL>/memory/    memory test
"""

import os
import sys
import time
import json
import subprocess
import threading

PYTHON_EXE  = r'C:\Users\amirhar.RESLAB\AppData\Local\Programs\Python\Python311\python.exe'
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PORT        = 5000
NGROK_EXE   = r'C:\Pictures-task\ngrok.exe'

_public_url = None


def _url_reader(proc):
    global _public_url
    for line in iter(proc.stderr.readline, b''):
        text = line.decode('utf-8', errors='replace').strip()
        try:
            obj = json.loads(text)
            if obj.get('msg') == 'started tunnel' and 'url' in obj:
                if _public_url is None:
                    _public_url = obj['url']
        except (ValueError, KeyError):
            pass


def start_flask():
    return subprocess.Popen(
        [PYTHON_EXE, os.path.join(BASE_DIR, 'app.py')],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=BASE_DIR,
    )


def start_ngrok():
    global _public_url
    _public_url = None
    proc = subprocess.Popen(
        [NGROK_EXE, 'http', str(PORT),
         '--log', 'stderr', '--log-format', 'json'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    t = threading.Thread(target=_url_reader, args=(proc,), daemon=True)
    t.start()
    return proc


def main():
    print()
    print('=== Encoding + Memory Test Launcher (ngrok) ===')
    print()

    for exe in [PYTHON_EXE, NGROK_EXE]:
        if not os.path.exists(exe):
            print('ERROR: not found: ' + exe)
            sys.exit(1)

    print('Starting server on port {}...'.format(PORT))
    flask_proc = start_flask()
    time.sleep(3)

    print('Starting ngrok tunnel...')
    ng_proc = start_ngrok()

    deadline = time.time() + 40
    while _public_url is None and time.time() < deadline:
        time.sleep(1)

    if _public_url is None:
        print('ERROR: Timed out waiting for ngrok URL.')
        flask_proc.kill(); ng_proc.kill()
        sys.exit(1)

    print()
    print('=' * 60)
    print('  PUBLIC URL:  ' + _public_url)
    print('=' * 60)
    print()
    print('  Encoding task : ' + _public_url + '/encoding/')
    print('  Memory test   : ' + _public_url + '/memory/')
    print()
    print('Keep this window open.  Press Ctrl+C to stop.')
    print()

    try:
        while True:
            time.sleep(10)
            if flask_proc.poll() is not None:
                print('Server stopped -- restarting...')
                flask_proc = start_flask()
                time.sleep(3)
            if ng_proc.poll() is not None:
                print('ngrok stopped -- restarting...')
                ng_proc = start_ngrok()
                deadline2 = time.time() + 30
                while _public_url is None and time.time() < deadline2:
                    time.sleep(1)
                if _public_url:
                    print('New URL: ' + _public_url)
                    print('  Encoding: ' + _public_url + '/encoding/')
                    print('  Memory:   ' + _public_url + '/memory/')
    except KeyboardInterrupt:
        print('\nShutting down...')
        flask_proc.kill(); ng_proc.kill()
        print('Done.')


if __name__ == '__main__':
    main()
