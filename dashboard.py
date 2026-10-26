"""Writes dashboard.html (your progress) and plan.html (the learning plans).

The pages are plain HTML files. Python embeds the data as JSON and a little
JavaScript in the page draws the tabs, cards, roadmaps and charts: one tab per
language, plus an Overview on the dashboard.
"""

import json

from languages import all_packs
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

DASHBOARD_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learning Tracker</title>
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
  .grid > *, .card { min-width: 0; }
  .tabs { display: flex; gap: 8px; margin-bottom: 18px; overflow-x: auto; padding-bottom: 2px; }
  .tab { border: 1px solid var(--border); background: var(--card); color: var(--text); padding: 8px 16px; border-radius: 999px;
         font: inherit; cursor: pointer; white-space: nowrap; }
  .tab.on { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
  [hidden] { display: none !important; }
  .ov-cards { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
  button.ov-card { text-align: left; font: inherit; color: var(--text); cursor: pointer; width: 100%; }
  button.ov-card:hover { border-color: var(--accent); }
  .ov-card .name { font-weight: 700; font-size: 16px; }
  .ov-card .lvl { margin: 6px 0; font-size: 14px; }
  .ov-card .row { display: flex; justify-content: space-between; font-size: 13px; margin: 8px 0 4px; color: var(--muted); }
  .add-card { border-style: dashed; color: var(--muted); font-size: 14px; }
  code { background: var(--track); padding: 1px 6px; border-radius: 6px; }
  .overall { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-bottom: 16px; font-size: 15px; }
  td small { display: block; color: var(--muted); font-size: 12px; }
  .st-off { color: var(--muted); font-weight: 600; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1 id="title">📚 My Learning Tracker</h1>
  </header>
  <nav class="tabs" id="tabs" role="tablist"></nav>
  <div id="panels"></div>
  <p class="muted" id="footer"></p>
</div>

<script>
const R = __DATA__;
const PACKS = __PACKS__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (iso, year) => new Date(iso.slice(0, 10) + 'T00:00').toLocaleDateString('en-GB',
  year ? { day: 'numeric', month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' });
const pct = (a, b) => b ? Math.min(100, Math.round(a / b * 100)) : 0;
const EXT = { python: '.py', java: '.java', javascript: '.js' };
// Categorical slots 1-3 of the dataviz palette (light, dark): a language keeps its colour everywhere.
const SERIES = { python: ['#2a78d6', '#3987e5'], java: ['#eb6834', '#d95926'], javascript: ['#1baf7a', '#199e70'] };
const isDark = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
const seriesColor = key => (SERIES[key] || ['#888', '#888'])[isDark() ? 1 : 0];
const errorBanner = rep => `<div class="banner bad">⚠️ Couldn't read ${esc(rep.label)} data, see data\\send_report.log</div>`;

const STATUS = {
  success: ['ok', '✅'], compiled: ['ok', '✅ compiled'], error: ['err', '❌'],
  compile_error: ['err', '❌ compile'], stopped: ['st-off', '⏹'], saved: ['st-off', '💾 saved'],
};

function chartDefaults() {
  const css = getComputedStyle(document.documentElement);
  const c = n => css.getPropertyValue(n).trim();
  Chart.defaults.color = c('--muted');
  Chart.defaults.borderColor = c('--border');
  return c;
}

// One language's page (the old single-report dashboard). Returns a function that draws its charts.
function renderLanguage(R, el) {
  if (R.error) { el.innerHTML = errorBanner(R); return null; }
  const k = R.language;
  const $ = id => document.getElementById(`${k}-${id}`);
  const S = R.stats, P = R.plan, cur = R.current_level;
  const started = R.day_number >= 1;
  const nLevels = R.curriculum_levels;
  el.innerHTML = `
  <div class="meta mb" id="${k}-meta"></div>
  <div id="${k}-banner"></div>
  <section class="grid kpis" id="${k}-kpis"></section>
  <section class="card mb">
    <h2>🗺️ Learning roadmap: Beginner → Advanced <a class="muted" href="plan.html" style="font-weight:400;margin-left:8px">see full plan →</a></h2>
    <div class="roadmap" id="${k}-roadmap"></div>
  </section>
  <section class="grid two">
    <div class="card" id="${k}-currentCard"></div>
    <div class="card"><h2>🎯 Targets</h2><div id="${k}-targets"></div></div>
  </section>
  <section class="grid two">
    <div class="card"><h2>📈 Plan vs actual (levels completed)</h2><div class="chart-box"><canvas id="${k}-planChart"></canvas></div></div>
    <div class="card"><h2>📊 Daily runs (last 14 days)</h2><div class="chart-box"><canvas id="${k}-runsChart"></canvas></div></div>
  </section>
  <section class="grid two">
    <div class="card"><h2>🐞 Most common errors (last 30 days)</h2><div class="table-wrap" id="${k}-errors"></div></div>
    <div class="card"><h2>📂 Recent runs</h2><div class="table-wrap" id="${k}-recent"></div></div>
  </section>
  ${k === 'java' ? `<section class="card mb"><h2>📁 Java sources found in</h2><div class="table-wrap" id="${k}-folders"></div>
    <p class="muted">Not your learning code? Add the folder to languages.java.exclude_folders in config.json.</p></section>` : ''}
  <p class="muted" id="${k}-notrun"></p>`;

  $('meta').innerHTML = `
    <span class="pill">${esc(R.icon)} ${esc(R.label)} · ${esc(R.editor)}</span>
    <span class="pill plan ${esc(R.plan_key)}">${esc(P.icon)} ${esc(P.label)} plan · ${R.total_days} days</span>
    <span class="pill">📅 ${started ? `Started ${fmt(R.start_date, 1)} · Day ${R.day_number}` : `Starts ${fmt(R.start_date, 1)}`}</span>
    <span class="pill">🏁 Target finish ${fmt(R.planned_finish, 1)}</span>`;

  if (!started) {
    $('banner').innerHTML = `<div class="banner info">⏳ Your ${esc(R.label)} plan starts on <b>${fmt(R.start_date, 1)}</b>. Runs before that date are not counted.</div>`;
  } else if (!cur) {
    $('banner').innerHTML = `<div class="banner good">🎉 <b>All ${nLevels} levels complete!</b> You've finished the ${esc(R.label)} learning path.</div>`;
  } else if (cur.status === 'overdue') {
    const missing = cur.topics.filter(t => !t.done).map(t => `<b>${esc(t.name)}</b>`).join(', ');
    $('banner').innerHTML = `<div class="banner bad">⚠️ <b>Stuck alert:</b> Level ${cur.id} "${esc(cur.name)}" was due on <b>${fmt(cur.due)}</b>
      and is now <b>${cur.overdue_days} day${cur.overdue_days === 1 ? '' : 's'} overdue</b>. Still to do: ${missing}.</div>`;
  }

  const kpi = (label, value, sub, color) => `<div class="card kpi"><div class="label">${label}</div>
    <div class="value"${color ? ` style="color:var(${color})"` : ''}>${value}</div><div class="sub">${sub}</div></div>`;
  const rate = S.runs_week ? Math.round(S.success_week / S.runs_week * 100) : 0;
  $('kpis').innerHTML = [
    kpi('🎓 Current level', cur ? `${cur.id} / ${nLevels}` : `${nLevels} / ${nLevels}`, cur ? esc(cur.name) : 'Complete'),
    kpi('📅 Schedule', R.days_behind ? `−${R.days_behind} days` : 'On track', R.days_behind ? 'Behind plan' : `Finish ${fmt(R.expected_finish)}`, R.days_behind ? '--red' : '--green'),
    kpi('🔥 Streak', `${S.streak} day${S.streak === 1 ? '' : 's'}`, `Best: ${S.best_streak} days`),
    kpi('▶️ Runs this week', S.runs_week, `${S.success_week} succeeded (${rate}%)`),
    kpi('⭐ Avg complexity', S.avg_score, `${esc(S.avg_level)} · ${S.files_total} files`),
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
    return `<div class="lvl-row ${esc(l.status)}">
      <div class="num">${l.status === 'done' ? '✓' : l.id}</div>
      <div class="lvl-name">${esc(l.name)}<small>${l.topics.map(t => esc(t.name)).join(', ')}</small></div>
      <div class="muted">${tierIcon[l.tier] || ''} ${esc(l.tier)}</div>
      <div class="muted">${l.days} days · due ${fmt(l.due)}</div>
      <div class="status s-${esc(l.status)}">${label}</div></div>`;
  }).join('');

  if (cur) {
    const next = cur.topics.find(t => !t.done);
    $('currentCard').innerHTML = `<h2>📌 Current level: ${cur.id}. ${esc(cur.name)}</h2>
      <div class="target-head"><span>Topics completed</span><span>${cur.topics_done} / ${cur.topics.length}</span></div>
      <div class="bar" style="margin-bottom:14px"><span class="${cur.status === 'overdue' ? 'late' : ''}" style="width:${pct(cur.topics_done, cur.topics.length)}%"></span></div>
      <div class="chips">${cur.topics.map(t => `<span class="chip ${t.done ? 'on' : 'off'}" title="${t.done ? 'First used in ' + esc(t.file) + ' on ' + fmt(t.done_on) : 'Not used yet'}">${t.done ? '✓ ' : ''}${esc(t.name)}</span>`).join('')}</div>
      ${next ? `<div class="tip">💡 <b>Try next:</b> ${esc(next.try)} <a href="${esc(next.link)}" target="_blank">Lesson →</a></div>` : ''}
      <div class="muted" style="margin-top:14px">📚 Learn this level:</div>
      <ul class="links">${cur.links.map(l => `<li><a href="${esc(l.url)}" target="_blank">${esc(l.title)}</a></li>`).join('')}</ul>
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
    target('Levels completed', R.levels_done, nLevels),
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

  const result = r => {
    const [cls, text] = STATUS[r.status] || ['st-off', esc(r.status)];
    return `<td class="${cls}">${text}${r.status === 'error' && r.error ? ' ' + esc(r.error) : ''}</td>`;
  };
  $('recent').innerHTML = R.recent.length
    ? `<table><thead><tr><th>When</th><th>File</th><th>Result</th><th>Lines</th><th>Score</th><th>Level</th></tr></thead><tbody>${
        R.recent.map(r => `<tr><td>${fmt(r.time)} ${esc(r.time.slice(11, 16))}</td>
          <td>${esc(r.file)}${k === 'java' && r.folder ? `<small>${esc(r.folder)}</small>` : ''}</td>${result(r)}
          <td>${r.lines ?? '–'}</td><td>${r.score ?? '–'}</td><td>${r.level ? `<span class="lv ${esc(r.level)}">${esc(r.level)}</span>` : '–'}</td></tr>`).join('')}</tbody></table>`
    : `<div class="empty">No runs yet. Run a ${EXT[k] || ''} file in ${esc(R.editor)} and it will appear here.</div>`;

  if (k === 'java') {
    const rows = R.java_folders || [];
    $('folders').innerHTML = rows.length
      ? `<table><thead><tr><th>Folder</th><th>Files</th><th>Last seen</th></tr></thead><tbody>${
          rows.map(f => `<tr><td>${esc(f.folder)}</td><td>${f.files}</td><td>${fmt(f.last_seen)}</td></tr>`).join('')}</tbody></table>`
      : '<div class="empty">No Java sources seen yet.</div>';
  }

  if (R.saved_not_run.length) $('notrun').textContent = `Saved in the last 7 days but never run (not counted): ${R.saved_not_run.join(', ')}`;

  return () => {
    if (!window.Chart) return;
    const c = chartDefaults();
    new Chart($('planChart'), {
      type: 'line',
      data: { labels: R.plan_vs_actual.map(p => fmt(p.date)), datasets: [
        { label: 'Plan', data: R.plan_vs_actual.map(p => p.planned), borderColor: c('--muted'), borderDash: [6, 4], stepped: true, pointRadius: 0 },
        { label: 'Actual', data: R.plan_vs_actual.map(p => p.actual), borderColor: c('--accent'), backgroundColor: c('--accent'), stepped: true, pointRadius: 3 } ] },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: nLevels, ticks: { stepSize: 1 } } } }
    });
    new Chart($('runsChart'), {
      type: 'bar',
      data: { labels: R.daily.map(d => fmt(d.date)), datasets: [
        { label: 'Success', data: R.daily.map(d => d.success), backgroundColor: c('--green'), borderRadius: 3 },
        { label: 'Error / stopped', data: R.daily.map(d => d.error), backgroundColor: c('--red'), borderRadius: 3 } ] },
      options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } }
    });
  };
}

function renderOverview(el) {
  const cards = R.enabled.map(k => {
    const rep = R.languages[k];
    if (rep.error) return `<button class="card ov-card" data-tab="${esc(k)}">${errorBanner(rep)}</button>`;
    const cur = rep.current_level, S = rep.stats;
    const status = rep.day_number < 1 ? `⏳ starts ${fmt(rep.start_date)}`
      : rep.days_behind ? `⚠️ ${rep.days_behind} day${rep.days_behind === 1 ? '' : 's'} behind` : '✅ on track';
    return `<button class="card ov-card" data-tab="${esc(k)}">
      <div class="name">${esc(rep.icon)} ${esc(rep.label)}</div>
      <div class="lvl">${cur ? `Level ${cur.id}: ${esc(cur.name)}` : '🎉 All levels complete'}</div>
      <div>${status} · 🔥 ${S.streak}-day streak</div>
      <div class="row"><span>Levels</span><span>${rep.levels_done}/${rep.curriculum_levels}</span></div>
      <div class="bar"><span class="${rep.levels_done >= rep.curriculum_levels ? 'done' : ''}" style="width:${pct(rep.levels_done, rep.curriculum_levels)}%"></span></div></button>`;
  }).join('');
  const add = PACKS.filter(p => !R.enabled.includes(p.key)).map(p =>
    `<div class="card add-card">➕ Add ${esc(p.icon)} ${esc(p.label)} with <code>python tracker\\setup.py</code></div>`).join('');
  const O = R.overall;
  el.innerHTML = `
    <section class="grid ov-cards">${cards}</section>
    <div class="overall"><span>🔥 <b>Any-language streak:</b> ${O.any_streak} day${O.any_streak === 1 ? '' : 's'}</span>
      <span>This week: <b>${O.week_activity}</b> runs/compiles</span></div>
    <section class="card mb"><h2>📊 Counting runs per day (last 14 days)</h2><div class="chart-box"><canvas id="overviewChart" role="img" aria-label="Counting runs per day by language"></canvas></div></section>
    ${add ? `<section class="grid ov-cards">${add}</section>` : ''}`;
  return () => {
    if (!window.Chart) return;
    const c = chartDefaults();
    const days = O.daily_by_language;
    const keys = R.enabled.filter(k => !R.languages[k].error);
    new Chart($('overviewChart'), {
      type: 'bar',
      data: { labels: days.map(d => fmt(d.date)), datasets: keys.map(k => ({
        label: R.languages[k].label, data: days.map(d => d[k] || 0), backgroundColor: seriesColor(k),
        borderColor: c('--card'), borderWidth: 2, borderRadius: 3 })) },
      options: { responsive: true, maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } }
    });
  };
}

// ----- page: header, tabs, panels -----
$('title').textContent = `📚 ${R.learner || 'My'}${R.learner ? "'s" : ''} Learning Tracker`;
$('footer').textContent = `Updated ${fmt(R.generated, 1)} ${R.generated.slice(11, 16)} · Refresh with: python tracker\\track.py`;
const tabKeys = ['overview', ...R.enabled];
const draw = {}, drawn = {};
$('tabs').innerHTML = tabKeys.map(k => {
  const rep = R.languages[k];
  return `<button class="tab" role="tab" id="tab-${esc(k)}" data-tab="${esc(k)}">${k === 'overview' ? '🏠 Overview' : `${esc(rep.icon)} ${esc(rep.label)}`}</button>`;
}).join('');
$('panels').innerHTML = tabKeys.map(k => `<div id="panel-${esc(k)}" role="tabpanel" hidden></div>`).join('');
draw.overview = renderOverview($('panel-overview'));
R.enabled.forEach(k => { draw[k] = renderLanguage(R.languages[k], $(`panel-${k}`)); });

function showTab(t, save) {
  if (!tabKeys.includes(t)) t = 'overview';
  tabKeys.forEach(k => {
    $(`panel-${k}`).hidden = k !== t;
    $(`tab-${k}`).classList.toggle('on', k === t);
    $(`tab-${k}`).setAttribute('aria-selected', k === t);
  });
  if (save) { try { localStorage.setItem('tracker.tab', t); } catch (e) {} }
  // Charts are drawn when their tab is first shown, so they get a real size.
  if (!drawn[t] && draw[t]) { drawn[t] = true; try { draw[t](); } catch (e) {} }
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-tab]');
  if (b) { showTab(b.dataset.tab, true); window.scrollTo(0, 0); }
});
let saved = null;
try { saved = localStorage.getItem('tracker.tab'); } catch (e) {}
showTab(saved, false);
</script>
</body>
</html>
"""

PLAN_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learning Plan</title>
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
  .tabs { display: flex; gap: 8px; margin: 18px 0 0; overflow-x: auto; padding-bottom: 2px; }
  .tab { border: 1px solid var(--border); background: var(--card); color: var(--text); padding: 8px 16px; border-radius: 999px;
         font: inherit; cursor: pointer; white-space: nowrap; }
  .tab.on { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🗺️ Learning Plan: Beginner → Advanced</h1>
  <div class="muted">Pick a language. Learn with the links, practise in its editor, and the tracker ticks off each topic when your code uses it and runs or compiles successfully.
    <a href="dashboard.html">Back to dashboard →</a></div>
  <nav class="tabs" id="tabs"></nav>

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
const keys = Object.keys(D.courses);
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

// Per-language preview state: starts at the learner's own plan and start date (today for a language not set up).
const state = {};
for (const k of keys) state[k] = D.mine[k] ? { plan: D.mine[k].plan, start: D.mine[k].start } : { plan: 'standard', start: iso(new Date()) };
let tab = keys.find(k => D.mine[k]) || keys[0];
try { const s = localStorage.getItem('tracker.tab'); if (keys.includes(s)) tab = s; } catch (e) {}

function render() {
  const course = D.courses[tab], cur = course.curriculum, st = state[tab], mineCfg = D.mine[tab];
  $('tabs').innerHTML = keys.map(k =>
    `<button class="tab${k === tab ? ' on' : ''}" data-tab="${esc(k)}">${esc(D.courses[k].icon)} ${esc(D.courses[k].label)}</button>`).join('');
  $('start').value = st.start;
  const plan = st.plan, P = cur.plans[plan];
  const mine = !!mineCfg && plan === mineCfg.plan && st.start === mineCfg.start;
  $('toggle').innerHTML = Object.entries(cur.plans).map(([k, p]) =>
    `<button class="${k === plan ? 'on ' + esc(k) : ''}" data-plan="${esc(k)}">${esc(p.icon)} ${esc(p.label)}${mineCfg && k === mineCfg.plan ? ' (yours)' : ''}</button>`).join('');
  $('note').innerHTML = !mineCfg ? '👀 Preview only. To learn it, re-run python tracker\\setup.py and choose it.' : mine ? '✅ This is <b>your</b> plan.' : '👀 Preview only. To switch, edit <b>plan</b> / <b>start_date</b> in config.json or re-run setup.py.';

  const start = new Date((st.start || iso(new Date())) + 'T00:00');
  const levels = cur.levels;
  const total = levels.reduce((t, l) => t + l.days[plan], 0);
  $('desc').innerHTML = `${esc(P.icon)} <b>${esc(P.label)}</b>: ${esc(P.description)} About ${esc(P.daily_effort)}. Practise in ${esc(course.editor)}.`;
  $('summary').innerHTML = [
    ['Total duration', `${total} days`], ['Finish date', fmt(addDays(start, total - 1))],
    ['Daily effort', esc(P.daily_effort)], ['Daily target', `${P.daily_runs_target} successful runs`],
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
      <div class="rule">✅ Complete when every topic appears in code that ran or compiled successfully. ⚠️ Alert email if not done by ${fmt(to)}.</div>
    </div>`;
  }
  $('levels').innerHTML = html;
}

$('tabs').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (b) { tab = b.dataset.tab; try { localStorage.setItem('tracker.tab', tab); } catch (e) {} render(); }
});
$('toggle').addEventListener('click', e => { const b = e.target.closest('button'); if (b) { state[tab].plan = b.dataset.plan; render(); } });
$('start').addEventListener('change', () => { state[tab].start = $('start').value; render(); });
render();
</script>
</body>
</html>
"""


def _embed(data):
    """JSON that is safe to put inside a <script> tag."""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _public(value):
    """Drop keys starting with "_" (raw data for the emailer) at every level."""
    if isinstance(value, dict):
        return {k: _public(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [_public(v) for v in value]
    return value


def write_dashboard(report, path=DASHBOARD_PATH):
    data = {key: _public(report[key]) for key in ("learner", "generated", "today", "enabled", "overall", "languages")}
    packs = [{"key": p.key, "label": p.label, "icon": p.icon} for p in all_packs()]
    html = (DASHBOARD_TEMPLATE.replace("__STYLE__", STYLE)
            .replace("__PACKS__", _embed(packs)).replace("__DATA__", _embed(data)))
    path.write_text(html, encoding="utf-8")
    return path


def write_plan(config, path=PLAN_PATH):
    courses = {p.key: {"label": p.label, "icon": p.icon, "editor": p.editor, "curriculum": p.curriculum()}
               for p in all_packs()}
    mine = {}
    for p in all_packs():
        lang = config.get("languages", {}).get(p.key, {})
        if lang.get("enabled"):
            mine[p.key] = {"plan": lang["plan"], "start": lang["start_date"]}
    html = PLAN_TEMPLATE.replace("__STYLE__", STYLE).replace("__DATA__", _embed({"courses": courses, "mine": mine}))
    path.write_text(html, encoding="utf-8")
    return path
