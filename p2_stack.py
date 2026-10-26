"""S2: stack of the goals-only model with the snapshot market, z_k = a log p_k + b log m_k + c_k (c mean zero),
and the market-only comparator (a = 0). Fitted by minimising mean log-loss; never fed closing odds."""
import numpy as np
from scipy.optimize import minimize

from exp_harness import DEV_START, VAL_START


def market_probs(odds):
    """Proportional overround removal: m_k = (1 / o_k) / sum_j (1 / o_j)."""
    implied = 1.0 / np.asarray(odds, float)
    return implied / implied.sum(axis=1, keepdims=True)


def _features(model_probs, market):
    # Model log-probabilities clipped at 1e-15, as in exp_model.apply_calibration.
    return np.log(np.clip(np.asarray(model_probs, float), 1e-15, 1.0)), np.log(np.asarray(market, float))


def _softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    weights = np.exp(z)
    return weights / weights.sum(axis=1, keepdims=True)


def apply(coef, model_probs, market):
    """Stacked probabilities. coef: {'a', 'b', 'c': [c1, c2, c3]} with c summing to 0 (a = 0 is market-only)."""
    c = np.asarray(coef['c'], float)
    if c.shape != (3,) or abs(c.sum()) > 1e-9:
        raise ValueError('The class offsets c must be three values summing to 0.')
    log_p, log_m = _features(model_probs, market)
    return _softmax(coef['a'] * log_p + coef['b'] * log_m + c)


def fit(model_probs, market, actual, with_model=True):
    """Coefficients minimising mean log-loss on the given rows (BFGS, analytic gradient)."""
    log_p, log_m = _features(model_probs, market)
    actual = np.asarray(actual)
    onehot = np.eye(3)[actual]
    basis = np.array([[1.0, 0.0, -1.0], [0.0, 1.0, -1.0]])  # c = (c1, c2, -c1 - c2)

    def unpack(theta):
        return (theta[0], theta[1], theta[2:]) if with_model else (0.0, theta[0], theta[1:])

    def loss(theta):
        a, b, free = unpack(theta)
        z = a * log_p + b * log_m + free @ basis
        z_max = z.max(axis=1, keepdims=True)
        log_norm = z_max[:, 0] + np.log(np.exp(z - z_max).sum(axis=1))
        value = np.mean(log_norm - z[np.arange(len(actual)), actual])
        residual = _softmax(z) - onehot
        grad_c = (residual @ basis.T).mean(axis=0)
        grad_b = np.mean((residual * log_m).sum(axis=1))
        if not with_model:
            return value, np.concatenate([[grad_b], grad_c])
        grad_a = np.mean((residual * log_p).sum(axis=1))
        return value, np.concatenate([[grad_a, grad_b], grad_c])

    start = np.array([0.0, 1.0, 0.0, 0.0]) if with_model else np.array([1.0, 0.0, 0.0])
    result = minimize(loss, start, jac=True, method='BFGS', options=dict(gtol=1e-9, maxiter=10_000))
    gradient = np.abs(loss(result.x)[1]).max()
    if not np.isfinite(result.fun) or gradient > 1e-6:
        raise RuntimeError(f'Stack fit did not converge: {result.message} (max |gradient| {gradient:.2e})')
    a, b, free = unpack(result.x)
    c = free @ basis
    return dict(a=float(a), b=float(b), c=[float(value) for value in c], log_loss=float(result.fun),
                n=int(len(actual)))


def dev_mask(dates, has_market):
    """Rows eligible for the selection fit: DEV dates (2020-07-01 to 2023-06-30) with snapshot odds."""
    dates = np.asarray(dates, dtype='datetime64[ns]')
    return ((dates >= np.datetime64(DEV_START)) & (dates < np.datetime64(VAL_START))
            & np.asarray(has_market, bool))


def fit_dev(dates, model_probs, market, actual, has_market, with_model=True):
    """Fit on DEV rows only; every other row is ignored whatever its values."""
    mask = dev_mask(dates, has_market)
    if not mask.any():
        raise ValueError('No DEV rows with snapshot odds.')
    return fit(np.asarray(model_probs)[mask], np.asarray(market)[mask], np.asarray(actual)[mask], with_model)
