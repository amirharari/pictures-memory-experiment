/**
 * Encoding Task – client-side trial loop
 * BASE is passed from the template (e.g. '/encoding')
 */

const EncodingTask = (() => {
  const cfg      = document.getElementById('config').dataset;
  const IMAGE_MS = parseInt(cfg.imageDuration);
  const HAS_MUSIC = cfg.hasMusic === 'true';

  let BASE         = '';
  let trialIdx     = 0;
  let imageShownAt = 0;
  let response     = '';
  let responseAt   = 0;
  let questionShown = false;
  let keyHandler   = null;

  const el    = id => document.getElementById(id);
  const audio = ()  => el('bg-music');

  function setProgress(current, total) {
    el('progress-bar').style.width = Math.round((current / total) * 100) + '%';
    el('progress-label').textContent = current + ' / ' + total;
  }

  function startMusic() {
    const a = audio();
    if (a && a.paused) a.play().catch(() => {});
  }

  function makeKeyHandler() {
    return function onKey(e) {
      if (response || !questionShown) return;
      if (e.key === '1' || e.key === '2') {
        response   = e.key === '1' ? 'yes' : 'no';
        responseAt = performance.now();
        el('question-panel').classList.add('hidden');
        el('fixation').classList.remove('hidden');
      }
    };
  }

  async function loadNext() {
    response      = '';
    responseAt    = 0;
    questionShown = false;
    el('fixation').classList.add('hidden');
    el('question-panel').classList.add('hidden');
    el('loading-overlay').classList.remove('hidden');

    const data = await fetch(BASE + '/api/next_trial').then(r => r.json());

    if (data.done) {
      const result = await fetch(BASE + '/block_done', { method: 'POST' }).then(r => r.json());
      window.location.href = BASE + '/' + result.next;
      return;
    }

    trialIdx      = data.trial_idx;
    questionShown = data.show_question;
    setProgress(data.trial, data.total);

    const img = el('stimulus');
    img.style.opacity = '0';
    img.src = data.image_url;
    await new Promise(resolve => { img.onload = resolve; img.onerror = resolve; });

    el('loading-overlay').classList.add('hidden');
    if (data.trial === 1 && HAS_MUSIC) startMusic();

    img.style.opacity = '1';
    // Wait for the browser to actually paint the frame before starting the timer
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    imageShownAt = performance.now();
    await wait(IMAGE_MS);

    img.style.opacity = '0';
    await runISI(data);
  }

  async function runISI(data) {
    if (data.show_question) {
      el('question-panel').classList.remove('hidden');
      keyHandler = makeKeyHandler();
      document.addEventListener('keydown', keyHandler);
    } else {
      el('fixation').classList.remove('hidden');
    }

    await wait(data.isi_ms);

    if (keyHandler) {
      document.removeEventListener('keydown', keyHandler);
      keyHandler = null;
    }
    el('fixation').classList.add('hidden');
    el('question-panel').classList.add('hidden');

    const finalResponse = response || (data.show_question ? 'no_response' : '');
    await fetch(BASE + '/api/save_trial', {
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
    init(base) {
      BASE = base;
      loadNext();
    },
  };
})();
