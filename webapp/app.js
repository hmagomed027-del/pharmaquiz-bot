/* ── Telegram WebApp init ─────────────────────────────────────────────── */
const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const INIT_DATA = tg?.initData || '';
const APP = document.getElementById('app');

/* ── State ────────────────────────────────────────────────────────────── */
const S = {
  training: {
    topic: null,
    question: null,
    answeredIds: [],
    answered: false,
    todayTotal: 0,
    todayCorrect: 0,
  },
  exam: {
    topic: null,
    count: 10,
    timeLimit: null,       // seconds or null
    sessionId: null,
    questions: [],
    currentIndex: 0,
    answers: {},           // { question_id: {chosen, is_skipped} }
    startTime: null,
    timerIv: null,
    warnShown: false,
    finished: false,
  },
};

/* ── API ──────────────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'X-Init-Data': INIT_DATA,
      ...(opts.headers || {}),
    },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Helpers ──────────────────────────────────────────────────────────── */
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fmt(sec) {
  const s = Math.abs(sec);
  return `${String(Math.floor(s / 60)).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`;
}

function grade(pct) {
  if (pct >= 90) return { e: '🌟', t: 'Отлично!' };
  if (pct >= 75) return { e: '✅', t: 'Хорошо!' };
  if (pct >= 60) return { e: '📚', t: 'Удовлетворительно' };
  return { e: '📖', t: 'Нужно повторить' };
}

function toast(msg) {
  document.querySelectorAll('.toast').forEach(el => el.remove());
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function haptic(type) {
  if (!tg?.HapticFeedback) return;
  if (type === 'select') tg.HapticFeedback.selectionChanged();
  else if (type === 'ok') tg.HapticFeedback.notificationOccurred('success');
  else if (type === 'err') tg.HapticFeedback.notificationOccurred('error');
  else if (type === 'warn') tg.HapticFeedback.notificationOccurred('warning');
  else tg.HapticFeedback.impactOccurred(type || 'light');
}

function backBtn(show, handler) {
  if (!tg?.BackButton) return;
  if (show) {
    tg.BackButton.offClick();
    tg.BackButton.onClick(handler);
    tg.BackButton.show();
  } else {
    tg.BackButton.hide();
  }
}

/* ── Render helpers ───────────────────────────────────────────────────── */
function setApp(html) { APP.innerHTML = html; }

function page(headerHtml, bodyHtml) {
  setApp(`${headerHtml}<div class="screen">${bodyHtml}</div>`);
}

function hdr(title, onBack) {
  return onBack
    ? `<div class="hdr"><button class="back-btn" onclick="(${onBack})()">&larr;</button><h1>${esc(title)}</h1></div>`
    : `<div class="hdr"><h1>${esc(title)}</h1></div>`;
}

/* ══════════════════════════════════════════════════════════════════════
   HOME
══════════════════════════════════════════════════════════════════════ */
async function showHome() {
  backBtn(false);

  page('', `
    <div style="text-align:center;padding:10px 0 4px">
      <div style="font-size:52px">💊</div>
      <div style="font-size:22px;font-weight:800;margin-top:6px">ФармаКвиз</div>
      <div style="font-size:13px;color:var(--hint);margin-top:4px">Фармакология — подготовка к экзаменам</div>
    </div>

    <div class="stats-row">
      <div class="stat"><div class="stat-val" id="h-total">—</div><div class="stat-lbl">Сегодня</div></div>
      <div class="stat"><div class="stat-val" id="h-corr">—</div><div class="stat-lbl">Правильно</div></div>
      <div class="stat"><div class="stat-val" id="h-pct">—</div><div class="stat-lbl">Точность</div></div>
    </div>

    <div class="menu-grid">
      <button class="menu-card full" onclick="showTopicPick('training')">
        <div class="menu-icon">📖</div>
        <div class="menu-title">Тренировка</div>
        <div class="menu-sub">Вопрос за вопросом с объяснениями</div>
      </button>
      <button class="menu-card" onclick="showExamSetup()">
        <div class="menu-icon">📝</div>
        <div class="menu-title">Экзамен</div>
        <div class="menu-sub">С таймером</div>
      </button>
      <button class="menu-card" onclick="showStats()">
        <div class="menu-icon">📊</div>
        <div class="menu-title">Статистика</div>
        <div class="menu-sub">Мой прогресс</div>
      </button>
    </div>
  `);

  try {
    const stats = await api('/stats');
    const t = stats.today || {};
    const total = t.total || 0;
    const corr  = t.correct || 0;
    document.getElementById('h-total').textContent = total;
    document.getElementById('h-corr').textContent = corr;
    document.getElementById('h-pct').textContent = total > 0 ? `${Math.round(corr/total*100)}%` : '—';
    S.training.todayTotal   = total;
    S.training.todayCorrect = corr;
  } catch (_) {}
}

/* ══════════════════════════════════════════════════════════════════════
   TOPIC PICKER
══════════════════════════════════════════════════════════════════════ */
async function showTopicPick(mode) {
  const titleMap = { training: 'Тренировка', exam: 'Экзамен' };
  backBtn(true, showHome);

  page(hdr(titleMap[mode] || 'Выбор темы', showHome), `
    <div class="topic-list" id="tlist">
      <div class="loading-screen" style="min-height:200px"><div class="spinner"></div></div>
    </div>
  `);

  try {
    const topics = await api('/topics');
    const list = document.getElementById('tlist');
    if (!list) return;
    list.innerHTML = topics.map(t => `
      <button class="topic-item" onclick="onTopicPick('${mode}','${t.topic.replace(/'/g,"\\'")}')">
        <div class="topic-icon">${t.icon}</div>
        <div class="topic-info">
          <div class="topic-name">${esc(t.topic)}</div>
          <div class="topic-cnt">${t.count} вопросов</div>
        </div>
        <div class="topic-arr">›</div>
      </button>
    `).join('');
  } catch (e) {
    document.getElementById('tlist').innerHTML = `
      <div style="text-align:center;color:var(--hint);padding:40px 0">Не удалось загрузить темы</div>
      <button class="btn btn-secondary" onclick="showTopicPick('${mode}')">Повторить</button>
    `;
  }
}

function onTopicPick(mode, topic) {
  if (mode === 'training') {
    S.training.topic = topic;
    S.training.answeredIds = [];
    showTrainingQ();
  } else {
    S.exam.topic = topic;
    showExamSetup();
  }
}

/* ══════════════════════════════════════════════════════════════════════
   TRAINING MODE
══════════════════════════════════════════════════════════════════════ */
async function showTrainingQ() {
  backBtn(true, () => showTopicPick('training'));
  S.training.answered = false;

  page(hdr(S.training.topic, () => showTopicPick('training')), `
    <div style="text-align:center;color:var(--hint);padding:50px 0">
      <div class="spinner" style="margin:0 auto 10px"></div>Загружаем вопрос…
    </div>
  `);

  try {
    const excl = S.training.answeredIds.slice(-50).join(',');
    const q = await api(`/question?topic=${encodeURIComponent(S.training.topic)}&exclude=${excl}`);

    if (!q || !q.id) {
      // Finished all questions
      APP.querySelector('.screen').innerHTML = `
        <div style="text-align:center;padding:40px 0">
          <div style="font-size:48px">🎉</div>
          <div style="font-size:18px;font-weight:700;margin-top:10px">Все вопросы пройдены!</div>
          <div style="color:var(--hint);margin-top:6px;font-size:14px">Начнём заново?</div>
        </div>
        <button class="btn btn-primary" onclick="S.training.answeredIds=[];showTrainingQ()">Начать заново</button>
        <button class="btn btn-secondary" onclick="showTopicPick('training')">Сменить тему</button>
        <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>
      `;
      return;
    }

    S.training.question = q;
    renderTrainingQuestion(q);
  } catch (e) {
    APP.querySelector('.screen').innerHTML = `
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки вопроса</div>
      <button class="btn btn-secondary" onclick="showTrainingQ()">Повторить</button>
    `;
  }
}

function renderTrainingQuestion(q) {
  const sc = APP.querySelector('.screen');
  if (!sc) return;
  const { todayTotal: tt, todayCorrect: tc } = S.training;
  const pct = tt > 0 ? `${Math.round(tc/tt*100)}%` : '';

  sc.innerHTML = `
    <div style="font-size:12px;color:var(--hint)">
      Сегодня: ${tt} отвечено${tc > 0 ? ` · ${tc} правильно ${pct ? '('+pct+')' : ''}` : ''}
    </div>

    <div class="q-card">
      <div class="q-meta">${esc(q.subtopic || q.topic)}</div>
      <div class="q-text">${esc(q.question)}</div>
    </div>

    <div class="answers">
      ${['A','B','C','D'].map(l => `
        <button class="ans-btn" id="t${l}" onclick="submitTraining('${l}')">
          <div class="letter">${l}</div>
          <div>${esc(q.options[l])}</div>
        </button>
      `).join('')}
    </div>

    <div id="t-result"></div>
  `;
}

async function submitTraining(letter) {
  if (S.training.answered) return;
  S.training.answered = true;

  const q = S.training.question;
  ['A','B','C','D'].forEach(l => document.getElementById('t'+l)?.classList.add('disabled'));
  haptic('light');

  try {
    const res = await api('/training/answer', { method: 'POST', body: { question_id: q.id, chosen_answer: letter } });
    const correct = res.correct_answer;
    const ok = letter === correct;

    ['A','B','C','D'].forEach(l => {
      const btn = document.getElementById('t'+l);
      if (!btn) return;
      if (l === correct) btn.classList.add('correct');
      else if (l === letter && !ok) btn.classList.add('wrong');
    });

    haptic(ok ? 'ok' : 'err');

    S.training.todayTotal   = res.today.total;
    S.training.todayCorrect = res.today.correct;
    if (!S.training.answeredIds.includes(q.id)) S.training.answeredIds.push(q.id);

    const rArea = document.getElementById('t-result');
    if (rArea) {
      rArea.innerHTML = `
        <div style="text-align:center;font-size:20px;font-weight:800;color:${ok?'var(--green)':'var(--red)'}">
          ${ok ? '✅ Правильно!' : '❌ Неправильно'}
        </div>
        ${q.drug_name ? `<div id="t-img"><div class="expl-loading"><div class="spinner"></div>Ищем изображение…</div></div>` : ''}
        <div class="expl-loading" id="t-expl-load"><div class="spinner"></div>Генерируем объяснение…</div>
        <div id="t-expl"></div>
        <button class="btn btn-primary" onclick="showTrainingQ()">Следующий вопрос →</button>
        <button class="btn btn-secondary" onclick="showTopicPick('training')">Сменить тему</button>
        <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>
      `;
      if (q.drug_name) loadImg(q.drug_name, 't-img');
      loadExpl(q.id, 't-expl-load', 't-expl');
    }
  } catch (_) {
    toast('Ошибка при отправке ответа');
  }
}

async function loadExpl(qid, loadId, areaId) {
  try {
    const res = await api(`/explanation/${qid}`);
    document.getElementById(loadId)?.remove();
    const el = document.getElementById(areaId);
    if (el) el.innerHTML = `<div class="expl-box">${esc(res.text)}</div>`;
  } catch (_) {
    const el = document.getElementById(loadId);
    if (el) el.textContent = 'Объяснение временно недоступно.';
  }
}

async function loadImg(drug, containerId) {
  try {
    const res = await api(`/image?drug=${encodeURIComponent(drug)}`);
    const c = document.getElementById(containerId);
    if (!c) return;
    if (res.url) {
      c.innerHTML = `<img class="drug-img" src="${esc(res.url)}" alt="${esc(drug)}" onerror="this.parentElement.remove()">`;
    } else {
      c.remove();
    }
  } catch (_) {
    document.getElementById(containerId)?.remove();
  }
}

/* ══════════════════════════════════════════════════════════════════════
   EXAM SETUP
══════════════════════════════════════════════════════════════════════ */
function showExamSetup() {
  backBtn(true, showHome);

  const topicSection = S.exam.topic
    ? `<div style="display:flex;justify-content:space-between;align-items:center">
         <span style="font-weight:600">${esc(S.exam.topic)}</span>
         <button class="chip" onclick="showTopicPick('exam')">Изменить</button>
       </div>`
    : `<button class="btn btn-secondary" onclick="showTopicPick('exam')">Выбрать тему →</button>`;

  const timeLimits = [
    { label: '10 мин', sec: 600 },
    { label: '20 мин', sec: 1200 },
    { label: '30 мин', sec: 1800 },
    { label: 'Без лимита', sec: null },
  ];

  page(hdr('Настройки экзамена', showHome), `
    <div class="card">
      <div class="opt-label">Тема</div>
      ${topicSection}
    </div>

    <div class="card">
      <div class="opt-label">Вопросов</div>
      <div class="chip-group">
        ${[10,20,30].map(n => `
          <button class="chip ${S.exam.count===n?'on':''}" id="cn${n}" onclick="setEC(${n})">${n}</button>
        `).join('')}
      </div>
    </div>

    <div class="card">
      <div class="opt-label">Лимит времени</div>
      <div class="chip-group" style="flex-direction:column;align-items:flex-start">
        ${timeLimits.map(t => `
          <button class="chip ${S.exam.timeLimit===t.sec?'on':''}" id="ct${t.sec}" onclick="setET(${t.sec})">
            ${t.label}
          </button>
        `).join('')}
      </div>
    </div>

    <button class="btn btn-primary" onclick="startExam()" ${!S.exam.topic?'disabled style="opacity:.5"':''}>
      Начать экзамен →
    </button>
  `);
}

function setEC(n) {
  S.exam.count = n;
  document.querySelectorAll('[id^="cn"]').forEach(el => el.classList.remove('on'));
  document.getElementById('cn'+n)?.classList.add('on');
}

function setET(sec) {
  S.exam.timeLimit = sec;
  document.querySelectorAll('[id^="ct"]').forEach(el => el.classList.remove('on'));
  document.getElementById('ct'+sec)?.classList.add('on');
}

/* ══════════════════════════════════════════════════════════════════════
   EXAM MODE
══════════════════════════════════════════════════════════════════════ */
async function startExam() {
  if (!S.exam.topic) { toast('Выберите тему!'); return; }
  setApp(`<div class="loading-screen"><div class="spinner"></div><p>Подготавливаем экзамен…</p></div>`);

  try {
    const res = await api('/exam/start', {
      method: 'POST',
      body: { topic: S.exam.topic, count: S.exam.count, time_limit_seconds: S.exam.timeLimit },
    });
    Object.assign(S.exam, {
      sessionId: res.session_id,
      questions: res.questions,
      currentIndex: 0,
      answers: {},
      startTime: Date.now(),
      warnShown: false,
      finished: false,
    });
    clearInterval(S.exam.timerIv);
    if (S.exam.timeLimit) S.exam.timerIv = setInterval(tickTimer, 1000);
    showExamQ();
  } catch (e) {
    setApp(`<div class="screen">
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка запуска экзамена</div>
      <button class="btn btn-secondary" onclick="showExamSetup()">Назад</button>
    </div>`);
  }
}

function showExamQ() {
  if (S.exam.finished) return;
  const { questions, currentIndex, answers, timeLimit } = S.exam;
  const q = questions[currentIndex];
  const total = questions.length;
  const pct = Math.round(currentIndex / total * 100);
  const picked = answers[q.id]?.chosen;

  backBtn(true, () => {
    if (confirm('Завершить экзамен досрочно?')) finishExam();
  });

  page(`
    <div class="hdr">
      <div style="flex:1">
        <div class="prog-row">
          <span>Вопрос ${currentIndex+1}/${total}</span>
          ${timeLimit ? `<span class="timer" id="etimer">⏱ --:--</span>` : `<span class="timer" id="etimer" style="color:var(--hint)">⏱ 00:00</span>`}
        </div>
        <div class="prog-bar"><div class="prog-fill" style="width:${pct}%"></div></div>
      </div>
    </div>
  `, `
    <div class="q-card">
      <div class="q-meta">${esc(q.subtopic || q.topic)}</div>
      <div class="q-text">${esc(q.question)}</div>
    </div>

    <div class="answers">
      ${['A','B','C','D'].map(l => `
        <button class="ans-btn ${picked===l?'picked':''}" id="eb${l}" onclick="pickExamAns('${l}')">
          <div class="letter">${l}</div>
          <div>${esc(q.options[l])}</div>
        </button>
      `).join('')}
    </div>

    <div style="display:flex;gap:8px">
      <button class="btn btn-secondary" style="flex:1" onclick="skipExamQ()">Пропустить</button>
      <button class="btn btn-primary" style="flex:2" onclick="nextExamQ()">
        ${currentIndex < total-1 ? 'Далее →' : 'Завершить'}
      </button>
    </div>

    <div style="text-align:center;font-size:12px;color:var(--hint)">
      Отвечено: ${Object.keys(answers).length}/${total}
    </div>
  `);

  tickTimer(); // update timer display immediately
}

function pickExamAns(l) {
  if (S.exam.finished) return;
  const q = S.exam.questions[S.exam.currentIndex];
  S.exam.answers[q.id] = { chosen: l, is_skipped: false };
  document.querySelectorAll('[id^="eb"]').forEach(btn => btn.classList.remove('picked'));
  document.getElementById('eb'+l)?.classList.add('picked');
  haptic('select');
}

function skipExamQ() {
  const q = S.exam.questions[S.exam.currentIndex];
  S.exam.answers[q.id] = { chosen: null, is_skipped: true };
  nextExamQ();
}

function nextExamQ() {
  const { currentIndex, questions } = S.exam;
  if (currentIndex < questions.length - 1) {
    S.exam.currentIndex++;
    showExamQ();
  } else {
    finishExam();
  }
}

function tickTimer() {
  const el = document.getElementById('etimer');
  if (!el) return;
  const elapsed = Math.floor((Date.now() - S.exam.startTime) / 1000);
  const limit = S.exam.timeLimit;

  if (limit) {
    const rem = limit - elapsed;
    if (rem <= 0) {
      clearInterval(S.exam.timerIv);
      el.textContent = '⏱ 00:00';
      el.className = 'timer warn';
      toast('⏰ Время вышло!');
      haptic('warn');
      setTimeout(finishExam, 1500);
      return;
    }
    el.textContent = `⏱ ${fmt(rem)}`;
    if (rem <= 120 && !S.exam.warnShown) {
      S.exam.warnShown = true;
      el.className = 'timer warn';
      toast('⚠️ Осталось 2 минуты!');
      haptic('warn');
    }
  } else {
    el.textContent = `⏱ ${fmt(elapsed)}`;
  }
}

async function finishExam() {
  if (S.exam.finished) return;
  S.exam.finished = true;
  clearInterval(S.exam.timerIv);
  backBtn(false);

  setApp(`<div class="loading-screen"><div class="spinner"></div><p>Подводим итоги…</p></div>`);

  const elapsed = Math.floor((Date.now() - S.exam.startTime) / 1000);
  const answers = S.exam.questions.map(q => ({
    question_id: q.id,
    chosen_answer: S.exam.answers[q.id]?.chosen ?? null,
    is_skipped: S.exam.answers[q.id]?.is_skipped ?? false,
  }));

  try {
    const result = await api('/exam/finish', {
      method: 'POST',
      body: { session_id: S.exam.sessionId, answers, elapsed_seconds: elapsed },
    });
    showExamResult(result);
  } catch (_) {
    setApp(`<div class="screen">
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка при завершении</div>
      <button class="btn btn-secondary" onclick="showHome()">На главную</button>
    </div>`);
  }
}

function showExamResult(result) {
  backBtn(false);
  const pct = result.percent;
  const g = grade(pct);
  const timeStr = fmt(result.elapsed_seconds);
  const limitStr = S.exam.timeLimit ? ` из ${fmt(S.exam.timeLimit)}` : '';
  const wrong = result.details.filter(d => !d.is_correct && !d.is_skipped);
  const skipped = result.details.filter(d => d.is_skipped);

  page(hdr('Результат экзамена'), `
    <div class="card" style="text-align:center">
      <div style="font-size:44px">${g.e}</div>
      <div class="result-pct">${pct}%</div>
      <div class="result-sub">${result.correct} из ${result.total} правильно</div>
      <div class="result-grade">${g.t}</div>
    </div>

    <div class="card">
      <div class="kv-list">
        <div class="kv-row"><span>Тема</span><span class="kv-val">${esc(S.exam.topic)}</span></div>
        <div class="kv-row"><span>Время</span><span class="kv-val">⏱ ${timeStr}${limitStr}</span></div>
        <div class="kv-row"><span>Правильных</span><span class="kv-val kv-green">${result.correct}</span></div>
        <div class="kv-row"><span>Неправильных</span><span class="kv-val kv-red">${wrong.length}</span></div>
        ${skipped.length ? `<div class="kv-row"><span>Пропущено</span><span class="kv-val" style="color:var(--hint)">${skipped.length}</span></div>` : ''}
      </div>
    </div>

    ${wrong.length > 0 ? `
      <div class="section-title">Разбор ошибок</div>
      ${wrong.map((d, i) => `
        <div class="err-item">
          <div class="err-q">${esc(d.question)}</div>
          <div>
            ${d.chosen_answer ? `<div class="err-wrong">❌ ${d.chosen_answer}) ${esc(d.options[d.chosen_answer])}</div>` : ''}
            <div class="err-corr">✅ ${d.correct_answer}) ${esc(d.options[d.correct_answer])}</div>
          </div>
          <button class="chip" onclick="toggleExpl('xe${i}','${d.question_id}',this)">
            Объяснение
          </button>
          <div id="xe${i}" style="display:none"></div>
        </div>
      `).join('')}
    ` : ''}

    <button class="btn btn-primary" onclick="showHome()">На главную</button>
    <button class="btn btn-secondary" onclick="S.exam.sessionId=null;S.exam.questions=[];S.exam.answers={};S.exam.finished=false;showExamSetup()">Повторить</button>
  `);
}

async function toggleExpl(elId, qid, btn) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (el.style.display !== 'none') { el.style.display = 'none'; btn.textContent = 'Объяснение'; return; }
  el.style.display = 'block';
  btn.textContent = 'Скрыть';
  if (el.innerHTML) return;
  el.innerHTML = `<div class="expl-loading"><div class="spinner"></div>Загружаем…</div>`;
  try {
    const res = await api(`/explanation/${qid}`);
    el.innerHTML = `<div class="expl-box">${esc(res.text)}</div>`;
  } catch (_) {
    el.innerHTML = `<div style="color:var(--hint);font-size:13px">Объяснение недоступно</div>`;
  }
}

/* ══════════════════════════════════════════════════════════════════════
   STATS
══════════════════════════════════════════════════════════════════════ */
async function showStats() {
  backBtn(true, showHome);
  page(hdr('Статистика', showHome), `
    <div class="loading-screen" style="min-height:200px"><div class="spinner"></div></div>
  `);

  try {
    const stats = await api('/stats');
    const today = stats.today || {};
    const topics = stats.topics || [];

    const sc = APP.querySelector('.screen');
    if (!sc) return;

    const accTotal = stats.total || 0;
    const accCorr  = stats.correct || 0;
    const accPct   = accTotal > 0 ? Math.round(accCorr/accTotal*100) : 0;

    sc.innerHTML = `
      <div class="stats-row">
        <div class="stat"><div class="stat-val">${accTotal}</div><div class="stat-lbl">Всего</div></div>
        <div class="stat"><div class="stat-val">${accPct}%</div><div class="stat-lbl">Точность</div></div>
        <div class="stat"><div class="stat-val">${stats.exams_completed||0}</div><div class="stat-lbl">Экзаменов</div></div>
      </div>

      <div class="card">
        <div class="opt-label" style="margin-bottom:8px">Сегодня</div>
        <div class="kv-list">
          <div class="kv-row"><span>Ответов</span><span class="kv-val">${today.total||0}</span></div>
          <div class="kv-row"><span>Правильных</span><span class="kv-val kv-green">${today.correct||0}</span></div>
        </div>
      </div>

      ${topics.length > 0 ? `
        <div class="card">
          <div class="opt-label" style="margin-bottom:12px">По темам</div>
          ${topics.map(t => {
            const p = t.total > 0 ? Math.round(t.correct/t.total*100) : 0;
            const barColor = p >= 75 ? 'var(--green)' : p >= 50 ? 'var(--orange)' : 'var(--red)';
            return `
              <div class="topic-bar-wrap">
                <div class="topic-bar-head">
                  <span style="font-size:14px">${esc(t.topic)}</span>
                  <span style="font-weight:700;font-size:14px">${p}%</span>
                </div>
                <div class="prog-bar"><div class="prog-fill" style="width:${p}%;background:${barColor}"></div></div>
                <div style="font-size:12px;color:var(--hint);margin-top:2px">${t.correct}/${t.total} правильно</div>
              </div>
            `;
          }).join('')}
        </div>
      ` : ''}

      <button class="btn btn-secondary" onclick="showHome()">На главную</button>
    `;
  } catch (_) {
    const sc = APP.querySelector('.screen');
    if (sc) sc.innerHTML = `
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки статистики</div>
      <button class="btn btn-secondary" onclick="showHome()">На главную</button>
    `;
  }
}

/* ══════════════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════════════ */
(async function init() {
  try {
    await api('/topics'); // also creates user record via auth middleware
    showHome();
  } catch (_) {
    setApp(`
      <div class="screen" style="align-items:center;justify-content:center;min-height:100vh;text-align:center">
        <div style="font-size:52px">⚠️</div>
        <div style="font-size:18px;font-weight:700;margin-top:12px">Ошибка подключения</div>
        <div style="color:var(--hint);margin-top:8px;font-size:14px">
          Откройте приложение через Telegram<br>или проверьте настройки сервера
        </div>
        <button class="btn btn-secondary" style="margin-top:20px" onclick="location.reload()">Перезагрузить</button>
      </div>
    `);
  }
})();
