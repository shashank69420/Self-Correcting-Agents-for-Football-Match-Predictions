// Scoreline forecast from goal rates: a line-for-line port of fan_features.score_grid / markets and
// exp_model.dixon_coles_probs (Poisson product grid, Dixon-Coles low-score factors floored at 0, renormalised).
(function (root) {
  'use strict';

  // Poisson pmf for k = 0..maxGoals, by recurrence.
  function poissonPmf(rate, maxGoals) {
    var out = new Array(maxGoals + 1);
    var logRate = Math.log(rate);
    var logFact = 0;
    for (var k = 0; k <= maxGoals; k++) {
      if (k > 0) logFact += Math.log(k);
      out[k] = Math.exp(k * logRate - rate - logFact);
    }
    return out;
  }

  // Normalised grid[h][a]; minMass null skips the mass check (dixon_coles_probs has none).
  function scoreGrid(lambdaHome, muAway, rho, maxGoals, minMass) {
    if (!isFinite(lambdaHome) || !isFinite(muAway)) throw new Error('Non-finite pre-match goal rate.');
    var ph = poissonPmf(lambdaHome, maxGoals), pa = poissonPmf(muAway, maxGoals);
    var grid = [], mass = 0, h, a;
    for (h = 0; h <= maxGoals; h++) {
      grid.push(new Array(maxGoals + 1));
      for (a = 0; a <= maxGoals; a++) { grid[h][a] = ph[h] * pa[a]; mass += grid[h][a]; }
    }
    if (minMass != null && !(mass >= minMass)) throw new Error('Score grid mass ' + mass + ' is below ' + minMass);
    if (rho !== 0) {
      grid[0][0] *= Math.max(1 - lambdaHome * muAway * rho, 0);
      grid[0][1] *= Math.max(1 + lambdaHome * rho, 0);
      grid[1][0] *= Math.max(1 + muAway * rho, 0);
      grid[1][1] *= Math.max(1 - rho, 0);
    }
    var total = 0;
    for (h = 0; h <= maxGoals; h++) for (a = 0; a <= maxGoals; a++) total += grid[h][a];
    if (!isFinite(total) || total <= 0) throw new Error('The specified score grid has no finite positive mass.');
    for (h = 0; h <= maxGoals; h++) for (a = 0; a <= maxGoals; a++) grid[h][a] /= total;
    return grid;
  }

  function outcomeProbs(grid) {
    var home = 0, draw = 0, away = 0;
    for (var h = 0; h < grid.length; h++) for (var a = 0; a < grid.length; a++) {
      if (h > a) home += grid[h][a]; else if (h === a) draw += grid[h][a]; else away += grid[h][a];
    }
    return [home, draw, away];
  }

  function markets(grid, overLine, topK) {
    var n = grid.length, xgH = 0, xgA = 0, over = 0, btts = 0, cells = [];
    for (var h = 0; h < n; h++) for (var a = 0; a < n; a++) {
      var p = grid[h][a];
      xgH += h * p; xgA += a * p;
      if (h + a > overLine) over += p;
      if (h >= 1 && a >= 1) btts += p;
      cells.push({ home_goals: h, away_goals: a, p: p });
    }
    // Probability descending, then home goals, then away goals.
    cells.sort(function (x, y) { return (y.p - x.p) || (x.home_goals - y.home_goals) || (x.away_goals - y.away_goals); });
    var hda = outcomeProbs(grid);
    return {
      home: hda[0], draw: hda[1], away: hda[2], xg_home: xgH, xg_away: xgA,
      top_scorelines: cells.slice(0, topK),
      over_2_5: over, under_2_5: 1 - over, btts: btts, btts_no: 1 - btts
    };
  }

  // Goal rates from uncentred rating means, as p2_model.run_filter forms them before a match.
  function rates(home, away, c) {
    var lambda = Math.exp(home.attack_mean_uncentred + away.defence_mean_uncentred + c.home_adv);
    var mu = Math.exp(away.attack_mean_uncentred + home.defence_mean_uncentred);
    if (c.clip_rates) {
      lambda = Math.min(Math.max(lambda, c.rate_bounds[0]), c.rate_bounds[1]);
      mu = Math.min(Math.max(mu, c.rate_bounds[0]), c.rate_bounds[1]);
    }
    return [lambda, mu];
  }

  function forecast(lambda, mu, c) {
    var grid = scoreGrid(lambda, mu, c.rho, c.grid.market_max_goals, c.grid.min_mass);
    return { lambda: lambda, mu: mu, grid: grid, markets: markets(grid, c.markets.over_line, c.markets.top_k) };
  }

  // Every entry of the committed sample forecasts must be reproduced to tol.
  function parity(samples, c, tol) {
    var worst = 0, failures = [];
    function check(label, got, want) {
      var d = Math.abs(got - want);
      if (!(d <= tol)) failures.push(label + ': ' + got + ' vs ' + want);
      if (d > worst || isNaN(d)) worst = isNaN(d) ? Infinity : d;
    }
    samples.forEach(function (s, i) {
      var tag = '#' + i + ' ';
      var m = forecast(s.lambda_home, s.mu_away, c).markets;
      ['home', 'draw', 'away', 'xg_home', 'xg_away', 'over_2_5', 'under_2_5', 'btts', 'btts_no'].forEach(function (k) {
        check(tag + k, m[k], s.markets[k]);
      });
      if (m.top_scorelines.length !== s.markets.top_scorelines.length) failures.push(tag + 'top scoreline count');
      s.markets.top_scorelines.forEach(function (t, j) {
        var g = m.top_scorelines[j] || {};
        if (g.home_goals !== t.home_goals || g.away_goals !== t.away_goals) failures.push(tag + 'top ' + j + ' scoreline');
        check(tag + 'top ' + j + ' p', g.p, t.p);
      });
      var hda = outcomeProbs(scoreGrid(s.lambda_home, s.mu_away, c.rho, c.grid.model_max_goals, null));
      for (var k = 0; k < 3; k++) check(tag + '1x2 ' + k, hda[k], s.model_1x2_max_goals_10[k]);
    });
    return { ok: failures.length === 0, worst: worst, failures: failures };
  }

  root.B12Forecast = { scoreGrid: scoreGrid, outcomeProbs: outcomeProbs, markets: markets, rates: rates,
                       forecast: forecast, parity: parity };
})(typeof window !== 'undefined' ? window : globalThis);
