/* ── Telegram WebApp init ─────────────────────────────────────────────── */
const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

/* ── User info ────────────────────────────────────────────────────────── */
const TG_USER    = tg?.initDataUnsafe?.user || {};
const FIRST_NAME = TG_USER.first_name || '';
const USERNAME   = TG_USER.username   || '';
const DISPLAY    = FIRST_NAME || (USERNAME ? `@${USERNAME}` : 'Студент');
const AVATAR_LTR = (FIRST_NAME[0] || USERNAME[0] || 'С').toUpperCase();
const INIT_DATA  = tg?.initData || '';

const APP = document.getElementById('app');

/* ── State ────────────────────────────────────────────────────────────── */
const S = {
  training: {
    topic: null, question: null, answeredIds: [],
    answered: false, todayTotal: 0, todayCorrect: 0,
    history: [],
  },
  exam: {
    topic: null, count: 10, timeLimit: null,
    sessionId: null, questions: [], currentIndex: 0,
    answers: {}, startTime: null, timerIv: null,
    warnShown: false, finished: false,
  },
  cls: {
    section: null, topic: null, mode: 'mcq',
    exercise: null, answered: false, answeredIds: [],
    sortItems: [], sortIndex: 0, sortAnswers: {},
  },
};

/* ── API ──────────────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', 'X-Init-Data': INIT_DATA, ...(opts.headers || {}) },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${res.status}`); }
  return res.json();
}

/* ── Helpers ──────────────────────────────────────────────────────────── */
function esc(s) { return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function fmt(s) { const a = Math.abs(s); return `${String(Math.floor(a/60)).padStart(2,'0')}:${String(a%60).padStart(2,'0')}`; }

function grade(pct) {
  if (pct >= 90) return { e:'🌟', t:'Блестяще!' };
  if (pct >= 75) return { e:'✅', t:'Хорошо!' };
  if (pct >= 60) return { e:'📚', t:'Удовлетворительно' };
  return { e:'📖', t:'Нужно повторить' };
}

const QUOTES_PASS = [
  { text: 'Медицина — это наука неопределённости и искусство вероятности.', author: 'Уильям Ослер' },
  { text: 'Знание — это не то, что вы запомнили, а то, что вы не можете забыть.', author: 'Альберт Эйнштейн' },
  { text: 'Лучший врач тот, кто знает бесполезность большинства лекарств.', author: 'Бенджамин Франклин' },
  { text: 'Наука — это организованное знание. Мудрость — это организованная жизнь.', author: 'Иммануил Кант' },
  { text: 'Труд всегда даёт, лень всегда берёт.', author: 'Народная мудрость' },
  { text: 'Образование — это то, что остаётся, когда забыто всё выученное в школе.', author: 'Альберт Эйнштейн' },
  { text: 'Врач лечит — природа исцеляет. Но знание механизма — это сила врача.', author: 'Гиппократ' },
  { text: 'Совершенство — это не пункт назначения, а способ путешествия.', author: 'Харлод Хорт' },
  { text: 'Победа — это не конец пути, а один из шагов на нём.', author: 'Уинстон Черчилль' },
  { text: 'Не бойся расти медленно — бойся стоять на месте.', author: 'Китайская мудрость' },
  { text: 'Каждый эксперт когда-то был новичком. Ты движешься в правильном направлении.', author: 'Хелен Хейс' },
  { text: 'Знание — сила, но применённое знание — настоящая мудрость врача.', author: 'Фрэнсис Бэкон' },
];

const QUOTES_FAIL = [
  { text: 'Падение — это не поражение. Поражение — это когда ты решаешь не вставать.', author: 'Конфуций' },
  { text: 'Я не терпел поражений. Я просто нашёл 10 000 способов, которые не работают.', author: 'Томас Эдисон' },
  { text: 'Трудности закаляют нас для более высоких достижений.', author: 'Сенека' },
  { text: 'Не важно, как медленно ты идёшь, главное — не останавливаться.', author: 'Конфуций' },
  { text: 'Каждая ошибка — это урок, который приближает тебя к мастерству.', author: 'Джон Дьюи' },
  { text: 'Великие врачи не рождаются великими — они становятся ими через повторение и упорство.', author: 'Уильям Ослер' },
  { text: 'Ошибки — это доказательство того, что ты стараешься.', author: 'Народная мудрость' },
  { text: 'Путь в тысячу миль начинается с одного шага. Сделай следующий.', author: 'Лао-Цзы' },
  { text: 'Успех — это движение от неудачи к неудаче без потери энтузиазма.', author: 'Уинстон Черчилль' },
  { text: 'Повторение — мать учения. Разбери ошибки, и следующий результат будет лучше.', author: 'Народная мудрость' },
  { text: 'Медицина требует смирения перед сложностью. Это нормально — учиться снова.', author: 'Авиценна' },
  { text: 'Сложность сегодня — это компетентность завтра.', author: 'Народная мудрость' },
];

function getQuote(passed) {
  const arr = passed ? QUOTES_PASS : QUOTES_FAIL;
  return arr[Math.floor(Math.random() * arr.length)];
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 6)  return 'Ночная смена! 🌙';
  if (h < 12) return 'Доброе утро!';
  if (h < 17) return 'Добрый день!';
  if (h < 21) return 'Добрый вечер!';
  return 'Вечерняя учёба 🌙';
}

function getMotto() {
  const mottos = [
    'Повторение — мать учения. Ещё один вопрос!',
    'Каждый правильный ответ — шаг к пятёрке.',
    'Фармакология — это логика, а не зубрёжка.',
    'Ты справишься! Главное — понять механизм.',
    'Отличный врач знает не только «что», но и «почему».',
    'Сегодняшняя тренировка — это завтрашняя уверенность.',
    'Механизм → Применение → Побочки. Три кита фармакологии!',
  ];
  return mottos[new Date().getDate() % mottos.length];
}

function toast(msg) {
  document.querySelectorAll('.toast').forEach(e => e.remove());
  const el = document.createElement('div');
  el.className = 'toast'; el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function haptic(t) {
  if (!tg?.HapticFeedback) return;
  if (t === 'ok') tg.HapticFeedback.notificationOccurred('success');
  else if (t === 'err') tg.HapticFeedback.notificationOccurred('error');
  else if (t === 'warn') tg.HapticFeedback.notificationOccurred('warning');
  else if (t === 'sel') tg.HapticFeedback.selectionChanged();
  else tg.HapticFeedback.impactOccurred(t || 'light');
}

function backBtn(show, fn) {
  if (!tg?.BackButton) return;
  if (show) { tg.BackButton.offClick(); tg.BackButton.onClick(fn); tg.BackButton.show(); }
  else tg.BackButton.hide();
}

function confetti() {
  const colors = ['#2D6A4F','#52B788','#f4a523','#3a7bd5','#d62828','#40916C'];
  for (let i = 0; i < 60; i++) {
    const el = document.createElement('div');
    el.className = 'confetti-piece';
    el.style.cssText = `left:${Math.random()*100}%;top:-20px;background:${colors[i%colors.length]};
      --dur:${.8+Math.random()*1.2}s;--rot:${Math.random()*720}deg;
      border-radius:${Math.random()>.5?'50%':'2px'};
      width:${6+Math.random()*8}px;height:${6+Math.random()*8}px;`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }
}

/* ── Render helpers ───────────────────────────────────────────────────── */
function setApp(html) { APP.innerHTML = html; }
function page(hdrHtml, bodyHtml) { setApp(`${hdrHtml}<div class="screen">${bodyHtml}</div>`); }
function hdr(title, onBack) {
  return onBack
    ? `<div class="hdr"><button class="back-btn" onclick="(${onBack})()">&larr;</button><h1>${esc(title)}</h1></div>`
    : `<div class="hdr"><h1>${esc(title)}</h1></div>`;
}

/* ── Avatar HTML ─────────────────────────────────────────────────────── */
function avatarHtml(size = 52) {
  if (TG_USER.photo_url) {
    return `<img class="avatar-img" src="${esc(TG_USER.photo_url)}" width="${size}" height="${size}" style="width:${size}px;height:${size}px" onerror="this.outerHTML=avatarLetterHtml(${size})">`;
  }
  return `<div class="avatar" style="width:${size}px;height:${size}px;font-size:${Math.round(size*.4)}px">${AVATAR_LTR}</div>`;
}
function avatarLetterHtml(size) {
  return `<div class="avatar" style="width:${size}px;height:${size}px;font-size:${Math.round(size*.4)}px">${AVATAR_LTR}</div>`;
}

/* ══════════════════════════════════════════════════════════════════════
   HOME
══════════════════════════════════════════════════════════════════════ */
async function showHome() {
  backBtn(false);

  page('', `
    <div class="hero">
      ${avatarHtml(52)}
      <div class="hero-info">
        <div class="hero-greet">${getGreeting()}</div>
        <div class="hero-name">${esc(DISPLAY)}</div>
        <div class="hero-streak" id="h-streak">Загружаем статистику…</div>
      </div>
    </div>

    <div class="motto">${getMotto()}</div>

    <div class="stats-row">
      <div class="stat"><div class="stat-val" id="h-total">—</div><div class="stat-lbl">Сегодня</div></div>
      <div class="stat"><div class="stat-val" id="h-corr">—</div><div class="stat-lbl">Правильно</div></div>
      <div class="stat"><div class="stat-val" id="h-pct">—</div><div class="stat-lbl">Точность</div></div>
    </div>

    <div class="menu-grid">
      <button class="menu-card full" onclick="showTopicPick('training')">
        <div class="menu-icon-bubble">📖</div>
        <div class="menu-body">
          <div class="menu-title">Тренировка</div>
          <div class="menu-sub">Вопрос за вопросом с объяснениями</div>
        </div>
      </button>
      <button class="menu-card c-blue" onclick="showExamSetup()">
        <div class="menu-icon-bubble">🎯</div>
        <div class="menu-title">Экзамен</div>
        <div class="menu-sub">С таймером и разбором ошибок</div>
      </button>
      <button class="menu-card c-purple" onclick="showStats()">
        <div class="menu-icon-bubble">📈</div>
        <div class="menu-title">Статистика</div>
        <div class="menu-sub">Мой прогресс по темам</div>
      </button>
      <button class="menu-card c-teal" onclick="showClassificationPick()" style="grid-column:span 2">
        <div class="menu-icon-bubble">📋</div>
        <div class="menu-body">
          <div class="menu-title">Классификации</div>
          <div class="menu-sub">Запоминай препараты по группам, поколениям и механизмам</div>
        </div>
      </button>
    </div>
  `);

  try {
    const stats = await api('/stats');
    const t = stats.today || {};
    const total = t.total || 0; const corr = t.correct || 0;
    document.getElementById('h-total').textContent = total;
    document.getElementById('h-corr').textContent = corr;
    document.getElementById('h-pct').textContent = total > 0 ? `${Math.round(corr/total*100)}%` : '—';
    S.training.todayTotal = total; S.training.todayCorrect = corr;

    const allTotal = stats.total || 0;
    const streak = document.getElementById('h-streak');
    if (streak) {
      if (total > 0) streak.textContent = `${total} ответов сегодня · ${corr} верных`;
      else streak.textContent = `Всего ответов: ${allTotal}`;
    }
  } catch (_) {
    const streak = document.getElementById('h-streak');
    if (streak) streak.textContent = 'Начни тренировку!';
  }
}

/* ══════════════════════════════════════════════════════════════════════
   TOPIC PICKER
══════════════════════════════════════════════════════════════════════ */
async function showTopicPick(mode) {
  const titles = { training: 'Тренировка', exam: 'Экзамен' };
  backBtn(true, showHome);

  page(hdr(titles[mode] || 'Выбор темы', () => showHome()), `
    <div class="topic-list" id="tlist">
      <div class="loading-screen" style="min-height:200px"><div class="spinner"></div></div>
    </div>
  `);

  try {
    const [topics, stats] = await Promise.all([
      api('/topics'),
      api('/stats').catch(() => ({ topics: [] })),
    ]);

    const topicStats = {};
    (stats.topics || []).forEach(t => { topicStats[t.topic] = t; });

    const list = document.getElementById('tlist');
    if (!list) return;
    list.innerHTML = topics.map(t => {
      const ts = topicStats[t.topic];
      const pct = ts && ts.total > 0 ? Math.round(ts.correct / ts.total * 100) : null;
      const pctColor = pct === null ? '' : pct >= 75 ? '#2D6A4F' : pct >= 50 ? '#e67e22' : '#d62828';
      const pctBadge = pct !== null
        ? `<div class="topic-pct-badge" style="background:${pctColor}18;color:${pctColor}">
             <span>${pct >= 75 ? '✅' : pct >= 50 ? '📈' : '📉'}</span>${pct}% верных
           </div>`
        : '';
      const col = t.color || '#95A5A6';
      return `
        <button class="topic-item" onclick="onTopicPick('${mode}','${t.topic.replace(/'/g,"\\'")}')">
          <div class="topic-icon-bubble" style="background:${col}20;border:1.5px solid ${col}38">
            ${t.icon}
          </div>
          <div class="topic-info">
            <div class="topic-name">${esc(t.topic)}</div>
            <div class="topic-cnt">${t.count} вопросов</div>
            ${pctBadge}
          </div>
          <div class="topic-arr">›</div>
        </button>
      `;
    }).join('');
  } catch (_) {
    const l = document.getElementById('tlist');
    if (l) l.innerHTML = `<div style="text-align:center;color:var(--hint);padding:40px 0">Не удалось загрузить темы</div>
      <button class="btn btn-secondary" onclick="showTopicPick('${mode}')">Повторить</button>`;
  }
}

function onTopicPick(mode, topic) {
  haptic('sel');
  if (mode === 'training') {
    S.training.topic = topic;
    // Restore seen IDs from localStorage so questions don't repeat across sessions
    S.training.answeredIds = _lsGet(`train_${topic}`).slice(-100);
    S.training.history = [];
    showTrainingQ();
  } else { S.exam.topic = topic; showExamSetup(); }
}

/* ══════════════════════════════════════════════════════════════════════
   TRAINING MODE
══════════════════════════════════════════════════════════════════════ */
async function showTrainingQ() {
  backBtn(true, () => showTopicPick('training'));
  S.training.answered = false;

  page(hdr(S.training.topic, () => showTopicPick('training')), `
    <div class="loading-screen" style="min-height:200px">
      <div class="spinner"></div><p>Загружаем вопрос…</p>
    </div>
  `);

  try {
    const excl = S.training.answeredIds.slice(-50).join(',');
    const q = await api(`/question?topic=${encodeURIComponent(S.training.topic)}&exclude=${excl}`);

    if (!q || !q.id) {
      APP.querySelector('.screen').innerHTML = `
        <div style="text-align:center;padding:40px 0">
          <div style="font-size:52px">🎉</div>
          <div style="font-size:18px;font-weight:800;margin-top:12px">Все вопросы пройдены!</div>
          <div style="color:var(--hint);margin-top:6px;font-size:14px">${esc(FIRST_NAME) ? `Отличная работа, ${esc(FIRST_NAME)}!` : 'Отличная работа!'}</div>
        </div>
        <button class="btn btn-primary" onclick="S.training.answeredIds=[];showTrainingQ()">Начать заново</button>
        <button class="btn btn-secondary" onclick="showTopicPick('training')">Сменить тему</button>
        <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>
      `;
      return;
    }
    S.training.question = shuffleQuestion(q);
    renderTrainingQ(S.training.question);
  } catch (_) {
    const sc = APP.querySelector('.screen');
    if (sc) sc.innerHTML = `
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки</div>
      <button class="btn btn-secondary" onclick="showTrainingQ()">Повторить</button>
    `;
  }
}

function isMultiAnswer(q) { return q.correct_answer && q.correct_answer.includes(','); }

function shuffleQuestion(q) {
  const letters = ['A', 'B', 'C', 'D'];
  const shuffled = [...letters].sort(() => Math.random() - 0.5);
  const oldOpts = q.options;
  const newOpts = {};
  const remap = {};   // oldL → newL  (for converting DB correct_answer to display position)
  const unmap = {};   // newL → oldL  (for converting chosen display letter back to DB letter)
  shuffled.forEach((oldL, i) => {
    const newL = letters[i];
    newOpts[newL] = oldOpts[oldL];
    remap[oldL] = newL;
    unmap[newL] = oldL;
  });
  const correctLetters = q.correct_answer.split(',').map(l => remap[l.trim()]);
  return { ...q, options: newOpts, correct_answer: correctLetters.join(','), _remap: remap, _unmap: unmap };
}

/* localStorage helpers — survive page reload */
function _lsGet(key) {
  try { return JSON.parse(localStorage.getItem(key) || '[]'); } catch (_) { return []; }
}
function _lsSet(key, arr) {
  try { localStorage.setItem(key, JSON.stringify(arr)); } catch (_) {}
}

function renderTrainingQ(q) {
  const sc = APP.querySelector('.screen'); if (!sc) return;
  const { todayTotal: tt, todayCorrect: tc } = S.training;
  const progPct = tt > 0 ? Math.round(tc/tt*100) : 0;
  const multi = isMultiAnswer(q);

  sc.innerHTML = `
    <div>
      <div class="prog-row">
        <span style="font-size:13px;color:var(--hint)">Сегодня: ${tt} / верных: ${tc}</span>
        ${tt > 0 ? `<span style="font-size:13px;font-weight:700;color:var(--green)">${progPct}%</span>` : ''}
      </div>
      ${tt > 0 ? `<div class="prog-bar" style="margin-top:5px"><div class="prog-fill" style="width:${progPct}%"></div></div>` : ''}
    </div>

    <div class="q-card">
      <div class="q-meta">${esc(q.subtopic || q.topic)}</div>
      <div class="q-text">${esc(q.question)}</div>
      ${multi ? `<div style="font-size:12px;color:var(--hint);margin-top:6px">✏️ Выберите все верные ответы</div>` : ''}
    </div>

    <div class="answers">
      ${['A','B','C','D'].map(l => `
        <button class="ans-btn${multi?' multi':''}" id="t${l}" onclick="${multi?`toggleTraining('${l}')`:`submitTraining('${l}')`}">
          <div class="letter">${l}</div>
          <div>${esc(q.options[l])}</div>
        </button>
      `).join('')}
    </div>

    ${multi ? `<button class="btn btn-primary" id="t-check" onclick="submitTrainingMulti()" disabled style="opacity:.45">Проверить</button>` : ''}
    <div id="t-result"></div>
  `;
}

function toggleTraining(letter) {
  if (S.training.answered) return;
  const btn = document.getElementById('t' + letter); if (!btn) return;
  btn.classList.toggle('picked');
  haptic('sel');
  const anyPicked = ['A','B','C','D'].some(l => document.getElementById('t'+l)?.classList.contains('picked'));
  const chk = document.getElementById('t-check');
  if (chk) { chk.disabled = !anyPicked; chk.style.opacity = anyPicked ? '1' : '.45'; }
}

async function submitTrainingMulti() {
  if (S.training.answered) return;
  const chosen = ['A','B','C','D'].filter(l => document.getElementById('t'+l)?.classList.contains('picked'));
  if (!chosen.length) return;
  await submitTraining(chosen.join(','));
}

async function submitTraining(chosen) {
  if (S.training.answered) return;
  S.training.answered = true;
  const q = S.training.question;
  ['A','B','C','D'].forEach(l => document.getElementById('t'+l)?.classList.add('disabled'));
  const chk = document.getElementById('t-check');
  if (chk) { chk.disabled = true; chk.style.opacity = '.45'; }
  haptic('light');

  // Convert shuffled display letters back to original DB letters before sending
  let originalChosen = chosen;
  if (chosen && q._unmap) {
    originalChosen = chosen.split(',').map(l => q._unmap[l.trim()] || l).join(',');
  }

  try {
    const res = await api('/training/answer', { method:'POST', body:{ question_id:q.id, chosen_answer:originalChosen } });
    // Server returns correct_answer in original letter space → remap to shuffled display positions
    const correctSet = new Set(res.correct_answer.split(',').map(l => q._remap?.[l.trim()] || l));
    const chosenSet  = new Set(chosen.split(','));
    const ok = res.is_correct;

    ['A','B','C','D'].forEach(l => {
      const btn = document.getElementById('t'+l); if (!btn) return;
      if (correctSet.has(l)) btn.classList.add('correct');
      else if (chosenSet.has(l) && !correctSet.has(l)) btn.classList.add('wrong');
    });

    haptic(ok ? 'ok' : 'err');
    S.training.todayTotal   = res.today.total;
    S.training.todayCorrect = res.today.correct;
    if (!S.training.answeredIds.includes(q.id)) {
      S.training.answeredIds.push(q.id);
      _lsSet(`train_${S.training.topic}`, S.training.answeredIds.slice(-100));
    }

    S.training.history.push({ q, chosen, res, expl: null });
    if (S.training.history.length > 30) S.training.history.shift();
    const hPos = S.training.history.length - 1;

    const rArea = document.getElementById('t-result');
    if (rArea) {
      rArea.innerHTML = `
        <div class="result-badge ${ok ? 'ok' : 'bad'}">${ok ? '✅ Правильно!' : '❌ Неправильно'}</div>

        ${q.drug_name ? `
          <div class="drug-img-wrap" id="t-img">
            <div class="expl-loading"><div class="spinner sm"></div>Ищем изображение…</div>
          </div>` : ''}

        <div class="expl-loading" id="t-expl-load"><div class="spinner sm"></div>Генерируем объяснение…</div>
        <div id="t-expl"></div>

        <button class="btn btn-primary" onclick="showTrainingQ()">Следующий вопрос →</button>
        ${hPos > 0 ? `<button class="btn btn-secondary" onclick="showHistoryQ(${hPos - 1})">← Предыдущий вопрос</button>` : ''}
        <button class="btn btn-secondary" onclick="showTopicPick('training')">Сменить тему</button>
        <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>
      `;
      if (q.drug_name) loadImg(q.drug_name, 't-img');
      loadExplSaving(q.id, hPos, 't-expl-load', 't-expl');
    }
  } catch (_) { toast('Ошибка при отправке ответа'); }
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

async function loadExplSaving(qid, historyIdx, loadId, areaId) {
  try {
    const res = await api(`/explanation/${qid}`);
    if (S.training.history[historyIdx]) S.training.history[historyIdx].expl = res.text;
    document.getElementById(loadId)?.remove();
    const el = document.getElementById(areaId);
    if (el) el.innerHTML = `<div class="expl-box">${esc(res.text)}</div>`;
  } catch (_) {
    const el = document.getElementById(loadId);
    if (el) el.textContent = 'Объяснение временно недоступно.';
  }
}

function showHistoryQ(pos) {
  const h = S.training.history;
  if (pos < 0 || pos >= h.length) return;
  const { q, chosen, res } = h[pos];
  const multi = isMultiAnswer(q);
  // res.correct_answer is in original DB letters; remap to shuffled display positions
  const correctSet = new Set(res.correct_answer.split(',').map(l => q._remap?.[l.trim()] || l));
  const chosenSet  = new Set(chosen ? chosen.split(',') : []);
  const ok = res.is_correct;
  const isLast  = pos === h.length - 1;
  const isFirst = pos === 0;

  backBtn(true, () => showHistoryQ(pos + 1 < h.length ? pos + 1 : pos));

  page(hdr(`${S.training.topic} — история`, () => showHistoryQ(isLast ? pos : h.length - 1)), `
    <div style="text-align:center;font-size:12px;color:var(--hint);margin-bottom:10px">
      Вопрос ${pos + 1} из ${h.length} пройденных
    </div>

    <div class="q-card">
      <div class="q-meta">${esc(q.subtopic || q.topic)}</div>
      <div class="q-text">${esc(q.question)}</div>
      ${multi ? `<div style="font-size:12px;color:var(--hint);margin-top:6px">✏️ Несколько верных ответов</div>` : ''}
    </div>

    <div class="answers">
      ${['A','B','C','D'].map(l => {
        let cls = 'ans-btn disabled';
        if (correctSet.has(l)) cls += ' correct';
        else if (chosenSet.has(l)) cls += ' wrong';
        return `<button class="${cls}"><div class="letter">${l}</div><div>${esc(q.options[l])}</div></button>`;
      }).join('')}
    </div>

    <div class="result-badge ${ok ? 'ok' : 'bad'}">${ok ? '✅ Правильно!' : '❌ Неправильно'}</div>

    ${q.drug_name ? `<div class="drug-img-wrap" id="h-img"><div class="expl-loading"><div class="spinner sm"></div>Ищем изображение…</div></div>` : ''}
    <div class="expl-loading" id="h-expl-load"><div class="spinner sm"></div>Загружаем объяснение…</div>
    <div id="h-expl"></div>

    <div style="display:flex;gap:8px;margin-top:8px">
      ${!isFirst ? `<button class="btn btn-secondary" style="flex:1" onclick="showHistoryQ(${pos - 1})">← Назад</button>` : ''}
      ${!isLast  ? `<button class="btn btn-secondary" style="flex:1" onclick="showHistoryQ(${pos + 1})">Вперёд →</button>` : ''}
    </div>
    ${isLast ? `<button class="btn btn-primary" onclick="showTrainingQ()">Следующий вопрос →</button>` : ''}
    <button class="btn btn-secondary" onclick="showTopicPick('training')">Сменить тему</button>
    <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>
  `);

  if (h[pos].expl) {
    document.getElementById('h-expl-load')?.remove();
    const el = document.getElementById('h-expl');
    if (el) el.innerHTML = `<div class="expl-box">${esc(h[pos].expl)}</div>`;
  } else {
    loadExplSaving(q.id, pos, 'h-expl-load', 'h-expl');
  }
  if (q.drug_name) loadImg(q.drug_name, 'h-img');
}

async function loadImg(drug, containerId) {
  try {
    const res = await api(`/image?drug=${encodeURIComponent(drug)}`);
    const c = document.getElementById(containerId); if (!c) return;
    if (res.url) {
      c.innerHTML = `<img class="drug-img" src="${esc(res.url)}" alt="${esc(drug)}"
        onerror="this.closest('.drug-img-wrap')?.remove()">`;
    } else { c.remove(); }
  } catch (_) { document.getElementById(containerId)?.remove(); }
}

/* ══════════════════════════════════════════════════════════════════════
   EXAM SETUP
══════════════════════════════════════════════════════════════════════ */
function showExamSetup() {
  backBtn(true, showHome);
  const limits = [
    { l:'10 мин', s:600 }, { l:'20 мин', s:1200 },
    { l:'30 мин', s:1800 }, { l:'Без лимита', s:null },
  ];

  const topicBlock = S.exam.topic
    ? `<div style="display:flex;justify-content:space-between;align-items:center">
         <span style="font-weight:700">${esc(S.exam.topic)}</span>
         <button class="chip" onclick="showTopicPick('exam')">Изменить</button>
       </div>`
    : `<button class="btn btn-secondary" onclick="showTopicPick('exam')">Выбрать тему →</button>`;

  page(hdr('Настройки экзамена', () => showHome()), `
    <div class="card"><div class="opt-label">Тема</div>${topicBlock}</div>

    <div class="card">
      <div class="opt-label">Количество вопросов</div>
      <div class="chip-group">
        ${[10,20,30].map(n => `<button class="chip ${S.exam.count===n?'on':''}" id="cn${n}" onclick="setEC(${n})">${n}</button>`).join('')}
      </div>
    </div>

    <div class="card">
      <div class="opt-label">Лимит времени</div>
      <div class="chip-group" style="flex-direction:column;align-items:flex-start">
        ${limits.map(t => `<button class="chip ${S.exam.timeLimit===t.s?'on':''}" id="ct${t.s}" onclick="setET(${t.s})">${t.l}</button>`).join('')}
      </div>
    </div>

    <button class="btn btn-primary" onclick="startExam()" ${!S.exam.topic?'disabled style="opacity:.5"':''}>
      Начать экзамен →
    </button>
  `);
}

function setEC(n) {
  S.exam.count = n; haptic('sel');
  document.querySelectorAll('[id^="cn"]').forEach(e => e.classList.remove('on'));
  document.getElementById('cn'+n)?.classList.add('on');
}
function setET(s) {
  S.exam.timeLimit = s; haptic('sel');
  document.querySelectorAll('[id^="ct"]').forEach(e => e.classList.remove('on'));
  document.getElementById('ct'+s)?.classList.add('on');
}

/* ══════════════════════════════════════════════════════════════════════
   EXAM MODE
══════════════════════════════════════════════════════════════════════ */
async function startExam() {
  if (!S.exam.topic) { toast('Выберите тему!'); return; }
  setApp(`<div class="loading-screen"><div class="spinner"></div><p>Подготавливаем экзамен…</p></div>`);

  try {
    // Load previously seen question IDs so the server picks different ones
    const seenIds = _lsGet(`exam_${S.exam.topic}`);
    const res = await api('/exam/start', {
      method:'POST',
      body:{ topic:S.exam.topic, count:S.exam.count, time_limit_seconds:S.exam.timeLimit, exclude_ids: seenIds },
    });
    Object.assign(S.exam, {
      sessionId:res.session_id, questions:res.questions.map(shuffleQuestion),
      currentIndex:0, answers:{}, startTime:Date.now(),
      warnShown:false, finished:false,
    });
    clearInterval(S.exam.timerIv);
    if (S.exam.timeLimit) S.exam.timerIv = setInterval(tickTimer, 1000);
    showExamQ();
  } catch (_) {
    setApp(`<div class="screen">
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка запуска</div>
      <button class="btn btn-secondary" onclick="showExamSetup()">Назад</button>
    </div>`);
  }
}

function showExamQ() {
  if (S.exam.finished) return;
  const { questions, currentIndex, answers, timeLimit } = S.exam;
  const q = questions[currentIndex]; const total = questions.length;
  const pct = Math.round(currentIndex / total * 100);
  const multi = isMultiAnswer(q);
  const savedChosen = answers[q.id]?.chosen || '';
  const savedSet = new Set(savedChosen ? savedChosen.split(',') : []);

  backBtn(true, () => { if (confirm('Завершить экзамен досрочно?')) finishExam(); });

  page(`
    <div class="hdr">
      <div style="flex:1">
        <div class="prog-row">
          <span>Вопрос ${currentIndex+1} / ${total}</span>
          ${timeLimit
            ? `<span class="timer" id="etimer">⏱ --:--</span>`
            : `<span class="timer" id="etimer" style="color:var(--hint)">⏱ 00:00</span>`}
        </div>
        <div class="prog-bar" style="margin-top:4px"><div class="prog-fill" style="width:${pct}%"></div></div>
      </div>
    </div>
  `, `
    <div class="q-card">
      <div class="q-meta">${esc(q.subtopic || q.topic)}</div>
      <div class="q-text">${esc(q.question)}</div>
      ${multi ? `<div style="font-size:12px;color:var(--hint);margin-top:6px">✏️ Выберите все верные ответы</div>` : ''}
    </div>

    <div class="answers">
      ${['A','B','C','D'].map(l => `
        <button class="ans-btn${multi?' multi':''} ${savedSet.has(l)?'picked':''}" id="eb${l}" onclick="${multi?`toggleExamAns('${l}')`:`pickExamAns('${l}')`}">
          <div class="letter">${l}</div><div>${esc(q.options[l])}</div>
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
      Отвечено: ${Object.keys(answers).length} / ${total}
    </div>
  `);
  tickTimer();
}

function pickExamAns(l) {
  if (S.exam.finished) return;
  const q = S.exam.questions[S.exam.currentIndex];
  S.exam.answers[q.id] = { chosen:l, is_skipped:false };
  document.querySelectorAll('[id^="eb"]').forEach(b => b.classList.remove('picked'));
  document.getElementById('eb'+l)?.classList.add('picked');
  haptic('sel');
}

function toggleExamAns(l) {
  if (S.exam.finished) return;
  const q = S.exam.questions[S.exam.currentIndex];
  const btn = document.getElementById('eb' + l); if (!btn) return;
  btn.classList.toggle('picked');
  const picked = ['A','B','C','D'].filter(x => document.getElementById('eb'+x)?.classList.contains('picked'));
  S.exam.answers[q.id] = { chosen: picked.join(',') || null, is_skipped: false };
  haptic('sel');
}
function skipExamQ() {
  const q = S.exam.questions[S.exam.currentIndex];
  S.exam.answers[q.id] = { chosen:null, is_skipped:true };
  nextExamQ();
}
function nextExamQ() {
  const { currentIndex, questions } = S.exam;
  if (currentIndex < questions.length-1) { S.exam.currentIndex++; showExamQ(); }
  else finishExam();
}

function tickTimer() {
  const el = document.getElementById('etimer'); if (!el) return;
  const elapsed = Math.floor((Date.now() - S.exam.startTime) / 1000);
  const limit = S.exam.timeLimit;
  if (limit) {
    const rem = limit - elapsed;
    if (rem <= 0) {
      clearInterval(S.exam.timerIv); el.textContent = '⏱ 00:00'; el.className = 'timer warn';
      toast('⏰ Время вышло!'); haptic('warn');
      setTimeout(finishExam, 1500); return;
    }
    el.textContent = `⏱ ${fmt(rem)}`;
    if (rem <= 120 && !S.exam.warnShown) {
      S.exam.warnShown = true; el.className = 'timer warn';
      toast('⚠️ Осталось 2 минуты!'); haptic('warn');
    }
  } else { el.textContent = `⏱ ${fmt(elapsed)}`; }
}

function _calcLocalResult(elapsed) {
  const questions = S.exam.questions;
  let correct = 0;
  const details = questions.map(q => {
    const ans = S.exam.answers[q.id];
    const chosen = ans?.chosen ?? null;
    const isSkipped = ans?.is_skipped ?? false;
    let isCorrect = false;
    if (!isSkipped && chosen) {
      const chosenSet  = new Set(chosen.split(',').map(s => s.trim()));
      const correctSet = new Set(q.correct_answer.split(',').map(s => s.trim()));
      isCorrect = chosenSet.size === correctSet.size && [...chosenSet].every(l => correctSet.has(l));
    }
    if (isCorrect) correct++;
    return {
      question_id: q.id, question: q.question, options: q.options,
      correct_answer: q.correct_answer, chosen_answer: chosen,
      is_correct: isCorrect, is_skipped: isSkipped, drug_name: q.drug_name,
    };
  });
  const total = questions.length;
  return { session_id: S.exam.sessionId, correct, total,
    percent: total > 0 ? Math.round(correct / total * 100) : 0,
    elapsed_seconds: elapsed, details };
}

async function finishExam() {
  if (S.exam.finished) return;
  S.exam.finished = true; clearInterval(S.exam.timerIv); backBtn(false);
  setApp(`<div class="loading-screen"><div class="spinner"></div><p>Подводим итоги…</p></div>`);

  const elapsed = Math.floor((Date.now() - S.exam.startTime) / 1000);

  // Save question IDs so next exam avoids repeating them
  const seenKey = `exam_${S.exam.topic}`;
  const prevSeen = _lsGet(seenKey);
  const nowSeen = S.exam.questions.map(q => q.id);
  _lsSet(seenKey, [...new Set([...prevSeen, ...nowSeen])].slice(-200));

  // Convert shuffled letters back to original DB letters before sending to server
  const answers = S.exam.questions.map(q => {
    const chosen   = S.exam.answers[q.id]?.chosen ?? null;
    const isSkipped = S.exam.answers[q.id]?.is_skipped ?? false;
    let originalChosen = chosen;
    if (chosen && q._unmap) {
      originalChosen = chosen.split(',').map(l => q._unmap[l.trim()] || l).join(',');
    }
    return { question_id: q.id, chosen_answer: originalChosen, is_skipped: isSkipped };
  });

  try {
    const result = await api('/exam/finish', {
      method:'POST', body:{ session_id:S.exam.sessionId, answers, elapsed_seconds:elapsed },
    });
    showExamResult(result);
  } catch (_) {
    // Server unavailable (e.g. Render sleep) — show result calculated locally
    showExamResult(_calcLocalResult(elapsed));
  }
}

function showExamResult(result) {
  backBtn(false);
  const pct = result.percent; const g = grade(pct);
  const timeStr = fmt(result.elapsed_seconds);
  const limitStr = S.exam.timeLimit ? ` из ${fmt(S.exam.timeLimit)}` : '';
  const wrong = result.details.filter(d => !d.is_correct && !d.is_skipped);
  const skipped = result.details.filter(d => d.is_skipped);
  const passed = pct >= 60;
  const quote = getQuote(passed);

  if (pct >= 75) confetti();

  page(hdr('Результат экзамена'), `
    <div class="card result-hero">
      <div class="result-emoji">${g.e}</div>

      <div class="result-circle" style="--pct:${pct*3.6}deg" id="rcircle">
        <div class="result-pct-text" id="rpct">0%</div>
      </div>

      <div class="result-grade">${g.t}</div>
      <div class="result-sub">${result.correct} из ${result.total} правильно</div>
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

    <div class="card quote-card ${passed ? 'quote-pass' : 'quote-fail'}">
      <div class="quote-label">${passed ? '🎓 Мудрость на сегодня' : '💪 Слова поддержки'}</div>
      <div class="quote-text">${esc(quote.text)}</div>
      <div class="quote-author">— ${esc(quote.author)}</div>
    </div>

    ${wrong.length > 0 ? `
      <div class="section-title">Разбор ошибок (${wrong.length})</div>
      ${wrong.map((d,i) => {
        const corrLetters = d.correct_answer ? d.correct_answer.split(',') : [];
        const corrText = corrLetters.map(l => `${l}) ${d.options[l]}`).join(', ');
        const chosenLetters = d.chosen_answer ? d.chosen_answer.split(',') : [];
        const chosenText = chosenLetters.map(l => `${l}) ${d.options[l]}`).join(', ');
        return `
        <div class="err-item">
          <div class="err-q">${esc(d.question)}</div>
          <div>
            ${d.chosen_answer ? `<div class="err-wrong">❌ ${esc(chosenText)}</div>` : ''}
            <div class="err-corr">✅ ${esc(corrText)}</div>
          </div>
          <button class="chip" onclick="toggleExpl('xe${i}','${d.question_id}',this)">Объяснение</button>
          <div id="xe${i}" style="display:none"></div>
        </div>`;
      }).join('')}
    ` : ''}

    <button class="btn btn-primary" onclick="showHome()">На главную</button>
    <button class="btn btn-secondary" onclick="S.exam.sessionId=null;S.exam.questions=[];S.exam.answers={};S.exam.finished=false;showExamSetup()">Повторить</button>
  `);

  /* Animate percentage counter */
  let cur = 0;
  const target = pct;
  const step = () => {
    cur = Math.min(cur + Math.ceil(target / 30), target);
    const el = document.getElementById('rpct');
    if (el) el.textContent = cur + '%';
    if (cur < target) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

async function toggleExpl(elId, qid, btn) {
  const el = document.getElementById(elId); if (!el) return;
  if (el.style.display !== 'none') { el.style.display = 'none'; btn.textContent = 'Объяснение'; return; }
  el.style.display = 'block'; btn.textContent = 'Скрыть';
  if (el.innerHTML) return;
  el.innerHTML = `<div class="expl-loading"><div class="spinner sm"></div>Загружаем…</div>`;
  try {
    const res = await api(`/explanation/${qid}`);
    el.innerHTML = `<div class="expl-box">${esc(res.text)}</div>`;
  } catch (_) { el.innerHTML = `<div style="color:var(--hint);font-size:13px">Объяснение недоступно</div>`; }
}

/* ══════════════════════════════════════════════════════════════════════
   STATS
══════════════════════════════════════════════════════════════════════ */
async function showStats() {
  backBtn(true, showHome);
  page(hdr('Статистика', () => showHome()), `
    <div class="loading-screen" style="min-height:200px"><div class="spinner"></div></div>
  `);

  try {
    const stats = await api('/stats');
    const today = stats.today || {}; const topics = stats.topics || [];
    const accTotal = stats.total || 0; const accCorr = stats.correct || 0;
    const accPct = accTotal > 0 ? Math.round(accCorr/accTotal*100) : 0;

    const sc = APP.querySelector('.screen'); if (!sc) return;
    sc.innerHTML = `
      <div class="hero" style="padding:14px 16px">
        ${avatarHtml(44)}
        <div class="hero-info">
          <div class="hero-greet">Моя статистика</div>
          <div class="hero-name" style="font-size:17px">${esc(DISPLAY)}</div>
        </div>
      </div>

      <div class="stats-row">
        <div class="stat"><div class="stat-val">${accTotal}</div><div class="stat-lbl">Всего</div></div>
        <div class="stat"><div class="stat-val">${accPct}%</div><div class="stat-lbl">Точность</div></div>
        <div class="stat"><div class="stat-val">${stats.exams_completed||0}</div><div class="stat-lbl">Экзаменов</div></div>
      </div>

      <div class="card">
        <div class="opt-label" style="margin-bottom:10px">Сегодня</div>
        <div class="kv-list">
          <div class="kv-row"><span>Ответов</span><span class="kv-val">${today.total||0}</span></div>
          <div class="kv-row"><span>Правильных</span><span class="kv-val kv-green">${today.correct||0}</span></div>
          ${today.total > 0 ? `<div class="kv-row"><span>Точность</span><span class="kv-val">${Math.round((today.correct||0)/(today.total)*100)}%</span></div>` : ''}
        </div>
      </div>

      ${topics.length > 0 ? `
        <div class="card">
          <div class="opt-label" style="margin-bottom:14px">По темам</div>
          ${topics.map(t => {
            const p = t.total > 0 ? Math.round(t.correct/t.total*100) : 0;
            const barColor = p >= 75 ? 'var(--green)' : p >= 50 ? 'var(--orange)' : 'var(--red)';
            return `
              <div class="topic-bar-wrap">
                <div class="topic-bar-head">
                  <span>${esc(t.topic)}</span>
                  <span style="font-weight:700;color:${barColor}">${p}%</span>
                </div>
                <div class="prog-bar"><div class="prog-fill" style="width:${p}%;background:${barColor}"></div></div>
                <div style="font-size:12px;color:var(--hint);margin-top:3px">${t.correct}/${t.total} правильно</div>
              </div>
            `;
          }).join('')}
        </div>
      ` : `<div class="card" style="text-align:center;color:var(--hint);padding:20px">Начни тренировку, чтобы увидеть статистику!</div>`}

      <button class="btn btn-secondary" onclick="showHome()">На главную</button>
    `;
  } catch (_) {
    const sc = APP.querySelector('.screen');
    if (sc) sc.innerHTML = `
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки</div>
      <button class="btn btn-secondary" onclick="showHome()">На главную</button>
    `;
  }
}

/* ══════════════════════════════════════════════════════════════════════
   CLASSIFICATIONS
══════════════════════════════════════════════════════════════════════ */

async function showClassificationPick() {
  backBtn(true, showHome);
  page(hdr('Классификации', () => showHome()), `
    <div style="font-size:13px;color:var(--hint);margin-bottom:2px">
      Выберите раздел для изучения
    </div>
    <div class="topic-list" id="cls-list">
      <div class="loading-screen" style="min-height:200px"><div class="spinner"></div></div>
    </div>
  `);

  try {
    const sections = await api('/cls/sections');
    const list = document.getElementById('cls-list');
    if (!list) return;
    list.innerHTML = sections.map(function(s) {
      const col = s.color || '#95A5A6';
      const safeSection = s.section.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
      const sub = s.topic_count + ' групп · Тест ' + s.mcq_count + ' · Сорт. ' + s.sort_count;
      return '<button class="cls-topic-item" onclick="showClsSectionTopics(\'' + safeSection + '\')">'
        + '<div class="cls-topic-icon" style="background:' + col + '22;border:1.5px solid ' + col + '44">' + s.icon + '</div>'
        + '<div class="cls-topic-info">'
        + '<div class="cls-topic-name">' + esc(s.section) + '</div>'
        + '<div style="font-size:12px;color:var(--hint);margin-top:2px">' + sub + '</div>'
        + '</div>'
        + '<div class="topic-arr">›</div>'
        + '</button>';
    }).join('');
  } catch (err) {
    const l = document.getElementById('cls-list');
    if (l) l.innerHTML = '<div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки</div>'
      + '<button class="btn btn-secondary" onclick="showClassificationPick()">Повторить</button>';
  }
}

async function showClsSectionTopics(section) {
  haptic('sel');
  S.cls.section = section;
  backBtn(true, showClassificationPick);
  page(hdr(section, () => showClassificationPick()), `
    <div style="font-size:13px;color:var(--hint);margin-bottom:2px">
      Выберите группу препаратов для изучения
    </div>
    <div class="topic-list" id="cls-list">
      <div class="loading-screen" style="min-height:200px"><div class="spinner"></div></div>
    </div>
  `);

  try {
    const topics = await api('/cls/topics?section=' + encodeURIComponent(section));
    const list = document.getElementById('cls-list');
    if (!list) return;
    list.innerHTML = topics.map(function(t) {
      const col = t.color || '#95A5A6';
      let badges = '';
      if (t.mcq_count > 0)  badges += '<span class="cls-badge" style="background:' + col + '22;color:' + col + '">Тест ' + t.mcq_count + '</span> ';
      if (t.sort_count > 0) badges += '<span class="cls-badge" style="background:rgba(0,131,143,.12);color:#006064">Сорт. ' + t.sort_count + '</span>';
      const safeTopic = t.topic.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
      return '<button class="cls-topic-item" onclick="showClsModeSelect(\'' + safeTopic + '\',' + t.mcq_count + ',' + t.sort_count + ')">'
        + '<div class="cls-topic-icon" style="background:' + col + '22;border:1.5px solid ' + col + '44">' + t.icon + '</div>'
        + '<div class="cls-topic-info">'
        + '<div class="cls-topic-name">' + esc(t.topic) + '</div>'
        + '<div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:4px">' + badges + '</div>'
        + '</div>'
        + '<div class="topic-arr">›</div>'
        + '</button>';
    }).join('');
  } catch (err) {
    const l = document.getElementById('cls-list');
    if (l) l.innerHTML = '<div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки</div>'
      + '<button class="btn btn-secondary" onclick="showClsSectionTopics(S.cls.section)">Повторить</button>';
  }
}

function showClsModeSelect(topic, mcqCount, sortCount) {
  haptic('sel');
  S.cls.topic = topic;
  S.cls.mcqCount  = mcqCount;
  S.cls.sortCount = sortCount;
  if (sortCount === 0) { S.cls.mode = 'mcq';     S.cls.answeredIds = []; startClsExercise(); return; }
  if (mcqCount  === 0) { S.cls.mode = 'sorting'; S.cls.answeredIds = []; startClsExercise(); return; }

  backBtn(true, () => showClsSectionTopics(S.cls.section));
  page(hdr(topic, () => showClsSectionTopics(S.cls.section)), `
    <div style="font-size:14px;color:var(--hint);margin-bottom:4px">Выберите режим занятия</div>

    <button class="menu-card full" style="background:linear-gradient(135deg,#1B4332,#2D6A4F,#40916C)" onclick="pickClsMode('mcq')">
      <div class="menu-icon-bubble" style="font-size:28px">❓</div>
      <div class="menu-body">
        <div class="menu-title">Тест (4 варианта)</div>
        <div class="menu-sub">Определи группу, поколение или механизм — выбери из 4 ответов</div>
      </div>
    </button>

    <button class="menu-card full" style="background:linear-gradient(135deg,#006064,#00838F,#26C6DA)" onclick="pickClsMode('sorting')">
      <div class="menu-icon-bubble" style="font-size:28px">🗂️</div>
      <div class="menu-body">
        <div class="menu-title">Сортировка</div>
        <div class="menu-sub">Отнеси каждый препарат к нужной категории — по одному</div>
      </div>
    </button>
  `);
}

function pickClsMode(mode) {
  haptic('sel');
  S.cls.mode = mode;
  S.cls.answeredIds = [];
  startClsExercise();
}

function _clsBack() {
  showClsModeSelect(S.cls.topic, S.cls.mcqCount || 1, S.cls.sortCount || 1);
}

async function startClsExercise() {
  if (S.cls.mode === 'mcq') await showClsMCQ();
  else await showClsSort();
}

/* ─── MCQ mode ─────────────────────────────────────────────────────── */
async function showClsMCQ() {
  backBtn(true, _clsBack);
  S.cls.answered = false;

  page(hdr(S.cls.topic, _clsBack), `
    <div class="loading-screen" style="min-height:200px"><div class="spinner"></div><p>Загружаем вопрос…</p></div>
  `);

  try {
    const excl = S.cls.answeredIds.slice(-30).join(',');
    const q = await api(`/cls/question?topic=${encodeURIComponent(S.cls.topic)}&type=mcq&exclude=${excl}`);

    if (!q || !q.id) {
      APP.querySelector('.screen').innerHTML = `
        <div style="text-align:center;padding:40px 0">
          <div style="font-size:52px">🎉</div>
          <div style="font-size:18px;font-weight:800;margin-top:12px">Все вопросы пройдены!</div>
        </div>
        <button class="btn btn-primary" onclick="S.cls.answeredIds=[];showClsMCQ()">Начать заново</button>
        <button class="btn btn-secondary" onclick="showClsSectionTopics(S.cls.section)">Другая тема</button>
        <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>`;
      return;
    }

    S.cls.exercise = shuffleQuestion(q);
    renderClsMCQ(S.cls.exercise);
  } catch (_) {
    const sc = APP.querySelector('.screen');
    if (sc) sc.innerHTML = `
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки</div>
      <button class="btn btn-secondary" onclick="showClsMCQ()">Повторить</button>`;
  }
}

function renderClsMCQ(q) {
  const sc = APP.querySelector('.screen'); if (!sc) return;
  sc.innerHTML = `
    <div class="q-card">
      <div class="q-meta">${esc(q.category || q.topic)}</div>
      <div class="q-text">${esc(q.question)}</div>
    </div>

    <div class="answers">
      ${['A','B','C','D'].map(l => `
        <button class="ans-btn" id="c${l}" onclick="submitClsMCQ('${l}')">
          <div class="letter">${l}</div>
          <div>${esc(q.options[l])}</div>
        </button>`).join('')}
    </div>

    <div id="c-result"></div>
  `;
}

function submitClsMCQ(chosen) {
  if (S.cls.answered) return;
  S.cls.answered = true;
  const q = S.cls.exercise;
  ['A','B','C','D'].forEach(l => document.getElementById('c'+l)?.classList.add('disabled'));

  // After shuffleQuestion(), q.correct_answer is already in shuffled display-letter space,
  // and 'chosen' is also a display letter — compare directly.
  const ok = chosen === q.correct_answer;
  haptic(ok ? 'ok' : 'err');
  document.getElementById('c' + chosen)?.classList.add(ok ? 'correct' : 'wrong');
  if (!ok) document.getElementById('c' + q.correct_answer)?.classList.add('correct');

  if (!S.cls.answeredIds.includes(q.id)) S.cls.answeredIds.push(q.id);

  const rArea = document.getElementById('c-result');
  if (!rArea) return;
  let html = '<div class="result-badge ' + (ok ? 'ok' : 'bad') + '">' + (ok ? '✅ Правильно!' : '❌ Неправильно') + '</div>';
  if (q.explanation) html += '<div class="expl-box">' + esc(q.explanation) + '</div>';
  html += '<button class="btn btn-primary" onclick="showClsMCQ()">Следующий →</button>';
  if (S.cls.sortCount > 0) html += '<button class="btn btn-secondary" onclick="pickClsMode(\'sorting\')">Попробовать сортировку</button>';
  html += '<button class="btn btn-secondary" onclick="showClsSectionTopics(S.cls.section)">Другая тема</button>';
  rArea.innerHTML = html;
}

/* ─── Sorting mode ──────────────────────────────────────────────────── */
async function showClsSort() {
  backBtn(true, _clsBack);

  page(hdr(S.cls.topic, _clsBack), `
    <div class="loading-screen" style="min-height:200px"><div class="spinner"></div><p>Загружаем упражнение…</p></div>
  `);

  try {
    const excl = S.cls.answeredIds.slice(-20).join(',');
    const ex = await api(`/cls/question?topic=${encodeURIComponent(S.cls.topic)}&type=sorting&exclude=${excl}`);

    if (!ex || !ex.id) {
      APP.querySelector('.screen').innerHTML = `
        <div style="text-align:center;padding:40px 0">
          <div style="font-size:52px">🎉</div>
          <div style="font-size:18px;font-weight:800;margin-top:12px">Все упражнения пройдены!</div>
        </div>
        <button class="btn btn-primary" onclick="S.cls.answeredIds=[];showClsSort()">Начать заново</button>
        <button class="btn btn-secondary" onclick="showClsSectionTopics(S.cls.section)">Другая тема</button>
        <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>`;
      return;
    }

    if (!S.cls.answeredIds.includes(ex.id)) S.cls.answeredIds.push(ex.id);
    S.cls.exercise  = ex;
    S.cls.sortItems = ex.items ? [...ex.items] : [];
    S.cls.sortIndex = 0;
    S.cls.sortAnswers = {};

    renderClsSortItem();
  } catch (_) {
    const sc = APP.querySelector('.screen');
    if (sc) sc.innerHTML = `
      <div style="text-align:center;color:var(--hint);padding:40px 0">Ошибка загрузки</div>
      <button class="btn btn-secondary" onclick="showClsSort()">Повторить</button>`;
  }
}

function renderClsSortItem() {
  const sc = APP.querySelector('.screen'); if (!sc) return;
  const { exercise: ex, sortItems, sortIndex } = S.cls;
  if (sortIndex >= sortItems.length) { showClsSortResult(); return; }

  const item = sortItems[sortIndex];
  const progress = `${sortIndex + 1} / ${sortItems.length}`;

  sc.innerHTML = `
    <div style="font-size:12px;color:var(--hint);text-align:center">${esc(ex.category || ex.topic)}</div>

    <div class="drug-card">
      <div class="drug-card-name">${esc(item.name)}</div>
      <div class="drug-card-hint">${esc(ex.instruction)}</div>
      <div class="drug-card-counter">${progress}</div>
    </div>

    <div class="prog-bar"><div class="prog-fill" style="width:${Math.round(sortIndex/sortItems.length*100)}%"></div></div>

    <div class="sort-cats">
      ${ex.categories.map((cat, ci) => `
        <button class="sort-cat-btn" id="scat${ci}" onclick="pickSortCat('${cat.replace(/'/g,"\\'")}',${ci})">
          ${esc(cat)}
        </button>`).join('')}
    </div>
  `;
}

function pickSortCat(chosen, btnIdx) {
  const { exercise: ex, sortItems, sortIndex } = S.cls;
  const item = sortItems[sortIndex];
  const correct = item.category;
  const ok = chosen === correct;

  haptic(ok ? 'ok' : 'err');

  // Disable all buttons
  ex.categories.forEach((_, ci) => {
    const btn = document.getElementById('scat' + ci);
    if (btn) btn.disabled = true;
  });

  // Mark chosen and correct
  const chosenBtn = document.getElementById('scat' + btnIdx);
  if (chosenBtn) chosenBtn.classList.add(ok ? 'correct' : 'wrong');

  if (!ok) {
    const correctIdx = ex.categories.indexOf(correct);
    const correctBtn = document.getElementById('scat' + correctIdx);
    if (correctBtn) correctBtn.classList.add('correct');
  }

  S.cls.sortAnswers[item.name] = { chosen, correct, ok };

  setTimeout(() => {
    S.cls.sortIndex++;
    renderClsSortItem();
  }, ok ? 600 : 1200);
}

function showClsSortResult() {
  const sc = APP.querySelector('.screen'); if (!sc) return;
  const { exercise: ex, sortAnswers } = S.cls;
  const entries = Object.entries(sortAnswers);
  const correct = entries.filter(([, v]) => v.ok).length;
  const pct = entries.length > 0 ? Math.round(correct / entries.length * 100) : 0;
  const g = grade(pct);

  if (pct >= 80) confetti();
  haptic(pct >= 80 ? 'ok' : 'warn');

  sc.innerHTML = `
    <div class="card result-hero">
      <div class="result-emoji">${g.e}</div>
      <div class="result-circle" style="--pct:${pct * 3.6}deg">
        <div class="result-pct-text">${pct}%</div>
      </div>
      <div class="result-grade">${g.t}</div>
      <div class="result-sub">${correct} из ${entries.length} препаратов распределено верно</div>
    </div>

    <div class="section-title">Разбор</div>
    <div style="display:flex;flex-direction:column;gap:7px">
      ${entries.map(([name, v]) => `
        <div class="sort-result-item ${v.ok ? 'sr-ok' : 'sr-bad'}">
          <div>
            <div class="sr-name">${v.ok ? '✅' : '❌'} ${esc(name)}</div>
            <div class="sr-cat">${v.ok ? esc(v.correct) : `Вы: ${esc(v.chosen)} → Верно: ${esc(v.correct)}`}</div>
          </div>
        </div>`).join('')}
    </div>

    <button class="btn btn-primary" onclick="showClsSort()">Ещё упражнение →</button>
    <button class="btn btn-secondary" onclick="pickClsMode('mcq')">Попробовать тест</button>
    <button class="btn btn-secondary" onclick="showClsSectionTopics(S.cls.section)">Другая тема</button>
    <button class="btn btn-secondary" onclick="showHome()">Главное меню</button>
  `;
}

/* ══════════════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════════════ */
(async function init() {
  try {
    await api('/topics');
    showHome();
  } catch (_) {
    setApp(`
      <div class="screen" style="align-items:center;justify-content:center;min-height:100vh;text-align:center">
        <div style="font-size:52px">⚠️</div>
        <div style="font-size:18px;font-weight:800;margin-top:12px">Ошибка подключения</div>
        <div style="color:var(--hint);margin-top:8px;font-size:14px">
          Откройте приложение через Telegram<br>или проверьте соединение с сервером
        </div>
        <button class="btn btn-secondary" style="margin-top:20px" onclick="location.reload()">Перезагрузить</button>
      </div>
    `);
  }
})();
