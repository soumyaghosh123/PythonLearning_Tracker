"""Writes dashboard.html (your progress) and plan.html (the full learning plan).

The pages are plain HTML files. Python embeds the data as JSON and a little
JavaScript in the page draws the cards, roadmap and charts.
"""

import json

from settings import DASHBOARD_PATH, PLAN_PATH

# Shared look for both pages: colours are defined once, with a dark-mode version.
STYLE = """
  :root {
    --bg: #f5f7fb; --card: #ffffff; --text: #1d2433; --muted: #6b7385;
    --border: #e3e7ef; --accent: #3572a5; --accent2: #f2c94c; --aggr: #c0392b;
    --green: #2e9e5b; --yellow: #d9a400; --red: #d64545; --track: #e9edf4;
    --red-bg: #fdecec; --green-bg: #e8f6ee;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #12151c; --card: #1b2029; --text: #e6e9ef; --muted: #9aa3b5;
      --border: #2a3140; --accent: #5b9bd5; --aggr: #e8705f;
      --green: #4cc27f; --yellow: #f0c040; --red: #f06b6b; --track: #2a3140;
      --red-bg: #3a2024; --green-bg: #1d3328;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 "Segoe UI", system-ui, sans-serif; }
  a { color: var(--accent); }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }
  h1 { margin: 0; font-size: 26px; }
  h2 { margin: 0 0 14px; font-size: 16px; }
  .muted { color: var(--muted); font-size: 13px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }
  .mb { margin-bottom: 16px; }
  .pill { font-size: 13px; padding: 4px 12px; border-radius: 999px; background: var(--card); border: 1px solid var(--border); white-space: nowrap; }
  .pill.plan { background: var(--accent); color: #fff; border-color: var(--accent); }
  .pill.plan.aggressive { background: var(--aggr); border-color: var(--aggr); }
  .bar { height: 10px; background: var(--track); border-radius: 6px; overflow: hidden; }
  .bar > span { display: block; height: 100%; background: var(--accent); border-radius: 6px; }
  .bar > span.done { background: var(--green); }
  .bar > span.late { background: var(--red); }
"""

DASHBOARD_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Python Learning Tracker</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
__STYLE__
  header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
  .meta { display: flex; gap: 8px; flex-wrap: wrap; }
  .grid { display: grid; gap: 16px; margin-bottom: 16px; }
  .kpis { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
  .two { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
  .kpi .label { color: var(--muted); font-size: 13px; }
  .kpi .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
  .kpi .sub { color: var(--muted); font-size: 13px; }
  .banner { border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; border: 1px solid; }
  .banner.bad { background: var(--red-bg); border-color: var(--red); }
  .banner.good { background: var(--green-bg); border-color: var(--green); }
  .banner.info { background: var(--card); border-color: var(--border); }
  .target { margin-bottom: 14px; } .target:last-child { margin-bottom: 0; }
  .target-head { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 4px; }
  .roadmap { display: flex; flex-direction: column; gap: 8px; }
  .lvl-row { display: grid; grid-template-columns: 34px 1fr 120px 150px 130px; gap: 12px; align-items: center;
             padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; }
  .lvl-row.current { border: 2px solid var(--accent); }
  .lvl-row.overdue { border: 2px solid var(--red); background: var(--red-bg); }
  .lvl-row.done { background: var(--green-bg); border-color: transparent; }
  .num { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 13px; background: var(--track); }
  .done .num { background: var(--green); color: #fff; }
  .current .num { background: var(--accent); color: #fff; }
  .overdue .num { background: var(--red); color: #fff; }
  .lvl-name { font-weight: 600; }
  .lvl-name small { display: block; font-weight: 400; color: var(--muted); font-size: 12px; }
  .status { font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; text-align: center; white-space: nowrap; }
  .s-done { background: var(--green); color: #fff; } .s-overdue { background: var(--red); color: #fff; }
  .s-current { background: var(--accent); color: #fff; } .s-upcoming { background: var(--track); color: var(--muted); }
  .chart-box { position: relative; height: 230px; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { padding: 6px 12px; border-radius: 999px; font-size: 13px; border: 1px solid var(--border); }
  .chip.on { background: var(--green); color: #fff; border-color: var(--green); }
  .chip.off { color: var(--muted); border-style: dashed; }
  ul.links { margin: 6px 0 0; padding-left: 18px; font-size: 14px; }
  .tip { margin-top: 14px; font-size: 14px; background: var(--track); border-radius: 8px; padding: 10px 12px; }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; }
  .ok { color: var(--green); font-weight: 600; } .err { color: var(--red); font-weight: 600; }
  .lv { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; color: #fff; }
  .lv.Beginner { background: var(--green); } .lv.Intermediate { background: var(--yellow); color: #3a2e00; } .lv.Advanced { background: var(--red); }
  .empty { color: var(--muted); font-size: 14px; padding: 12px 0; }
  @media (max-width: 760px) {
    .lvl-row { grid-template-columns: 34px 1fr; }
    .lvl-row > :nth-child(n+3) { grid-column: 2; justify-self: start; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1 id="title">🐍 My Python Learning Tracker</h1>
    <div class="meta" id="meta"></div>
  </header>
  <div id="banner"></div>
  <section class="grid kpis" id="kpis"></section>

  <section class="card mb">
    <h2>🗺️ Learning roadmap: Beginner → Advanced <a class="muted" href="plan.html" style="font-weight:400;margin-left:8px">see full plan →</a></h2>
    <div class="roadmap" id="roadmap"></div>
  </section>

  <section class="grid two">
    <div class="card" id="currentCard"></div>
    <div class="card"><h2>🎯 Targets</h2><div id="targets"></div></div>
  </section>

  <section class="grid two">
    <div class="card"><h2>📈 Plan vs actual (levels completed)</h2><div class="chart-box"><canvas id="planChart"></canvas></div></div>
    <div class="card"><h2>📊 Daily runs (last 14 days)</h2><div class="chart-box"><canvas id="runsChart"></canvas></div></div>
  </section>

  <section class="grid two">
    <div class="card"><h2>🐞 Most common errors (last 30 days)</h2><div id="errors"></div></div>
    <div class="card"><h2>📂 Recent runs</h2><div class="table-wrap" id="recent"></div></div>
  </section>

  <p class="muted" id="notrun"></p>
  <p class="muted" id="footer"></p>
</div>

<script>
const R = __DATA__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (iso, year) => new Date(iso.slice(0, 10) + 'T00:00').toLocaleDateString('en-GB',
  year ? { day: 'numeric', month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' });
const pct = (a, b) => b ? Math.min(100, Math.round(a / b * 100)) : 0;
const S = R.stats, P = R.plan, cur = R.current_level;
const started = R.day_number >= 1;

if (R.learner) $('title').textContent = `🐍 ${R.learner}'s Python Learning Tracker`;
$('meta').innerHTML = `
  <span class="pill plan ${R.plan_key}">${P.icon} ${P.label} plan · ${R.total_days} days</span>
  <span class="pill">📅 ${started ? `Started ${fmt(R.start_date, 1)} · Day ${R.day_number}` : `Starts ${fmt(R.start_date, 1)}`}</span>
  <span class="pill">🏁 Target finish ${fmt(R.planned_finish, 1)}</span>`;

if (!started) {
  $('banner').innerHTML = `<div class="banner info">⏳ Your plan starts on <b>${fmt(R.start_date, 1)}</b>. Runs before that date are not counted.</div>`;
} else if (!cur) {
  $('banner').innerHTML = `<div class="banner good">🎉 <b>All 9 levels complete!</b> You've finished the Python learning path.</div>`;
} else if (cur.status === 'overdue') {
  const missing = cur.topics.filter(t => !t.done).map(t => `<b>${esc(t.name)}</b>`).join(', ');
  $('banner').innerHTML = `<div class="banner bad">⚠️ <b>Stuck alert:</b> Level ${cur.id} "${esc(cur.name)}" was due on <b>${fmt(cur.due)}</b>
    and is now <b>${cur.overdue_days} day${cur.overdue_days === 1 ? '' : 's'} overdue</b>. Still to do: ${missing}.</div>`;
}

const kpi = (label, value, sub, color) => `<div class="card kpi"><div class="label">${label}</div>
  <div class="value"${color ? ` style="color:var(${color})"` : ''}>${value}</div><div class="sub">${sub}</div></div>`;
const rate = S.runs_week ? Math.round(S.success_week / S.runs_week * 100) : 0;
$('kpis').innerHTML = [
  kpi('🎓 Current level', cur ? `${cur.id} / 9` : '9 / 9', cur ? esc(cur.name) : 'Complete'),
  kpi('📅 Schedule', R.days_behind ? `−${R.days_behind} days` : 'On track', R.days_behind ? 'Behind plan' : `Finish ${fmt(R.expected_finish)}`, R.days_behind ? '--red' : '--green'),
  kpi('🔥 Streak', `${S.streak} day${S.streak === 1 ? '' : 's'}`, `Best: ${S.best_streak} days`),
  kpi('▶️ Runs this week', S.runs_week, `${S.success_week} succeeded (${rate}%)`),
  kpi('⭐ Avg complexity', S.avg_score, `${S.avg_level} · ${S.files_total} files`),
].join('');

const tierIcon = { Beginner: '🟢', Intermediate: '🟡', Advanced: '🔴' };
$('roadmap').innerHTML = R.levels.map(l => {
  // Functions, so only the label for this level's status is built (done_on is null until a level is done).
  const label = {
    done: () => `Done ${fmt(l.done_on)}${l.late_by ? ` (+${l.late_by}d)` : ''}`,
    overdue: () => `${l.overdue_days} day${l.overdue_days === 1 ? '' : 's'} overdue`,
    current: () => `In progress ${l.topics_done}/${l.topics.length}`,
    upcoming: () => l.topics_done ? `${l.topics_done}/${l.topics.length} topics early` : 'Upcoming',
  }[l.status]();
  return `<div class="lvl-row ${l.status}">
    <div class="num">${l.status === 'done' ? '✓' : l.id}</div>
    <div class="lvl-name">${esc(l.name)}<small>${l.topics.map(t => esc(t.name)).join(', ')}</small></div>
    <div class="muted">${tierIcon[l.tier]} ${l.tier}</div>
    <div class="muted">${l.days} days · due ${fmt(l.due)}</div>
    <div class="status s-${l.status}">${label}</div></div>`;
}).join('');

if (cur) {
  const next = cur.topics.find(t => !t.done);
  $('currentCard').innerHTML = `<h2>📌 Current level: ${cur.id}. ${esc(cur.name)}</h2>
    <div class="target-head"><span>Topics completed</span><span>${cur.topics_done} / ${cur.topics.length}</span></div>
    <div class="bar" style="margin-bottom:14px"><span class="${cur.status === 'overdue' ? 'late' : ''}" style="width:${pct(cur.topics_done, cur.topics.length)}%"></span></div>
    <div class="chips">${cur.topics.map(t => `<span class="chip ${t.done ? 'on' : 'off'}" title="${t.done ? 'First used in ' + esc(t.file) + ' on ' + fmt(t.done_on) : 'Not used yet'}">${t.done ? '✓ ' : ''}${esc(t.name)}</span>`).join('')}</div>
    ${next ? `<div class="tip">💡 <b>Try next:</b> ${esc(next.try)} <a href="${esc(next.link)}" target="_blank">Lesson →</a></div>` : ''}
    <div class="muted" style="margin-top:14px">📚 Learn this level:</div>
    <ul class="links">${cur.links.map(k => `<li><a href="${esc(k.url)}" target="_blank">${esc(k.title)}</a></li>`).join('')}</ul>
    <div class="tip">🛠️ <b>Practice project:</b> ${esc(cur.project)}</div>`;
} else {
  $('currentCard').innerHTML = `<h2>📌 Current level</h2><div class="empty">🎉 Every level is complete.</div>`;
}

const target = (name, value, goal, unit) => {
  const done = value >= goal;
  return `<div class="target"><div class="target-head"><span>${name}</span><span>${value} / ${goal}${unit || ''} ${done ? '✅' : ''}</span></div>
    <div class="bar"><span class="${done ? 'done' : ''}" style="width:${pct(value, goal)}%"></span></div></div>`;
};
$('targets').innerHTML = [
  target('Levels completed', R.levels_done, 9),
  target('Topics mastered', R.topics_done, R.topics_total),
  target(`Time used (day ${Math.max(0, R.day_number)} of ${R.total_days})`, Math.max(0, R.day_number), R.total_days, ' days'),
  target("Today's successful runs", S.success_today, P.daily_runs_target),
  target("This week's lines of code", S.week_lines, P.weekly_lines_target),
  target('Streak', S.streak, P.streak_target_days, ' days'),
].join('');

$('errors').innerHTML = R.errors.length
  ? `<table><thead><tr><th>Error</th><th>Count</th><th>Last seen</th></tr></thead><tbody>${
      R.errors.map(e => `<tr><td>${esc(e.error)}</td><td>${e.count}</td><td>${fmt(e.last_seen)}</td></tr>`).join('')}</tbody></table>`
  : '<div class="empty">No errors in the last 30 days 🎉</div>';

$('recent').innerHTML = R.recent.length
  ? `<table><thead><tr><th>When</th><th>File</th><th>Result</th><th>Lines</th><th>Score</th><th>Level</th></tr></thead><tbody>${
      R.recent.map(r => `<tr><td>${fmt(r.time)} ${r.time.slice(11, 16)}</td><td>${esc(r.file)}</td>
        <td class="${r.status === 'success' ? 'ok' : 'err'}">${r.status === 'success' ? '✓ success' : esc(r.error || r.status)}</td>
        <td>${r.lines ?? '–'}</td><td>${r.score ?? '–'}</td><td>${r.level ? `<span class="lv ${r.level}">${r.level}</span>` : '–'}</td></tr>`).join('')}</tbody></table>`
  : '<div class="empty">No runs yet. Run a .py file from your code folder in VS Code and it will appear here.</div>';

if (R.saved_not_run.length) $('notrun').textContent = `Saved in the last 7 days but never run (not counted): ${R.saved_not_run.join(', ')}`;
$('footer').textContent = `Updated ${fmt(R.generated, 1)} ${R.generated.slice(11, 16)} · Refresh with: python tracker\\\\track.py`;

if (window.Chart) {
  const css = getComputedStyle(document.documentElement);
  const c = n => css.getPropertyValue(n).trim();
  Chart.defaults.color = c('--muted');
  Chart.defaults.borderColor = c('--border');
  new Chart($('planChart'), {
    type: 'line',
    data: { labels: R.plan_vs_actual.map(p => fmt(p.date)), datasets: [
      { label: 'Plan', data: R.plan_vs_actual.map(p => p.planned), borderColor: c('--muted'), borderDash: [6, 4], stepped: true, pointRadius: 0 },
      { label: 'Actual', data: R.plan_vs_actual.map(p => p.actual), borderColor: c('--accent'), backgroundColor: c('--accent'), stepped: true, pointRadius: 3 } ] },
    options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 9, ticks: { stepSize: 1 } } } }
  });
  new Chart($('runsChart'), {
    type: 'bar',
    data: { labels: R.daily.map(d => fmt(d.date)), datasets: [
      { label: 'Success', data: R.daily.map(d => d.success), backgroundColor: c('--green'), borderRadius: 3 },
      { label: 'Error / stopped', data: R.daily.map(d => d.error), backgroundColor: c('--red'), borderRadius: 3 } ] },
    options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } }
  });
}
</script>
</body>
</html>
"""

PLAN_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Python Learning Plan</title>
<style>
__STYLE__
  .wrap { max-width: 1000px; }
  .controls { display: flex; flex-wrap: wrap; gap: 16px; align-items: end; margin: 18px 0 16px; }
  .toggle { display: inline-flex; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: var(--card); }
  .toggle button { border: 0; background: transparent; color: var(--text); padding: 10px 18px; font: inherit; cursor: pointer; }
  .toggle button.on { background: var(--accent); color: #fff; font-weight: 600; }
  .toggle button.on.aggressive { background: var(--aggr); }
  label { font-size: 13px; color: var(--muted); display: block; margin-bottom: 4px; }
  input[type=date] { font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--card); color: var(--text); }
  .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .summary .card { padding: 14px; }
  .summary .v { font-size: 20px; font-weight: 700; }
  .timeline { display: flex; height: 26px; border-radius: 8px; overflow: hidden; margin-bottom: 6px; }
  .timeline div { display: grid; place-items: center; color: #fff; font-size: 12px; font-weight: 600; min-width: 0; }
  .t0 { background: var(--green); } .t1 { background: var(--yellow); color: #3a2e00 !important; } .t2 { background: var(--red); }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
  .tier-title { margin: 22px 0 10px; font-size: 18px; }
  .level { margin-bottom: 12px; }
  .level-head { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: baseline; }
  .level-head h3 { margin: 0; font-size: 17px; }
  .dates { font-size: 13px; font-weight: 600; background: var(--track); padding: 3px 10px; border-radius: 999px; white-space: nowrap; }
  .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 12px; }
  .cols h4 { margin: 0 0 6px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; }
  ul { margin: 0; padding-left: 18px; font-size: 14px; }
  .project { margin-top: 12px; font-size: 14px; background: var(--track); border-radius: 8px; padding: 10px 12px; }
  .rule { margin-top: 8px; font-size: 13px; color: var(--muted); }
  .note { font-size: 13px; padding: 8px 12px; border-radius: 8px; background: var(--card); border: 1px dashed var(--border); }
</style>
</head>
<body>
<div class="wrap">
  <h1>🗺️ Python Learning Plan: Beginner → Advanced</h1>
  <div class="muted">9 levels. Learn with the links, practise in VS Code, and the tracker ticks off each topic when your code uses it and runs successfully.
    <a href="dashboard.html">Back to dashboard →</a></div>

  <div class="controls">
    <div><label>Plan</label><div class="toggle" id="toggle"></div></div>
    <div><label for="start">Start date</label><input type="date" id="start"></div>
    <div class="note" id="note"></div>
  </div>

  <div class="card mb" id="desc"></div>
  <div class="summary" id="summary"></div>
  <div class="timeline" id="timeline"></div>
  <div class="legend muted">
    <span><span class="dot t0"></span>Beginner (levels 1–3)</span>
    <span><span class="dot t1"></span>Intermediate (levels 4–6)</span>
    <span><span class="dot t2"></span>Advanced (levels 7–9)</span>
  </div>
  <div id="levels"></div>
</div>

<script>
const D = __DATA__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = d => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const tiers = { Beginner: ['🟢 Beginner', 0], Intermediate: ['🟡 Intermediate', 1], Advanced: ['🔴 Advanced', 2] };
let plan = D.my_plan;
$('start').value = D.my_start;

function render() {
  const P = D.curriculum.plans[plan];
  const mine = plan === D.my_plan && $('start').value === D.my_start;
  $('toggle').innerHTML = Object.entries(D.curriculum.plans).map(([k, p]) =>
    `<button class="${k === plan ? 'on ' + k : ''}" data-plan="${k}">${p.icon} ${p.label}${k === D.my_plan ? ' (yours)' : ''}</button>`).join('');
  $('note').innerHTML = mine ? '✅ This is <b>your</b> plan.' : '👀 Preview only. To switch, edit <b>plan</b> / <b>start_date</b> in config.json or re-run setup.py.';

  const start = new Date(($('start').value || D.my_start) + 'T00:00');
  const levels = D.curriculum.levels;
  const total = levels.reduce((t, l) => t + l.days[plan], 0);
  $('desc').innerHTML = `${P.icon} <b>${P.label}</b>: ${esc(P.description)} About ${esc(P.daily_effort)}.`;
  $('summary').innerHTML = [
    ['Total duration', `${total} days`], ['Finish date', fmt(addDays(start, total - 1))],
    ['Daily effort', P.daily_effort], ['Daily target', `${P.daily_runs_target} successful runs`],
    ['Weekly target', `${P.weekly_lines_target} lines`],
  ].map(([k, v]) => `<div class="card"><div class="muted">${k}</div><div class="v">${v}</div></div>`).join('');
  $('timeline').innerHTML = levels.map(l =>
    `<div class="t${tiers[l.tier][1]}" style="flex:${l.days[plan]}" title="${esc(l.name)}: ${l.days[plan]} days">${l.id}</div>`).join('');

  let day = 0, html = '', lastTier = '';
  for (const l of levels) {
    if (l.tier !== lastTier) { html += `<h2 class="tier-title">${tiers[l.tier][0]}</h2>`; lastTier = l.tier; }
    const days = l.days[plan], from = addDays(start, day), to = addDays(start, day + days - 1);
    day += days;
    html += `<div class="card level">
      <div class="level-head"><h3>Level ${l.id}: ${esc(l.name)}</h3>
        <span class="dates">${days} days · ${fmt(from)} → ${fmt(to)}</span></div>
      <div class="cols">
        <div><h4>Topics tracked</h4><ul>${l.topics.map(t => `<li><a href="${esc(t.link)}" target="_blank">${esc(t.name)}</a></li>`).join('')}</ul></div>
        <div><h4>Learn from</h4><ul>${l.links.map(k => `<li><a href="${esc(k.url)}" target="_blank">${esc(k.title)}</a></li>`).join('')}</ul></div>
      </div>
      <div class="project">🛠️ <b>Practice project:</b> ${esc(l.project)}</div>
      <div class="rule">✅ Complete when every topic appears in code that ran successfully. ⚠️ Alert email if not done by ${fmt(to)}.</div>
    </div>`;
  }
  $('levels').innerHTML = html;
}

$('toggle').addEventListener('click', e => { const b = e.target.closest('button'); if (b) { plan = b.dataset.plan; render(); } });
$('start').addEventListener('change', render);
render();
</script>
</body>
</html>
"""


def _embed(data):
    """JSON that is safe to put inside a <script> tag."""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def write_dashboard(report, path=DASHBOARD_PATH):
    public = {k: v for k, v in report.items() if not k.startswith("_")}
    html = DASHBOARD_TEMPLATE.replace("__STYLE__", STYLE).replace("__DATA__", _embed(public))
    path.write_text(html, encoding="utf-8")
    return path


def write_plan(config, curriculum, path=PLAN_PATH):
    data = {"curriculum": curriculum, "my_plan": config["plan"], "my_start": config["start_date"]}
    html = PLAN_TEMPLATE.replace("__STYLE__", STYLE).replace("__DATA__", _embed(data))
    path.write_text(html, encoding="utf-8")
    return path
