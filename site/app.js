// B12 site: renders data.json (built by build_data.py). No figure is typed here: headline values come from
// data.claims (results/claims.json by id), everything else from per-match or per-team rows.
(function () {
  'use strict';
  var F = window.B12Forecast;
  var PARITY_TOL = 1e-9;
  var PAGE_SIZES = [5, 10, 20];
  var VIEWS = ['home', 'project', 'overview', 'season', 'ratings', 'matchup', 'methods', 'conclusion'];
  var EASE_OUT = 'cubic-bezier(.22,1,.36,1)';
  var NEWCOMER_TIP = 'A newcomer is a team playing in 2026-27 that appears in no earlier match in the data, so the model ' +
    'starts it from a preset rating instead of its history.';
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  // ---------------------------------------------------------------- helpers
  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'class') n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function animate(node, frames, opts) {
    if (reduceMotion.matches || !node.animate) return { finished: Promise.resolve() };
    var a = node.animate(frames, opts);
    a.finished.catch(function () { /* cancelled */ });
    // Never leave content hidden if frames stop (throttled tab): finish late animations.
    setTimeout(function () { if (a.playState === 'running') a.finish(); }, (opts.delay || 0) + opts.duration + 400);
    return a;
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

  // The three-way forecast strip; setStrip updates it in place so widths can glide.
  function strip(p, cls, actual, names) {
    var s = el('div', { class: 'strip' + (cls ? ' ' + cls : ''), role: 'img' });
    ['h', 'd', 'a'].forEach(function (c) { s.appendChild(el('span', { class: c })); });
    setStrip(s, p, actual, names);
    return s;
  }
  function setStrip(s, p, actual, names) {
    names = names || OUT;
    s.setAttribute('aria-label', names.map(function (n, i) { return n + ' ' + pct(p[i]); }).join(', ') +
      (actual != null ? '; actual: ' + names[actual] : ''));
    Array.prototype.forEach.call(s.children, function (seg, i) {
      seg.style.width = (100 * p[i]).toFixed(3) + '%';
      seg.classList.toggle('actual', actual === i);
      seg.textContent = p[i] >= 0.12 ? pct(p[i]) : '';
    });
  }
  var GLOSSARY = {
    baseline: 'Baseline: the Stage 2 sequential Bayesian filter with its original settings, the starting point every improvement is measured against.',
    p1: 'P1, version 1 of the learned filter: the baseline with its uncertainty settings tuned on past seasons, a careful start for new teams and a low-score correction.',
    p2: 'P2, version 2 of the learned filter: P1 plus finer tuning and shots on target in the rating update. P2 is the final model.',
    final: 'Final model: P2, the version of the filter used for every forecast on this site.',
    market: 'Closing market: bookmakers\' closing odds turned into probabilities. They use information up to kickoff, so they serve as a benchmark.',
    t1: 'T1, test 1 on the 2026-27 matches: does P1 forecast better than the baseline?',
    t2: 'T2, test 2 on the 2026-27 matches: does the final model forecast better than P1?',
    stage1: 'Static Dixon-Coles (Stage 1): a classic model that fits fixed team strengths once, weighting recent matches more.',
    filter: 'Sequential filter (Stage 2): ratings held as Gaussian beliefs and updated after every match.',
    gateb: 'Gate B: the pre-registered test of whether starting-XI market values improve the ratings.',
    pp: 'Posterior-predictive forecast: averaging the forecast over each rating\'s uncertainty, instead of using its best guess (the plug-in forecast).',
    test: 'TEST window: matches from February 2025 to May 2026, held out from all tuning.'
  };
  function term(label, key) {
    return el('button', { type: 'button', class: 'tip term', 'data-tip': GLOSSARY[key] }, [label]);
  }
  function newcomerTag() {
    return el('button', { type: 'button', class: 'tag tip', 'data-tip': NEWCOMER_TIP, 'aria-label': 'Newcomer: what does this mean?' }, ['newcomer']);
  }

  var DATA, C;
  function claim(id) {
    if (!(id in C)) throw new Error('unknown claim ' + id);
    return el('span', { class: 'claim', text: minus(C[id]) });
  }
  function frag(parts) {
    var f = document.createDocumentFragment();
    parts.forEach(function (p) { f.appendChild(typeof p === 'string' ? document.createTextNode(p) : p); });
    return f;
  }
  function claimInterval(lo, hi) { return frag(['[', claim(lo), ', ', claim(hi), ']']); }

  // ---------------------------------------------------------------- theme
  function initTheme() {
    var btn = $('theme-toggle'), root = document.documentElement, stored = null;
    try { stored = localStorage.getItem('b12-theme'); } catch (e) { /* storage unavailable */ }
    if (stored === 'dark' || stored === 'light') root.setAttribute('data-theme', stored);
    function isDark() {
      var t = root.getAttribute('data-theme');
      return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    function label() { btn.textContent = isDark() ? 'Light mode' : 'Dark mode'; btn.setAttribute('aria-pressed', String(isDark())); }
    btn.addEventListener('click', function () {
      var next = isDark() ? 'light' : 'dark';
      root.classList.add('theme-fade');
      root.setAttribute('data-theme', next);
      setTimeout(function () { root.classList.remove('theme-fade'); }, 450);
      try { localStorage.setItem('b12-theme', next); } catch (e) { /* storage unavailable */ }
      label();
    });
    label();
  }

  // ---------------------------------------------------------------- views and navigation
  var router = { current: null, token: 0 };
  var TITLES = { home: 'Start', project: 'Project', conclusion: 'Conclusion', overview: 'Overview', season: '2026-27 season', ratings: 'Team ratings',
                 matchup: 'Matchup', methods: 'Methods' };

  function viewEl(name) { return document.querySelector('.view[data-view="' + name + '"]'); }
  function routeName() {
    var h = location.hash.replace(/^#\/?/, '');
    return VIEWS.indexOf(h) >= 0 ? h : 'home';
  }
  function moveIndicator(name, instant) {
    var nav = document.querySelector('.tabs'), ind = nav.querySelector('.tab-indicator');
    var link = nav.querySelector('a[href="#' + name + '"]');
    nav.querySelectorAll('a').forEach(function (a) { a.toggleAttribute('aria-current', a === link); if (a === link) a.setAttribute('aria-current', 'page'); });
    if (!link) { ind.style.opacity = '0'; return; }
    if (instant) ind.style.transition = 'none';
    ind.style.opacity = '1';
    ind.style.width = link.offsetWidth + 'px';
    ind.style.transform = 'translateX(' + link.offsetLeft + 'px)';
    if (instant) { void ind.offsetWidth; ind.style.transition = ''; }
    var left = link.offsetLeft - (nav.clientWidth - link.offsetWidth) / 2;
    if (nav.scrollWidth > nav.clientWidth) nav.scrollTo({ left: left, behavior: instant || reduceMotion.matches ? 'auto' : 'smooth' });
  }
  function renderPager(name) {
    var pager = $('pager');
    pager.textContent = '';
    var i = VIEWS.indexOf(name);
    if (name === 'home') { pager.hidden = true; return; }
    pager.hidden = false;
    var prev = VIEWS[i - 1], next = VIEWS[i + 1];
    pager.appendChild(el('a', { class: 'pager-link prev', href: '#' + prev }, [el('span', { class: 'pager-dir', text: 'Previous' }), el('span', { class: 'pager-name', text: TITLES[prev] })]));
    if (next) pager.appendChild(el('a', { class: 'pager-link next', href: '#' + next }, [el('span', { class: 'pager-dir', text: 'Next' }), el('span', { class: 'pager-name', text: TITLES[next] })]));
  }
  function show(name, first) {
    var from = router.current ? viewEl(router.current) : null, to = viewEl(name);
    if (from === to) return;
    var token = ++router.token;
    moveIndicator(name, first);
    function enter() {
      if (token !== router.token) return;
      VIEWS.forEach(function (v) { viewEl(v).hidden = v !== name; });
      router.current = name;
      renderPager(name);
      window.scrollTo(0, 0);
      document.title = name === 'home' ? 'SCAF Football Forecasts' : TITLES[name] + ', SCAF';
      if (!first) { var h = to.querySelector('[tabindex="-1"]'); if (h) h.focus({ preventScroll: true }); }
      animate(to, [{ opacity: 0, transform: 'translateY(18px)' }, { opacity: 1, transform: 'none' }], { duration: 520, easing: EASE_OUT });
      animate($('pager'), [{ opacity: 0 }, { opacity: 1 }], { duration: 600, delay: 160, easing: EASE_OUT, fill: 'backwards' });
      if (name === 'ratings' || name === 'matchup' || name === 'season') document.dispatchEvent(new CustomEvent('b12:view', { detail: name }));
    }
    if (from && !first && from.getAnimations) from.getAnimations().forEach(function (a) { a.cancel(); });
    if (from && !first) {
      var out = animate(from, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-8px)' }], { duration: 170, easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards' });
      // A throttled tab can stall animation promises; the timer makes sure the swap always happens.
      Promise.race([out.finished.catch(function () { /* cancelled by a newer navigation */ }), new Promise(function (r) { setTimeout(r, 220); })]).then(function () {
        if (token !== router.token) return;
        enter();
        if (from.getAnimations) from.getAnimations().forEach(function (a) { a.cancel(); });
      });
    } else enter();
  }
  function initRouter() {
    window.addEventListener('hashchange', function () { show(routeName()); });
    window.addEventListener('resize', function () { moveIndicator(router.current, true); });
    show(routeName(), true);
    if (router.current === 'home') {
      var homeView = document.querySelector('.view[data-view="home"]');
      homeView.classList.add('intro');
      // Drop the entrance once it should be over, so a stalled animation never leaves the page faded.
      setTimeout(function () { homeView.classList.remove('intro'); }, 1800);
    }
  }

  // ---------------------------------------------------------------- popover
  function initPopover() {
    var pop = $('pop'), owner = null, hideTimer = null;
    function place(t) {
      var r = t.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
      var left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
      var top = r.top - h - 10, below = top < 8;
      if (below) top = r.bottom + 10;
      pop.style.left = left + 'px'; pop.style.top = top + 'px';
      pop.classList.toggle('below', below);
      pop.style.setProperty('--arrow', (r.left + r.width / 2 - left) + 'px');
    }
    function open(t) {
      clearTimeout(hideTimer);
      if (owner && owner !== t) owner.removeAttribute('aria-describedby');
      owner = t;
      pop.textContent = t.getAttribute('data-tip');
      pop.hidden = false;
      place(t);
      t.setAttribute('aria-describedby', 'pop');
      requestAnimationFrame(function () { pop.classList.add('show'); });
    }
    function close() {
      if (!owner) return;
      owner.removeAttribute('aria-describedby');
      owner = null;
      pop.classList.remove('show');
      hideTimer = setTimeout(function () { pop.hidden = true; }, 200);
    }
    document.addEventListener('mouseover', function (e) { var t = e.target.closest && e.target.closest('.tip'); if (t) open(t); });
    document.addEventListener('mouseout', function (e) { var t = e.target.closest && e.target.closest('.tip'); if (t && t === owner && !t.contains(e.relatedTarget)) close(); });
    document.addEventListener('focusin', function (e) { if (e.target.classList && e.target.classList.contains('tip')) open(e.target); });
    document.addEventListener('focusout', function (e) { if (e.target === owner) close(); });
    document.addEventListener('click', function (e) {
      var t = e.target.closest && e.target.closest('.tip');
      if (t) { if (owner === t && pop.classList.contains('show') && e.detail) close(); else open(t); } else close();
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    window.addEventListener('scroll', function () { if (owner) place(owner); }, { passive: true });
  }

  // ---------------------------------------------------------------- overview
  function renderResults() {
    var rows = [
      { what: frag([term('Static Dixon-Coles', 'stage1'), ' vs the ', term('sequential filter', 'filter'), ' (RPS, lower is better)']),
        data: frag([term('TEST window', 'test'), ', ', claim('c019'), ' common matches']),
        diff: frag([claim('c020'), ' vs ', claim('c023')]), iv: '', verdict: ['Filter matches the static model while updating live', 'info'] },
      { what: frag(['Learned filter (', term('P1', 'p1'), ') vs ', term('baseline', 'baseline')]),
        data: frag([term('TEST window', 'test'), ', ', claim('c008'), ' matches (retrospective holdout)']),
        diff: claim('c124'), iv: claimInterval('c125', 'c126'), verdict: ['Accepted', 'pass'] },
      { what: frag([term('P1', 'p1'), ' vs ', term('baseline', 'baseline'), ', replication']),
        data: frag(['Four untouched seasons 2015-16 to 2018-19, ', claim('p2_003'), ' matches']),
        diff: claim('p2_027'), iv: frag([claim('p2_026'), ' ', claimInterval('p2_028', 'p2_029')]), verdict: ['Replicated', 'pass'] },
      { what: frag([term('Final model', 'final'), ' (', term('P2', 'p2'), ') vs ', term('P1', 'p1')]),
        data: 'Same fresh seasons',
        diff: claim('p2_032'), iv: frag([claim('p2_026'), ' ', claimInterval('p2_033', 'p2_034')]), verdict: ['Replicated', 'pass'] },
      { what: frag([term('P1', 'p1'), ' vs ', term('baseline', 'baseline'), ' (', term('T1', 't1'), ')']),
        data: frag(['2026-27, ', claim('l10_002'), ' completed matches, frozen parameters']),
        diff: claim('l10_009'), iv: frag([claim('l10_006'), ' ', claimInterval('l10_010', 'l10_011')]), verdict: ['Accepted', 'pass'] },
      { what: frag([term('Final model', 'final'), ' vs ', term('P1', 'p1'), ' (', term('T2', 't2'), ')']),
        data: 'Same 2026-27 matches',
        diff: claim('l10_013'), iv: frag([claim('l10_006'), ' ', claimInterval('l10_014', 'l10_015')]), verdict: ['Accepted', 'pass'] },
      { what: frag([term('Posterior-predictive forecast', 'pp'), ' vs plug-in forecast']),
        data: 'Development and validation windows',
        diff: 'Plug-in better on both', iv: frag([claim('pp_007'), ' ', claimInterval('pp_012', 'pp_013')]), verdict: ['Plug-in forecast confirmed', 'info'] },
      { what: frag(['Lineup weighting, defence term (', term('Gate B', 'gateb'), ')']),
        data: 'Training data',
        diff: claim('c050'), iv: claimInterval('c051', 'c052'), verdict: ['Model runs without a lineup feed', 'info'] },
      { what: 'Model stacked with market odds vs odds alone',
        data: 'Development and validation windows',
        diff: '', iv: frag([claim('p2_004'), ' ', claimInterval('p2_023', 'p2_024')]), verdict: ['Model stays independent of the market', 'info'] }
    ];
    var tb = document.querySelector('#results-table tbody');
    rows.forEach(function (r) {
      function cell2(x) { var th = el('th', { scope: 'row' }); if (typeof x === 'string') th.textContent = x; else th.appendChild(x); return th; }
      function cell(x, cls) { var td = el('td', cls ? { class: cls } : null); if (typeof x === 'string') td.textContent = x; else td.appendChild(x); return td; }
      tb.appendChild(el('tr', null, [
        cell2(r.what), cell(r.data), cell(r.diff, 'n'), cell(r.iv, 'n'),
        el('td', { class: 'verdict ' + r.verdict[1], text: r.verdict[0] })
      ]));
    });
  }

  function renderCaveats(season) {
    var items = [
      frag([el('strong', { text: 'Both novelties became design insights. ' }), 'Validation showed the Bayesian update already reacts to surprises, so no extra surprise term is needed. Lineup values showed a clear attack effect, ',
        claim('c047'), ', while the defence effect centred on ', claim('c050'), ', so the model runs without a lineup feed.']),
      frag([el('strong', { text: 'The plug-in forecast is confirmed. ' }), 'Forecasting from each rating\'s best guess beat averaging over its uncertainty, interval ',
        claimInterval('pp_012', 'pp_013'), '.']),
      frag([el('strong', { text: '2026-27 is an early-season check. ' }), 'Parameters were frozen before the data was fetched and forecasts were computed after the matches, covering the opening weeks (',
        fmtDay(day(season.earliest_date)), ' to ', fmtDay(day(season.latest_date)), ').']),
      frag([el('strong', { text: 'Biggest gains for new arrivals. ' }), term('T1', 't1'), ' difference ', claim('l10_020'), ' on ', claim('l10_004'),
        ' matches with a newly arrived team, and ', claim('l10_022'), ' on the other ', claim('l10_005'), '.']),
      frag([el('strong', { text: 'Closing in on the market. ' }), 'On 2026-27 the ', term('final model', 'final'), ' is within ', claim('l10_025'),
        ' log-loss of ', term('closing odds', 'market'), ', which use information right up to kickoff.'])
    ];
    var ul = $('caveats');
    items.forEach(function (f) { ul.appendChild(el('li', null, [f])); });
  }

  // ---------------------------------------------------------------- season
  function renderAggregate() {
    var box = $('aggregate');
    var rows = [['Baseline', 'l10_008', '', 'baseline'], ['P1', 'l10_007', '', 'p1'], ['Final model', 'l10_012', 'final', 'final'], ['Closing market', 'l10_024', 'market', 'market']];
    var vals = rows.map(function (r) { return parseFloat(C[r[1]]); });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad = (hi - lo) * 0.15;
    box.appendChild(el('h3', { text: 'Mean log-loss on the ' + C.l10_002 + ' matches' }));
    box.appendChild(el('p', { class: 'note', text: 'Lower is better. Bars show position between the best and worst value, not size from zero.' }));
    var wrap = el('div', { class: 'agg-rows' });
    rows.forEach(function (r, i) {
      var w = 100 * (vals[i] - lo + pad) / (hi - lo + pad);
      wrap.appendChild(el('div', { class: 'agg-row ' + r[2] }, [
        el('span', null, [term(r[0], r[3])]), el('span', { class: 'agg-bar', 'aria-hidden': 'true' }, [el('i', { style: '--w:' + w.toFixed(1) + '%' })]),
        el('span', { class: 'num' }, [claim(r[1])])
      ]));
    });
    var tests = el('div', { class: 'agg-tests' }, [
      el('p', null, [frag([el('strong', null, [term('T1', 't1'), ', P1 vs baseline: ']), claim('l10_009'), ' ', claimInterval('l10_010', 'l10_011'), ', accepted.'])]),
      el('p', null, [frag([el('strong', null, [term('T2', 't2'), ', final model vs P1: ']), claim('l10_013'), ' ', claimInterval('l10_014', 'l10_015'), ', accepted.'])]),
      el('p', { class: 'note' }, [frag(['Intervals are ', claim('l10_006'), ' paired bootstrap intervals. Market odds are a benchmark only.'])])
    ]);
    box.appendChild(el('div', { class: 'agg-body' }, [wrap, tests]));
  }

  var season = { size: 10, shown: 10, list: [], total: 0 };
  function initSeason(matches) {
    matches = matches.slice().sort(function (a, b) { return a.datetime < b.datetime ? 1 : a.datetime > b.datetime ? -1 : 0; });
    season.total = matches.length;
    var fl = $('f-league'), ft = $('f-team'), ff = $('f-from'), fto = $('f-to'), fo = $('f-outcome'), fq = $('f-q');
    var leagues = [], seen = {};
    matches.forEach(function (r) { if (!seen[r.league]) { seen[r.league] = 1; leagues.push(r.league); } });
    leagues.sort().forEach(function (l) { fl.appendChild(el('option', { value: l, text: l })); });
    var days = matches.map(function (r) { return day(r.datetime); }).sort();
    [ff, fto].forEach(function (i) { i.min = days[0]; i.max = days[days.length - 1]; });

    // per-page segmented control
    var seg = $('page-size');
    PAGE_SIZES.forEach(function (n) {
      var id = 'ps-' + n;
      var input = el('input', { type: 'radio', name: 'page-size', id: id, value: String(n) });
      if (n === season.size) input.checked = true;
      seg.appendChild(input);
      seg.appendChild(el('label', { for: id, text: String(n) }));
      input.addEventListener('change', function () {
        season.size = n; season.shown = n;
        moveThumb(); draw(true);
      });
    });
    function moveThumb(instant) {
      var thumb = seg.querySelector('.seg-thumb'), lab = seg.querySelector('input:checked + label');
      if (!lab) return;
      if (instant) thumb.style.transition = 'none';
      thumb.style.width = lab.offsetWidth + 'px';
      thumb.style.transform = 'translateX(' + lab.offsetLeft + 'px)';
      if (instant) { void thumb.offsetWidth; thumb.style.transition = ''; }
    }
    document.addEventListener('b12:view', function (e) { if (e.detail === 'season') moveThumb(true); });
    window.addEventListener('resize', function () { moveThumb(true); });

    function fillTeams() {
      var keep = ft.value, names = {};
      matches.forEach(function (r) { if (!fl.value || r.league === fl.value) { names[r.home] = 1; names[r.away] = 1; } });
      ft.length = 1;
      Object.keys(names).sort().forEach(function (n) { ft.appendChild(el('option', { value: n, text: n })); });
      ft.value = names[keep] ? keep : '';
    }
    function apply() {
      var q = fq.value.trim().toLowerCase();
      season.list = matches.filter(function (r) {
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
      season.shown = season.size;
      draw(true);
    }
    fl.addEventListener('change', function () { fillTeams(); apply(); });
    [ft, ff, fto, fo].forEach(function (i) { i.addEventListener('change', apply); });
    fq.addEventListener('input', apply);
    $('filters').addEventListener('reset', function () { setTimeout(function () { fillTeams(); apply(); }, 0); });
    $('more').addEventListener('click', function () {
      var first = season.shown;
      season.shown += season.size;
      draw(false, first);
      var next = document.querySelectorAll('#matches > li')[first];
      if (next) next.focus({ preventScroll: true });
    });
    fillTeams(); apply();
    requestAnimationFrame(function () { moveThumb(true); });
  }

  function matchItem(r) {
    var act = outcome(r.goals_home, r.goals_away), pick = argmax(r.M2), hit = pick === act;
    var models = el('div', { class: 'models' }, [
      el('div', { class: 'model-row final' }, [el('span', { class: 'who' }, [term('Final model', 'final')]), strip(r.M2, '', act)]),
      el('div', { class: 'model-row' }, [el('span', { class: 'who' }, [term('Baseline', 'baseline')]), strip(r.M0, 'small', act)]),
      r.M4 ? el('div', { class: 'model-row' }, [el('span', { class: 'who' }, [term('Closing market', 'market')]), strip(r.M4, 'small', act)])
           : el('div', { class: 'model-row' }, [el('span', { class: 'who' }, [term('Closing market', 'market')]), el('span', { class: 'note', text: 'no odds for this match' })])
    ]);
    var left = el('div', null, [
      el('div', { class: 'match-meta' }, [el('span', { text: fmtStamp(r.datetime) + ', ' + r.league }), r.newcomer ? newcomerTag() : null]),
      el('div', { class: 'fixture' }, [
        el('span', { class: 't h', text: r.home }), el('span', { class: 'sc', text: r.goals_home + '–' + r.goals_away }), el('span', { class: 't', text: r.away })
      ]),
      el('p', { class: 'pick ' + (hit ? 'hit' : 'miss'),
        text: hit ? 'Favourite won: the final model made a ' + OUT[pick] + ' most likely (' + pct(r.M2[pick]) + ').'
          : 'Upset: the final model favoured a ' + OUT[pick] + ' (' + pct(r.M2[pick]) + ') and gave the ' + OUT[act] + ' ' + pct(r.M2[act]) + '.' })
    ]);
    return el('li', { class: 'match', tabindex: '-1', 'aria-label': r.home + ' ' + r.goals_home + ', ' + r.away + ' ' + r.goals_away }, [left, models]);
  }

  function draw(fresh, from) {
    var ol = $('matches'), list = season.list, n = Math.min(season.shown, list.length);
    if (fresh) { ol.textContent = ''; from = 0; }
    for (var i = from; i < n; i++) {
      var li = matchItem(list[i]);
      ol.appendChild(li);
      if (i - from < 12) animate(li, [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'none' }],
        { duration: 420, delay: (i - from) * 28, easing: EASE_OUT, fill: 'backwards' });
    }
    if (!list.length) ol.appendChild(el('li', { class: 'empty', text: 'No match fits these filters. Clear a filter to see more.' }));
    $('match-count').textContent = list.length === season.total
      ? season.total + ' matches, showing ' + n
      : list.length + ' of ' + season.total + ' matches, showing ' + n;
    $('more').hidden = n >= list.length;
    $('more').textContent = 'Show ' + Math.min(season.size, list.length - n) + ' more';
  }

  // ---------------------------------------------------------------- ratings
  var pickForMatchup = null;
  function initRatings(R) {
    var sel = $('r-league'), sort = $('r-sort');
    R.leagues.forEach(function (l, i) { sel.appendChild(el('option', { value: String(i), text: l.league })); });
    document.querySelectorAll('[data-bar-label]').forEach(function (s) { s.textContent = 'bars: ' + R.bar_label; });
    $('r-interval').textContent = 'Bar: ' + R.interval + '. Dashed line: league average (1.00).';

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
    function extent(teams, lo, hi) {
      return [Math.min.apply(null, teams.map(function (t) { return t[lo]; }).concat([1])),
              Math.max.apply(null, teams.map(function (t) { return t[hi]; }).concat([1]))];
    }
    function render() {
      var L = R.leagues[+sel.value];
      var teams = L.teams.slice();
      var key = { overall: 'rank_overall', attack: 'rank_attack', defence: 'rank_defence' }[sort.value];
      teams.sort(function (a, b) { return a[key] - b[key]; });
      teams = teams.slice(0, 5);
      var ae = extent(teams, 'attack_low', 'attack_high'), de = extent(teams, 'defence_low', 'defence_high');
      var sa = logScale(ae[0], ae[1]), sd = logScale(de[0], de[1]);
      var tb = document.querySelector('#ratings-table tbody');
      tb.textContent = '';
      teams.forEach(function (t, i) {
        var pick = el('button', { type: 'button', class: 'team-link', title: 'Use ' + t.team + ' in the matchup tool', text: t.team });
        pick.addEventListener('click', function () { if (pickForMatchup) pickForMatchup(+sel.value, t.team); location.hash = 'matchup'; });
        var tr = el('tr', null, [
          el('th', { scope: 'row', class: 'team-cell' }, [el('span', { class: 'rank', text: String(t[key]) }), pick, t.newcomer ? newcomerTag() : null]),
          el('td', { class: 'n', text: t.matches_2026_27 + ' / ' + t.matches_total }),
          el('td', null, [plot('att', t.attack_factor, t.attack_low, t.attack_high, sa, 'Attack')]),
          el('td', null, [plot('def', t.defence_factor, t.defence_low, t.defence_high, sd, 'Defence')])
        ]);
        tb.appendChild(tr);
        if (i < 14) animate(tr, [{ opacity: 0, transform: 'translateX(-8px)' }, { opacity: 1, transform: 'none' }],
          { duration: 380, delay: i * 22, easing: EASE_OUT, fill: 'backwards' });
      });
    }
    sel.addEventListener('change', render);
    sort.addEventListener('change', render);
    render();
  }

  // ---------------------------------------------------------------- matchup
  function tween(node, to, fmt) {
    var from = node._v == null ? to : node._v;
    node._v = to;
    if (reduceMotion.matches || from === to) { node.textContent = fmt(to); return; }
    var t0 = performance.now(), dur = 520;
    cancelAnimationFrame(node._raf);
    (function step(now) {
      var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 4);
      node.textContent = fmt(Array.isArray(to) ? to.map(function (v, i) { return from[i] + (v - from[i]) * e; }) : from + (to - from) * e);
      if (k < 1) node._raf = requestAnimationFrame(step);
    })(t0);
  }

  function initMatchup(R, c, samples, snapshot) {
    // Parity: the JS forecast must reproduce every committed sample forecast.
    var res;
    try { res = F.parity(samples, c, PARITY_TOL); } catch (e) { res = { ok: false, failures: [String(e)] }; }
    if (res.ok) console.info('Forecast parity: ' + samples.length + ' committed forecasts reproduced within ' + PARITY_TOL);
    else console.warn('Forecast parity failed', res.failures);

    var s = snapshot;
    $('matchup-label').textContent = 'Computed from ratings as of the snapshot date (' +
      fmtDay(s.slice(0, 4) + '-' + s.slice(4, 6) + '-' + s.slice(6, 8)) + '); not a logged forecast.';

    var hl = $('m-home-league'), al = $('m-away-league'), fh = $('m-home'), fa = $('m-away');
    [hl, al].forEach(function (sel) { R.leagues.forEach(function (l, i) { sel.appendChild(el('option', { value: String(i), text: l.league })); }); });
    function byName(li) { return R.leagues[li].teams.slice().sort(function (a, b) { return a.team < b.team ? -1 : 1; }); }
    function byRank(li) { return R.leagues[li].teams.slice().sort(function (a, b) { return a.rank_overall - b.rank_overall; }); }
    function fillTeams(sel, li, want) {
      sel.textContent = '';
      byName(li).forEach(function (t) { sel.appendChild(el('option', { value: t.team, text: t.team })); });
      sel.value = want;
    }
    function find(li, name) { return R.leagues[li].teams.filter(function (t) { return t.team === name; })[0]; }

    // persistent output so values glide between matchups
    var out = $('m-out');
    var names = { h: el('span', { class: 't' }), a: el('span', { class: 't a' }) };
    var bigStrip = strip([1 / 3, 1 / 3, 1 / 3], 'big', null);
    var facts = {}, factLabels = {};
    function fact(key, label) {
      factLabels[key] = el('dt', { text: label }); facts[key] = el('dd');
      return el('div', null, [factLabels[key], facts[key]]);
    }
    var top5 = el('ol', { class: 'top5' });
    var gridCells = [], show = 6;
    var gridCap = el('caption');
    var table = el('table', { class: 'sgrid' }, [gridCap]);
    var hr = el('tr', null, [el('th', { scope: 'col', text: '' })]);
    for (var j = 0; j <= show; j++) hr.appendChild(el('th', { scope: 'col', text: String(j) }));
    table.appendChild(el('thead', null, [hr]));
    var tbody = el('tbody');
    for (var i = 0; i <= show; i++) {
      var tr = el('tr', null, [el('th', { scope: 'row', text: String(i) })]);
      gridCells.push([]);
      for (j = 0; j <= show; j++) {
        var td = el('td', { class: i > j ? 'gh' : i === j ? 'gd' : 'ga' });
        gridCells[i].push(td); tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    out.appendChild(el('div', { class: 'mo-card' }, [
      el('div', { class: 'mo-teams' }, [names.h, el('span', { class: 'vs', text: 'home v away' }), names.a]),
      bigStrip,
      el('dl', { class: 'mo-facts' }, [fact('home', ''), fact('draw', 'Draw'), fact('away', ''),
        fact('xg', 'Expected goals'), fact('over', 'Over ' + c.markets.over_line + ' goals'), fact('btts', 'Both teams score')]),
      el('h3', { class: 'mo-sub', text: 'Most likely scorelines' }),
      top5
    ]));
    out.appendChild(el('div', { class: 'mo-card' }, [el('div', { class: 'grid-wrap' }, [table])]));

    function render() {
      var same = hl.value === al.value && fh.value === fa.value;
      $('m-cross').hidden = hl.value === al.value;
      out.classList.toggle('is-empty', same);
      if (same) { if (!$('m-same')) out.parentNode.insertBefore(el('p', { class: 'empty', id: 'm-same', text: 'Pick two different teams.' }), out); return; }
      var gone = $('m-same'); if (gone) gone.remove();
      var home = find(+hl.value, fh.value), away = find(+al.value, fa.value);
      var rt = F.rates(home, away, c), fc = F.forecast(rt[0], rt[1], c), m = fc.markets;
      names.h.textContent = home.team; names.a.textContent = away.team;
      setStrip(bigStrip, [m.home, m.draw, m.away], null, [home.team + ' win', 'draw', away.team + ' win']);
      factLabels.home.textContent = home.team + ' win'; factLabels.away.textContent = away.team + ' win';
      tween(facts.home, m.home, pct1); tween(facts.draw, m.draw, pct1); tween(facts.away, m.away, pct1);
      tween(facts.xg, [m.xg_home, m.xg_away], function (v) { return v[0].toFixed(2) + ' – ' + v[1].toFixed(2); });
      tween(facts.over, m.over_2_5, pct1); tween(facts.btts, m.btts, pct1);

      top5.textContent = '';
      var max = m.top_scorelines[0].p;
      m.top_scorelines.forEach(function (x, k) {
        var li = el('li', { 'aria-label': home.team + ' ' + x.home_goals + ', ' + away.team + ' ' + x.away_goals + ': ' + pct1(x.p) }, [
          el('span', { class: 'num', text: x.home_goals + '–' + x.away_goals }),
          el('span', { class: 'bar', 'aria-hidden': 'true' }, [el('i', { style: '--w:' + (100 * x.p / max).toFixed(1) + '%' })]),
          el('span', { class: 'num', text: pct1(x.p) })
        ]);
        top5.appendChild(li);
        animate(li, [{ opacity: 0, transform: 'translateX(-6px)' }, { opacity: 1, transform: 'none' }], { duration: 360, delay: k * 40, easing: EASE_OUT, fill: 'backwards' });
      });

      gridCap.textContent = 'Scoreline probabilities, ' + home.team + ' goals down, ' + away.team + ' goals across (shown to ' + show + '; computed to ' + c.grid.market_max_goals + ')';
      var gmax = 0;
      for (var a = 0; a <= show; a++) for (var b = 0; b <= show; b++) gmax = Math.max(gmax, fc.grid[a][b]);
      for (a = 0; a <= show; a++) for (b = 0; b <= show; b++) {
        var p = fc.grid[a][b], k = p / gmax, cell = gridCells[a][b];
        cell.style.setProperty('--k', (8 + 85 * k).toFixed(1) + '%');
        cell.classList.toggle('strong', k > 0.55);
        cell.textContent = (p * 100).toFixed(1);
      }
    }
    function setSide(sideLeague, sideTeam, li, team) { sideLeague.value = String(li); fillTeams(sideTeam, li, team); }
    hl.addEventListener('change', function () { fillTeams(fh, +hl.value, byRank(+hl.value)[0].team); render(); });
    al.addEventListener('change', function () {
      var r = byRank(+al.value), want = r[0].team === fh.value && al.value === hl.value ? r[1].team : r[0].team;
      fillTeams(fa, +al.value, want); render();
    });
    fh.addEventListener('change', render);
    fa.addEventListener('change', render);
    $('m-swap').addEventListener('click', function () {
      var l1 = +hl.value, t1 = fh.value;
      setSide(hl, fh, +al.value, fa.value); setSide(al, fa, l1, t1);
      animate($('m-swap').querySelector('svg'), [{ transform: 'rotate(0)' }, { transform: 'rotate(180deg)' }], { duration: 480, easing: EASE_OUT });
      render();
    });
    pickForMatchup = function (li, team) {
      var r = byRank(li);
      setSide(hl, fh, li, team);
      setSide(al, fa, li, r[0].team === team ? r[1].team : r[0].team);
      render();
    };
    var first = byRank(0);
    setSide(hl, fh, 0, first[0].team); setSide(al, fa, 0, first[1].team);
    render();
  }

  function fillClaimSpans() {
    document.querySelectorAll('[data-claim]').forEach(function (s) {
      var id = s.getAttribute('data-claim');
      s.textContent = minus(C[id]);
    });
  }

  // ---------------------------------------------------------------- boot
  initTheme();
  initPopover();
  initRouter();
  fetch('data.json').then(function (r) {
    if (!r.ok) throw new Error('data.json: HTTP ' + r.status);
    return r.json();
  }).then(function (d) {
    DATA = d; C = d.claims;
    renderResults();
    renderCaveats(d.season);
    renderAggregate();
    initSeason(d.season.matches);
    initRatings(d.ratings);
    initMatchup(d.ratings, d.constants, d.samples, d.constants.snapshot_date);
    fillClaimSpans();
    document.body.classList.add('loaded');
  }).catch(function (e) {
    console.error(e);
    var m = $('main');
    m.insertBefore(el('p', { class: 'empty', role: 'alert', text: 'Could not load data.json (' + e.message + '). Serve the folder with: python -m http.server -d site 8000' }), m.firstChild);
  });
})();
