/**
 * Encoding Task – client-side trial loop
 *
 * Flow per trial:
 *   show image (IMAGE_DURATION_MS)
 *   → hide image, show fixation or incidental question (ISI_MS)
 *   → keyboard 1/2 captured during ISI if question shown
 *   → save trial → next trial
 *
 * At end of block: POST /block_done → redirect to next phase
 */

const EncodingTask = (() => {
  const cfg   = document.getElementById('config').dataset;
  const IMAGE_MS  = parseInt(cfg.imageDuration);
  const HAS_MUSIC = cfg.hasMusic === 'true';

  let trialIdx    = 0;
  let imageShownAt = 0;
  let response    = '';
  let responseAt  = 0;
  let questionShown = false;
  let keyHandler  = null;

  const el    = id => document.getElementById(id);
  const audio = ()  => el('bg-music');

  // ── Progress ──────────────────────────────────────
  function setProgress(current, total) {
    const pct = Math.round((current / total) * 100);
    el('progress-bar').style.width = pct + '%';
    el('progress-label').textContent = current + ' / ' + total;
  }

  // ── Music ─────────────────────────────────────────
  function startMusic() {
    const a = audio();
    if (a && a.paused) a.play().catch(() => {});
  }

  // ── Keyboard handler during ISI ───────────────────
  function makeKeyHandler(resolve) {
    return function onKey(e) {
      if (response) return;
      if (!questionShown) return;
      if (e.key === '1' || e.key === '2') {
        response   = e.key === '1' ? 'beginner' : 'professional';
        responseAt = performance.now();
        el('question-panel').classList.add('hidden');
        el('fixation').classList.remove('hidden');
      }
    };
  }

  // ── Core trial loader ─────────────────────────────
  async function loadNext() {
    // Reset state
    response      = '';
    responseAt    = 0;
    questionShown = false;

    el('fixation').classList.add('hidden');
    el('question-panel').classList.add('hidden');
    el('loading-overlay').classList.remove('hidden');

    const data = await fetch('/api/next_trial').then(r => r.json());

    if (data.done) {
      // End of block — notify server and follow redirect
      const result = await fetch('/block_done', { method: 'POST' }).then(r => r.json());
      window.location.href = '/' + result.next;
      return;
    }

    trialIdx      = data.trial_idx;
    questionShown = data.show_question;
    setProgress(data.trial, data.total);

    // Preload image
    const img = el('stimulus');
    img.style.opacity = '0';
    img.src = data.image_url;

    await new Promise(resolve => {
      img.onload = resolve;
      img.onerror = resolve;  // continue even if image fails
    });

    el('loading-overlay').classList.add('hidden');

    // If first trial, start music
    if (data.trial === 1 && HAS_MUSIC) startMusic();

    // Show image
    img.style.opacity = '1';
    imageShownAt = performance.now();

    await wait(IMAGE_MS);

    // Hide image, start ISI
    img.style.opacity = '0';
    await runISI(data);
  }

  async function runISI(data) {
    if (data.show_question) {
      el('question-panel').classList.remove('hidden');
    } else {
      el('fixation').classList.remove('hidden');
    }

    // Listen for keyboard
    if (data.show_question) {
      keyHandler = makeKeyHandler();
      document.addEventListener('keydown', keyHandler);
    }

    await wait(data.isi_ms);

    // Clean up
    if (keyHandler) {
      document.removeEventListener('keydown', keyHandler);
      keyHandler = null;
    }
    el('fixation').classList.add('hidden');
    el('question-panel').classList.add('hidden');

    // Save trial
    const finalResponse = response || (data.show_question ? 'no_response' : '');
    await fetch('/api/save_trial', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trial_idx:      data.trial_idx,
        image_onset_ms: Math.round(imageShownAt),
        isi_dur_ms:     data.isi_ms,
        question_shown: data.show_question,
        response:       finalResponse,
        rt_ms:          responseAt ? Math.round(responseAt - imageShownAt) : '',
      }),
    });

    loadNext();
  }

  function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  return {
    init() { loadNext(); },
  };
})();
