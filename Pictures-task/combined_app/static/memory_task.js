/**
 * Memory Task – client-side logic
 * BASE is passed from the template (e.g. '/memory')
 */

const MemoryTask = (() => {
  let BASE          = '';
  let trialIdx      = 0;
  let recognition   = null;
  let certainty     = null;
  let valence       = null;
  let imgShownAt    = 0;
  let recognitionAt = 0;
  let certaintyAt   = 0;
  let valenceAt     = 0;
  let currentBlock  = null;

  const IMAGE_MS = 4000;

  const el    = id => document.getElementById(id);
  const audio = ()  => el('bg-music');

  function setProgress(current, total) {
    el('progress-bar').style.width = Math.round((current / total) * 100) + '%';
    el('progress-label').textContent = current + ' / ' + total;
  }

  function setOverlay(visible) {
    el('loading-overlay').classList.toggle('hidden', !visible);
  }

  function setMusic(shouldPlay) {
    const a = audio();
    if (!a) return;
    if (shouldPlay) {
      if (a.paused) a.play().catch(() => {});
    } else {
      if (!a.paused) { a.pause(); a.currentTime = 0; }
    }
  }

  function showBlockTransition(msg, onDone) {
    const overlay = el('block-transition');
    el('block-transition-text').textContent = msg;
    overlay.classList.remove('hidden');
    overlay.onclick = () => {
      overlay.classList.add('hidden');
      overlay.onclick = null;
      onDone();
    };
  }

  function fadeImage(src, onReady) {
    const img = el('stimulus');
    img.style.opacity = '0';
    setTimeout(() => {
      img.src = src;
      img.onload = () => { img.style.opacity = '1'; onReady(); };
    }, 200);
  }

  function hideAllSteps() {
    recognition = null;
    certainty   = null;
    valence     = null;
    ['step-recognition', 'step-certainty', 'step-valence', 'step-arousal']
      .forEach(id => el(id).classList.add('hidden'));
  }

  async function loadNext() {
    setOverlay(true);
    hideAllSteps();

    const data = await fetch(BASE + '/api/next_image').then(r => r.json());

    if (data.done) {
      window.location.href = BASE + '/done';
      return;
    }

    trialIdx = data.trial_idx;
    setProgress(data.trial, data.total);

    if (data.block_changed && currentBlock !== null) {
      setOverlay(false);
      setMusic(false);
      showBlockTransition('החלק הבא יתנהל ללא מוזיקה.', () => startTrial(data));
    } else {
      startTrial(data);
    }

    currentBlock = data.block;
  }

  function startTrial(data) {
    setMusic(data.music);
    fadeImage(data.image_url, () => {
      setOverlay(false);
      imgShownAt = performance.now();
      setTimeout(() => el('step-recognition').classList.remove('hidden'), IMAGE_MS);
    });
  }

  window.handleRecognition = function (answer) {
    if (recognition !== null) return;
    recognition   = answer;
    recognitionAt = performance.now();
    el('step-recognition').classList.add('hidden');
    el('step-certainty').classList.remove('hidden');
  };

  window.handleCertainty = function (rating) {
    certainty   = rating;
    certaintyAt = performance.now();
    el('step-certainty').classList.add('hidden');
    el('step-valence').classList.remove('hidden');
  };

  window.handleValence = function (rating) {
    valence   = rating;
    valenceAt = performance.now();
    el('step-valence').classList.add('hidden');
    el('step-arousal').classList.remove('hidden');
  };

  window.handleArousal = async function (rating) {
    const arousalAt = performance.now();
    setOverlay(true);

    await fetch(BASE + '/api/save_response', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trial_idx:         trialIdx,
        recognition:       recognition,
        certainty:         certainty,
        image_valence:     valence,
        image_arousal:     rating,
        rt_recognition_ms: Math.round(recognitionAt - imgShownAt),
        rt_certainty_ms:   Math.round(certaintyAt   - recognitionAt),
        rt_valence_ms:     Math.round(valenceAt      - certaintyAt),
        rt_arousal_ms:     Math.round(arousalAt      - valenceAt),
      }),
    });

    await loadNext();
  };

  return {
    init(total, base) {
      BASE = base;
      loadNext();
    },
  };
})();
