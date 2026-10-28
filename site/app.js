// B12 site: renders data.json (built by build_data.py). No figure is typed here: headline values come from
// data.claims (results/claims.json by id), everything else from per-match or per-team rows.
(function () {
  'use strict';
  var F = window.B12Forecast;
  var PAGE = 40;
  var PARITY_TOL = 1e-9;

  // ---------------------------------------------------------------- helpers
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'html') n.innerHTML = attrs[k];
      else if (k === 'class') n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function minus(s) { return String(s).replace(/^-/, '−'); }
  function pct(p) { return Math.round(p * 100) + '%'; }
  function pct1(p) { return (p * 100).toFixed(1) + '%'; }
  function argmax(a) { var b = 0; for (var i = 1; i < a.length; i++) if (a[i] > a[b]) b = i; return b; }
  function outcome(h, a) { return h > a ? 0 : h === a ? 1 : 2; }
  var OUT = ['home win', 'draw', 'away win'];
  function day(dt) { return dt.slice(0, 10); }
  function fmtDay(d) {
    var m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return +d.slice(8, 10) + ' ' + m[+d.slice(5, 7) - 1] + ' ' + d.slice(0, 4);
  }
  function fmtStamp(s) { return fmtDay(s.slice(0, 10)) + ', ' + s.slice(11, 16); }
  function strip(p, cls, actual, names) {
    names = names || OUT;
    var s = el('div', { class: 'strip' + (cls ? ' ' + cls : ''), role: 'img',
      'aria-label': names.map(function (n, i) { return n + ' ' + pct(p[i]); }).join(', ') +
        (actual != null ? '; actual: ' + names[actual] : '') });
    ['h', 'd', 'a'].forEach(function (c, i) {
      var seg = el('span', { class: c + (actual === i ? ' actual' : ''), style: 'width:' + (100 * p[i]).toFixed(3) + '%' });
      if (p[i] >= 0.12) seg.textContent = pct(p[i]);
      s.appendChild(seg);
    });
    return s;
  }

  var DATA, C;
  function claim(id) {
    if (!(id in C)) throw new Error('unknown claim ' + id);
    return el('span', { class: 'claim', title: 'results/claims.json: ' + id, 'data-claim-id': id, text: minus(C[id]) });
  }
  function frag(parts) {
    var f = document.createDocumentFragment();
    parts.forEach(function (p) { f.appendChild(typeof p === 'string' ? document.createTextNode(p) : p); });
    return f;
  }
  function claimInterval(lo, hi) { return frag(['[', claim(lo), ', ', claim(hi), ']']); }

  // ---------------------------------------------------------------- theme
  function initTheme() {
    var btn = document.getElementById('theme-toggle');
    var root = document.documentElement;
    var stored = null;
    try { stored = localStorage.getItem('b12-theme'); } catch (e) { /* storage unavailable */ }
    if (stored === 'dark' || stored === 'light') root.setAttribute('data-theme', stored);
    function isDark() {
      var t = root.getAttribute('data-theme');
      return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    function label() {
      btn.textContent = isDark() ? 'Light mode' : 'Dark mode';
      btn.setAttribute('aria-pressed', String(isDark()));
    }
    btn.addEventListener('click', function () {
      var next = isDark() ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('b12-theme', next); } catch (e) { /* storage unavailable */ }
      label();
    });
    label();
  }

  function initNav() {
    var links = Array.prototype.slice.call(document.querySelectorAll('nav a'));
    var targets = links.map(function (a) { return document.querySelector(a.getAttribute('href')); });
    var pending = false;
    function mark() {
      pending = false;
      var current = -1;
      targets.forEach(function (t, i) { if (t && t.getBoundingClientRect().top <= window.innerHeight * 0.35) current = i; });
      links.forEach(function (a, i) { if (i === current) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
    }
    window.addEventListener('scroll', function () { if (!pending) { pending = true; requestAnimationFrame(mark); } }, { passive: true });
    mark();
  }

  // ---------------------------------------------------------------- hero
  function renderHero(matches) {
    var games = matches.slice().sort(function (a, b) { return a.datetime < b.datetime ? 1 : -1; }).slice(0, 6);
    var ol = document.getElementById('hero-board');
    games.forEach(function (r) {
      var act = outcome(r.goals_home, r.goals_away);
      ol.appendChild(el('li', null, [
        el('span', { class: 't h', text: r.home }),
        el('span', { class: 'sc', text: r.goals_home + '–' + r.goals_away }),
        el('span', { class: 't', text: r.away }),
        strip(r.M2, 'small', act),
        el('span', { class: 'lg', text: r.league + ', ' + fmtDay(day(r.datetime)) })
      ]));
    });
  }

  // ---------------------------------------------------------------- overview
  function renderResults() {
    var rows = [
      { what: 'Static Dixon-Coles vs the sequential filter (RPS, lower is better)',
        data: frag(['TEST window, ', claim('c019'), ' common matches']),
        diff: frag([claim('c020'), ' vs ', claim('c023')]), iv: '', verdict: ['The filter alone does not beat the static model', 'meh'] },
      { what: 'Learned filter (P1) vs baseline',
        data: frag(['TEST window, ', claim('c008'), ' matches (retrospective holdout)']),
        diff: claim('c124'), iv: claimInterval('c125', 'c126'), verdict: ['Accepted', 'pass'] },
      { what: 'P1 vs baseline, replication',
        data: frag(['Four untouched seasons 2015-16 to 2018-19, ', claim('p2_003'), ' matches']),
        diff: claim('p2_027'), iv: frag([claim('p2_026'), ' ', claimInterval('p2_028', 'p2_029')]), verdict: ['Replicated', 'pass'] },
      { what: 'Final model (P2: refined settings, shots on target in the update) vs P1',
        data: 'Same fresh seasons',
        diff: claim('p2_032'), iv: frag([claim('p2_026'), ' ', claimInterval('p2_033', 'p2_034')]), verdict: ['Replicated', 'pass'] },
      { what: 'P1 vs baseline (T1)',
        data: frag(['2026-27, ', claim('l10_002'), ' completed matches, frozen parameters']),
        diff: claim('l10_009'), iv: frag([claim('l10_006'), ' ', claimInterval('l10_010', 'l10_011')]), verdict: ['Accepted', 'pass'] },
      { what: 'Final model vs P1 (T2)',
        data: 'Same 2026-27 matches',
        diff: claim('l10_013'), iv: frag([claim('l10_006'), ' ', claimInterval('l10_014', 'l10_015')]), verdict: ['Accepted, marginal', 'meh'] },
      { what: 'Forecast averaged over rating uncertainty vs plug-in forecast',
        data: 'Development and validation windows',
        diff: frag(['Worse on both']), iv: frag([claim('pp_007'), ' ', claimInterval('pp_012', 'pp_013')]), verdict: ['Rejected', 'fail'] },
      { what: 'Lineup weighting, defence term (Gate B)',
        data: 'Training data',
        diff: claim('c050'), iv: claimInterval('c051', 'c052'), verdict: ['Failed', 'fail'] },
      { what: 'Model stacked with market odds vs odds alone',
        data: 'Development and validation windows',
        diff: '', iv: frag([claim('p2_004'), ' ', claimInterval('p2_023', 'p2_024')]), verdict: ['Rejected', 'fail'] }
    ];
    var tb = document.querySelector('#results-table tbody');
    rows.forEach(function (r) {
      function cell(x, cls) { var td = el('td', cls ? { class: cls } : null); if (typeof x === 'string') td.textContent = x; else td.appendChild(x); return td; }
      tb.appendChild(el('tr', null, [
        el('th', { scope: 'row', text: r.what }), cell(r.data), cell(r.diff, 'n'), cell(r.iv, 'n'),
        el('td', { class: 'verdict ' + r.verdict[1], text: r.verdict[0] })
      ]));
    });
  }

  function renderCaveats(season, forward) {
    var scored = forward.filter(function (f) { return f.scored; }).length;
    var items = [
      frag([el('strong', { text: 'Both novelties failed. ' }), 'Surprise-driven updating was switched off by validation, and lineup weighting failed its gate: the defence effect was ',
        claim('c050'), ' with interval ', claimInterval('c051', 'c052'), '.']),
      frag([el('strong', { text: 'The posterior-predictive forecast was rejected. ' }), 'Averaging over rating uncertainty made forecasts worse, interval ',
        claimInterval('pp_012', 'pp_013'), '.']),
      frag([el('strong', { text: 'The 2026-27 result is retrospective. ' }), 'Parameters were frozen before the data was fetched, but forecasts were computed after the matches, and only the first weeks are covered (',
        fmtDay(day(season.earliest_date)), ' to ', fmtDay(day(season.latest_date)), ').']),
      frag([el('strong', { text: 'T2 is marginal. ' }), 'Its upper bound is ', claim('l10_015'), ', only just below zero.']),
      frag([el('strong', { text: 'The gain is concentrated in newcomer matches. ' }), 'T1 difference ', claim('l10_020'), ' on ', claim('l10_004'),
        ' matches with a newly arrived team, against ', claim('l10_022'), ' on the other ', claim('l10_005'), '.']),
      frag([el('strong', { text: 'The closing market is still ahead. ' }), 'On 2026-27 the final model\'s log-loss is ', claim('l10_025'),
        ' worse than closing odds, which use later information.']),
      frag([el('strong', { text: 'The forward test is too small for inference. ' }), String(forward.length) + ' forecasts logged, ' + scored +
        ' scored; below the pre-registered minimum it is descriptive only.'])
    ];
    var ul = document.getElementById('caveats');
    items.forEach(function (f) { ul.appendChild(el('li', null, [f])); });
  }

  // ---------------------------------------------------------------- season
  function renderAggregate() {
    var box = document.getElementById('aggregate');
    var rows = [['Baseline', 'l10_008', ''], ['P1', 'l10_007', ''], ['Final model', 'l10_012', 'final'], ['Closing market', 'l10_024', 'market']];
    var vals = rows.map(function (r) { return parseFloat(C[r[1]]); });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad = (hi - lo) * 0.15;
    box.appendChild(el('h3', { text: 'Mean log-loss on the ' + C.l10_002 + ' matches' }));
    box.appendChild(el('p', { class: 'note', text: 'Lower is better. Bars show position between the best and worst value, not size from zero.' }));
    var wrap = el('div', { class: 'agg-rows' });
    rows.forEach(function (r, i) {
      var w = 100 * (vals[i] - lo + pad) / (hi - lo + pad);
      wrap.appendChild(el('div', { class: 'agg-row ' + r[2] }, [
        el('span', { text: r[0] }), el('span', { class: 'agg-bar', 'aria-hidden': 'true' }, [el('i', { style: 'width:' + w.toFixed(1) + '%' })]),
        el('span', { class: 'num' }, [claim(r[1])])
      ]));
    });
    box.appendChild(wrap);
    box.appendChild(el('div', { class: 'agg-tests' }, [
      el('p', null, [frag([el('strong', { text: 'T1, P1 vs baseline: ' }), claim('l10_009'), ' ', claimInterval('l10_010', 'l10_011'), ', accepted.'])]),
      el('p', null, [frag([el('strong', { text: 'T2, final model vs P1: ' }), claim('l10_013'), ' ', claimInterval('l10_014', 'l10_015'), ', accepted, marginal.'])]),
      el('p', { class: 'note' }, [frag(['Intervals are ', claim('l10_006'), ' paired bootstrap intervals. Market odds are a benchmark only.'])])
    ]));
  }

  function renderBlind(s) {
    var dl = document.getElementById('blind');
    var pre = s.manifest_preregistration;
    function row(t, d) { dl.appendChild(el('dt', { text: t })); dl.appendChild(el('dd', null, [d])); }
    row('Pre-registration committed', frag([el('code', { text: pre.path }), ' at commit ', el('code', { text: s.preregistration_commit.slice(0, 12) })]));
    row('Season data fetched (UTC)', el('span', { text: fmtStamp(s.fetched_at_utc) }));
    row('Frozen model file, self-hash', el('code', { text: s.p2_frozen_sha256.slice(0, 16) + '…' }));
    row('Snapshot rows, sha256', el('code', { text: s.rows_sha256.slice(0, 16) + '…' }));
    var same = pre.commit === s.preregistration_commit;
    dl.appendChild(el('dd', { class: 'verdict-line', text: same
      ? 'The manifest and the scoring file name the same pre-registration commit. Run git log on it to see that it predates the fetch time above.'
      : 'Warning: the manifest and the scoring file name different pre-registration commits.' }));
  }

  var state = { shown: PAGE, list: [] };
  function initSeason(matches) {
    matches = matches.slice().sort(function (a, b) { return a.datetime < b.datetime ? 1 : a.datetime > b.datetime ? -1 : 0; });
    var fl = document.getElementById('f-league'), ft = document.getElementById('f-team');
    var ff = document.getElementById('f-from'), fto = document.getElementById('f-to');
    var fo = document.getElementById('f-outcome'), fq = document.getElementById('f-q');
    var leagues = [], seen = {};
    matches.forEach(function (r) { if (!seen[r.league]) { seen[r.league] = 1; leagues.push(r.league); } });
    leagues.sort().forEach(function (l) { fl.appendChild(el('option', { value: l, text: l })); });
    var days = matches.map(function (r) { return day(r.datetime); }).sort();
    [ff, fto].forEach(function (i) { i.min = days[0]; i.max = days[days.length - 1]; });

    function fillTeams() {
      var keep = ft.value, names = {};
      matches.forEach(function (r) { if (!fl.value || r.league === fl.value) { names[r.home] = 1; names[r.away] = 1; } });
      ft.length = 1;
      Object.keys(names).sort().forEach(function (n) { ft.appendChild(el('option', { value: n, text: n })); });
      ft.value = names[keep] ? keep : '';
    }
    function apply() {
      var q = fq.value.trim().toLowerCase();
      state.list = matches.filter(function (r) {
        var d = day(r.datetime);
        if (fl.value && r.league !== fl.value) return false;
        if (ft.value && r.home !== ft.value && r.away !== ft.value) return false;
        if (ff.value && d < ff.value) return false;
        if (fto.value && d > fto.value) return false;
        if (q && r.home.toLowerCase().indexOf(q) < 0 && r.away.toLowerCase().indexOf(q) < 0) return false;
        if (fo.value) {
          var hit = argmax(r.M2) === outcome(r.goals_home, r.goals_away);
          if ((fo.value === 'hit') !== hit) return false;
        }
        return true;
      });
      state.shown = PAGE;
      draw();
    }
    fl.addEventListener('change', function () { fillTeams(); apply(); });
    [ft, ff, fto, fo].forEach(function (i) { i.addEventListener('change', apply); });
    fq.addEventListener('input', apply);
    document.getElementById('filters').addEventListener('reset', function () { setTimeout(function () { fillTeams(); apply(); }, 0); });
    document.getElementById('more').addEventListener('click', function () {
      var first = state.shown; state.shown += PAGE; draw();
      var next = document.querySelectorAll('#matches > li')[first];
      if (next) next.focus();
    });
    fillTeams(); apply();
    document.getElementById('match-count').dataset.total = String(matches.length);
  }

  function matchItem(r) {
    var act = outcome(r.goals_home, r.goals_away), pick = argmax(r.M2), hit = pick === act;
    var models = el('div', { class: 'models' }, [
      el('div', { class: 'model-row final' }, [el('span', { class: 'who', text: 'Final model' }), strip(r.M2, '', act)]),
      el('div', { class: 'model-row' }, [el('span', { class: 'who', text: 'Baseline' }), strip(r.M0, 'small', act)]),
      r.M4 ? el('div', { class: 'model-row' }, [el('span', { class: 'who', text: 'Closing market' }), strip(r.M4, 'small', act)])
           : el('div', { class: 'model-row' }, [el('span', { class: 'who', text: 'Closing market' }), el('span', { class: 'note', text: 'no odds for this match' })])
    ]);
    var left = el('div', null, [
      el('div', { class: 'match-meta' }, [fmtStamp(r.datetime) + ', ' + r.league, r.newcomer ? el('span', { class: 'tag', text: 'newcomer' }) : null]),
      el('div', { class: 'fixture' }, [
        el('span', { class: 't h', text: r.home }), el('span', { class: 'sc', text: r.goals_home + '–' + r.goals_away }), el('span', { class: 't', text: r.away })
      ]),
      el('p', { class: 'pick ' + (hit ? 'hit' : 'miss'),
        text: (hit ? 'Hit: ' : 'Miss: ') + 'the final model\'s most likely outcome was a ' + OUT[pick] + ' (' + pct(r.M2[pick]) + '); it gave the result ' + pct(r.M2[act]) + '.' })
    ]);
    return el('li', { class: 'match', tabindex: '-1', 'aria-label': r.home + ' ' + r.goals_home + ', ' + r.away + ' ' + r.goals_away }, [left, models]);
  }

  function draw() {
    var ol = document.getElementById('matches');
    ol.textContent = '';
    var list = state.list, n = Math.min(state.shown, list.length);
    for (var i = 0; i < n; i++) ol.appendChild(matchItem(list[i]));
    if (!list.length) ol.appendChild(el('li', { class: 'empty', text: 'No match fits these filters. Clear a filter to see more.' }));
    var total = document.getElementById('match-count').dataset.total || String(DATA.season.matches.length);
    document.getElementById('match-count').textContent = list.length === +total
      ? total + ' matches, showing ' + n
      : list.length + ' of ' + total + ' matches, showing ' + n;
    var more = document.getElementById('more');
    more.hidden = n >= list.length;
  }

  // ---------------------------------------------------------------- ratings
  function initRatings(R) {
    var sel = document.getElementById('r-league'), sort = document.getElementById('r-sort');
    R.leagues.forEach(function (l, i) { sel.appendChild(el('option', { value: String(i), text: l.league })); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-bar-label]'), function (s) { s.textContent = 'bars: ' + R.bar_label; });
    document.getElementById('r-interval').textContent = 'Bar: ' + R.interval + '. Dashed line: league average (1.00).';
    var ex = document.getElementById('r-excluded');
    ex.appendChild(el('h3', { text: 'Excluded teams' }));
    var ul = el('ul');
    R.excluded.forEach(function (x) { ul.appendChild(el('li', { text: x.team + ' (' + x.league + '): ' + x.reason })); });
    if (!R.excluded.length) ul.appendChild(el('li', { text: 'None.' }));
    ex.appendChild(ul);

    function plot(cls, f, low, high, scale, label) {
      var pos = function (v) { return (100 * scale(v)).toFixed(2) + '%'; };
      return el('div', { class: 'iv ' + cls, role: 'img', title: R.bar_label,
        'aria-label': label + ' ' + f.toFixed(2) + ', range ' + low.toFixed(2) + ' to ' + high.toFixed(2) + ' (' + R.bar_label + ')' }, [
        el('div', { class: 'axis' }, [
          el('span', { class: 'one', style: 'left:' + pos(1) }),
          el('span', { class: 'rng', style: 'left:' + pos(low) + ';width:calc(' + pos(high) + ' - ' + pos(low) + ')' }),
          el('span', { class: 'dot', style: 'left:' + pos(f) })
        ]),
        el('span', { class: 'v', text: f.toFixed(2) })
      ]);
    }
    function logScale(lo, hi) { var a = Math.log(lo), b = Math.log(hi); return function (v) { return (Math.log(v) - a) / (b - a); }; }

    function render() {
      var L = R.leagues[+sel.value];
      document.getElementById('r-note').textContent = L.defence_bar_note;
      var teams = L.teams.slice();
      var key = { overall: 'rank_overall', attack: 'rank_attack', defence: 'rank_defence' }[sort.value];
      teams.sort(function (a, b) { return a[key] - b[key]; });
      var aLo = Math.min.apply(null, teams.map(function (t) { return t.attack_low; }).concat([1]));
      var aHi = Math.max.apply(null, teams.map(function (t) { return t.attack_high; }).concat([1]));
      var dLo = Math.min.apply(null, teams.map(function (t) { return t.defence_low; }).concat([1]));
      var dHi = Math.max.apply(null, teams.map(function (t) { return t.defence_high; }).concat([1]));
      var sa = logScale(aLo, aHi), sd = logScale(dLo, dHi);
      var tb = document.querySelector('#ratings-table tbody');
      tb.textContent = '';
      teams.forEach(function (t) {
        tb.appendChild(el('tr', null, [
          el('th', { scope: 'row', class: 'team-cell' }, [el('span', { class: 'rank', text: String(t[key]) }), t.team,
            t.newcomer ? el('span', { class: 'tag', text: 'newcomer' }) : null]),
          el('td', { class: 'n', text: t.matches_2026_27 + ' / ' + t.matches_total }),
          el('td', null, [plot('att', t.attack_factor, t.attack_low, t.attack_high, sa, 'Attack')]),
          el('td', null, [plot('def', t.defence_factor, t.defence_low, t.defence_high, sd, 'Defence')])
        ]));
      });
    }
    sel.addEventListener('change', render);
    sort.addEventListener('change', render);
    render();
  }

  // ---------------------------------------------------------------- matchup
  function initMatchup(R, c, samples, snapshot) {
    var badge = document.getElementById('parity');
    var res;
    try { res = F.parity(samples, c, PARITY_TOL); } catch (e) { res = { ok: false, failures: [String(e)] }; }
    badge.textContent = res.ok
      ? 'Parity check passed: ' + samples.length + ' committed forecasts reproduced to within 1e-9'
      : 'Parity check failed: ' + res.failures.length + ' value(s) differ from the committed forecasts';
    badge.className = 'parity ' + (res.ok ? 'ok' : 'bad');
    if (!res.ok) console.warn('parity failures', res.failures);

    var s = snapshot;
    document.getElementById('matchup-label').textContent = 'Computed from ratings as of the snapshot date (' +
      fmtDay(s.slice(0, 4) + '-' + s.slice(4, 6) + '-' + s.slice(6, 8)) + '); not a logged forecast.';

    var fl = document.getElementById('m-league'), fh = document.getElementById('m-home'), fa = document.getElementById('m-away');
    R.leagues.forEach(function (l, i) { fl.appendChild(el('option', { value: String(i), text: l.league })); });
    function teams() { return R.leagues[+fl.value].teams.slice().sort(function (a, b) { return a.team < b.team ? -1 : 1; }); }
    function fill() {
      var ts = teams();
      [fh, fa].forEach(function (s) { s.textContent = ''; ts.forEach(function (t, i) { s.appendChild(el('option', { value: t.team, text: t.team })); }); });
      var byRank = R.leagues[+fl.value].teams.slice().sort(function (a, b) { return a.rank_overall - b.rank_overall; });
      fh.value = byRank[0].team; fa.value = byRank[1].team;
    }
    function find(name) { return R.leagues[+fl.value].teams.filter(function (t) { return t.team === name; })[0]; }
    function render() {
      var out = document.getElementById('m-out');
      out.textContent = '';
      if (fh.value === fa.value) { out.appendChild(el('p', { class: 'empty', text: 'Pick two different teams.' })); return; }
      var home = find(fh.value), away = find(fa.value);
      var rt = F.rates(home, away, c), fc = F.forecast(rt[0], rt[1], c), m = fc.markets;
      var names = [home.team + ' win', 'draw', away.team + ' win'];
      var card1 = el('div', { class: 'mo-card' }, [
        el('div', { class: 'mo-teams' }, [el('span', { class: 't', text: home.team }), el('span', { class: 'vs', text: 'home v away' }), el('span', { class: 't a', text: away.team })]),
        strip([m.home, m.draw, m.away], 'big', null, names),
        el('dl', { class: 'mo-facts' }, [
          fact(home.team + ' win', pct1(m.home)), fact('Draw', pct1(m.draw)), fact(away.team + ' win', pct1(m.away)),
          fact('Expected goals', m.xg_home.toFixed(2) + ' – ' + m.xg_away.toFixed(2)),
          fact('Over ' + c.markets.over_line + ' goals', pct1(m.over_2_5)), fact('Both teams score', pct1(m.btts))
        ]),
        el('h3', { text: 'Most likely scorelines', style: 'margin-top:1.2rem' }),
        top5(m.top_scorelines, home.team, away.team)
      ]);
      out.appendChild(card1);
      out.appendChild(el('div', { class: 'mo-card' }, [gridTable(fc.grid, home.team, away.team, c.grid.market_max_goals)]));
    }
    function fact(t, v) { return el('div', null, [el('dt', { text: t }), el('dd', { text: v })]); }
    function top5(list, h, a) {
      var max = list[0].p, ol = el('ol', { class: 'top5' });
      list.forEach(function (x) {
        ol.appendChild(el('li', { 'aria-label': h + ' ' + x.home_goals + ', ' + a + ' ' + x.away_goals + ': ' + pct1(x.p) }, [
          el('span', { class: 'num', text: x.home_goals + '–' + x.away_goals }),
          el('span', { class: 'bar', 'aria-hidden': 'true' }, [el('i', { style: 'width:' + (100 * x.p / max).toFixed(1) + '%' })]),
          el('span', { class: 'num', text: pct1(x.p) })
        ]));
      });
      return ol;
    }
    function gridTable(grid, h, a, maxGoals) {
      var show = 6, max = 0;
      for (var i = 0; i <= show; i++) for (var j = 0; j <= show; j++) max = Math.max(max, grid[i][j]);
      var t = el('table', { class: 'sgrid' });
      t.appendChild(el('caption', { text: 'Scoreline probabilities, ' + h + ' goals down, ' + a + ' goals across (shown to ' + show + '; computed to ' + maxGoals + ')' }));
      var hr = el('tr', null, [el('th', { scope: 'col', text: '' })]);
      for (j = 0; j <= show; j++) hr.appendChild(el('th', { scope: 'col', text: String(j) }));
      t.appendChild(el('thead', null, [hr]));
      var tb = el('tbody');
      var dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
        (!document.documentElement.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
      for (i = 0; i <= show; i++) {
        var tr = el('tr', null, [el('th', { scope: 'row', text: String(i) })]);
        for (j = 0; j <= show; j++) {
          var p = grid[i][j], k = p / max;
          var col = i > j ? '11,110,95' : i === j ? '115,107,96' : '122,46,82';
          if (dark) col = i > j ? '63,181,158' : i === j ? '165,158,146' : '215,121,159';
          var strong = k > 0.55;
          tr.appendChild(el('td', { style: 'background:rgba(' + col + ',' + (0.08 + 0.85 * k).toFixed(3) + ');' + (strong ? 'color:' + (dark ? '#0e1613' : '#fff') + ';' : ''),
            text: (p * 100).toFixed(1) }));
        }
        tb.appendChild(tr);
      }
      t.appendChild(tb);
      return el('div', { class: 'grid-wrap' }, [t]);
    }
    fl.addEventListener('change', function () { fill(); render(); });
    fh.addEventListener('change', render);
    fa.addEventListener('change', render);
    document.getElementById('m-swap').addEventListener('click', function () { var x = fh.value; fh.value = fa.value; fa.value = x; render(); });
    document.getElementById('theme-toggle').addEventListener('click', render);
    fill(); render();
  }

  // ---------------------------------------------------------------- forward
  function renderForward(rows) {
    var scored = rows.filter(function (r) { return r.scored; }).length;
    var logged = rows.map(function (r) { return r.logged_at_utc; }).sort();
    document.getElementById('forward-intro').textContent = rows.length + ' forecasts have been logged' +
      (logged.length ? ' since ' + fmtStamp(logged[0]) + ' UTC' : '') + ', each before kickoff, in an append-only, hash-chained file. ' +
      'Scored so far: ' + scored + '. Below the pre-registered minimum of scored matches the forward test is descriptive only, and no inference is drawn from it.';
    var tb = document.querySelector('#forward-table tbody');
    rows.slice().sort(function (a, b) { return a.kickoff_utc < b.kickoff_utc ? -1 : 1; }).forEach(function (r) {
      tb.appendChild(el('tr', null, [
        el('td', { class: 'n', text: fmtStamp(r.kickoff_utc) }),
        el('th', { scope: 'row' }, [r.home + ' v ' + r.away, el('span', { class: 'sub', text: r.league })]),
        el('td', null, [strip(r.base, 'small')]), el('td', null, [strip(r.p1, 'small')]),
        el('td', { class: 'n', text: fmtStamp(r.logged_at_utc) })
      ]));
    });
  }

  // ---------------------------------------------------------------- methods claims
  function fillClaimSpans() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-claim]'), function (s) {
      var id = s.getAttribute('data-claim');
      s.textContent = minus(C[id]); s.title = 'results/claims.json: ' + id;
    });
  }

  // ---------------------------------------------------------------- boot
  initTheme();
  initNav();
  fetch('data.json').then(function (r) {
    if (!r.ok) throw new Error('data.json: HTTP ' + r.status);
    return r.json();
  }).then(function (d) {
    DATA = d; C = d.claims;
    renderHero(d.season.matches);
    renderResults();
    renderCaveats(d.season, d.forward);
    renderAggregate();
    renderBlind(d.season);
    initSeason(d.season.matches);
    initRatings(d.ratings);
    initMatchup(d.ratings, d.constants, d.samples, d.constants.snapshot_date);
    renderForward(d.forward);
    fillClaimSpans();
  }).catch(function (e) {
    console.error(e);
    var m = document.getElementById('main');
    m.insertBefore(el('p', { class: 'empty', role: 'alert', text: 'Could not load data.json (' + e.message + '). Serve the folder with: python -m http.server -d site 8000' }), m.firstChild);
  });
})();
