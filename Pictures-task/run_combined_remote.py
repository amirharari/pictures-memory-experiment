#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Combined Remote Launcher
========================
Starts combined_app.py (memory test + encoding) on port 5000
and exposes it via ngrok.

Memory Test : https://<ngrok>/
Encoding    : https://<ngrok>/encoding/
"""

import os
import sys
import time
import json
import subprocess
import threading

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PORT      = 5000
NGROK_EXE = r'C:\Pictures-task\ngrok.exe'

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
        [sys.executable, os.path.join(BASE_DIR, 'combined_app.py')],
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
    print('=== Combined Remote Launcher ===')
    print()

    if not os.path.exists(NGROK_EXE):
        print('ERROR: ngrok.exe not found at: ' + NGROK_EXE)
        sys.exit(1)

    # Kill any stale processes on port 5000
    subprocess.call(
        ['powershell', '-Command',
         'Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue '
         '| Select-Object -ExpandProperty OwningProcess '
         '| Where-Object {$_ -ne ' + str(os.getpid()) + '} '
         '| ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.call(
        ['powershell', '-Command',
         'Stop-Process -Name ngrok -Force -ErrorAction SilentlyContinue'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    print('Starting combined server on port {}...'.format(PORT))
    flask_proc = start_flask()
    time.sleep(4)

    print('Starting ngrok tunnel...')
    ng_proc = start_ngrok()

    deadline = time.time() + 40
    while _public_url is None and time.time() < deadline:
        time.sleep(1)

    if _public_url is None:
        print('ERROR: Timed out waiting for ngrok URL.')
        flask_proc.kill()
        ng_proc.kill()
        sys.exit(1)

    print()
    print('=' * 60)
    print('  Memory Test : ' + _public_url + '/')
    print('  Encoding    : ' + _public_url + '/encoding/')
    print('=' * 60)
    print()
    print('Keep this window open.  Press Ctrl+C to stop.')
    print()

    try:
        while True:
            time.sleep(10)
            if flask_proc.poll() is not None:
                print('Server crashed -- restarting...')
                flask_proc = start_flask()
                time.sleep(4)
            if ng_proc.poll() is not None:
                print('ngrok stopped -- restarting...')
                ng_proc = start_ngrok()
                deadline2 = time.time() + 30
                while _public_url is None and time.time() < deadline2:
                    time.sleep(1)
                if _public_url:
                    print('New URL: ' + _public_url)
    except KeyboardInterrupt:
        print('\nShutting down...')
        flask_proc.kill()
        ng_proc.kill()
        print('Done.')


if __name__ == '__main__':
    main()
