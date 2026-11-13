"""Tiny Gaussian HMM (EM + causal forward filter) in numpy/numba."""
import numpy as np
from numba import njit

@njit(cache=True)
def _fb(B, A, pi):
    T, K = B.shape
    al = np.zeros((T, K)); be = np.zeros((T, K)); sc = np.zeros(T)
    a = pi * B[0]; sc[0] = a.sum(); al[0] = a / sc[0]
    for t in range(1, T):
        a = np.zeros(K)
        for j in range(K):
            v = 0.0
            for i in range(K): v += al[t-1, i] * A[i, j]
            a[j] = v * B[t, j]
        sc[t] = a.sum(); al[t] = a / sc[t]
    be[T-1] = 1.0
    for t in range(T-2, -1, -1):
        for i in range(K):
            v = 0.0
            for j in range(K): v += A[i, j] * B[t+1, j] * be[t+1, j]
            be[t, i] = v / sc[t+1]
    xi = np.zeros((K, K))
    for t in range(T-1):
        for i in range(K):
            for j in range(K):
                xi[i, j] += al[t, i] * A[i, j] * B[t+1, j] * be[t+1, j] / sc[t+1]
    return al, be, sc, xi

def emis(x, mu, sd):
    return np.exp(-0.5 * ((x[:, None] - mu[None]) / sd[None]) ** 2) / sd[None] + 1e-300

def fit(x, mu, sd, A, iters=200, tie_sd=False, verbose=False):
    K = len(mu); pi = np.full(K, 1 / K); ll0 = -np.inf
    for it in range(iters):
        al, be, sc, xi = _fb(emis(x, mu, sd), A, pi)
        g = al * be; g /= g.sum(1, keepdims=True)
        A = xi / xi.sum(1, keepdims=True)
        w = g.sum(0)
        mu = (g * x[:, None]).sum(0) / w
        v = (g * (x[:, None] - mu[None]) ** 2).sum(0) / w
        sd = np.sqrt(v) if not tie_sd else np.full(K, np.sqrt((v * w).sum() / w.sum()))
        ll = np.log(sc).sum()
        if verbose and it % 20 == 0: print(it, ll)
        if abs(ll - ll0) < 1e-4: break
        ll0 = ll
    return mu, sd, A, ll

def filt(x, mu, sd, A):
    """causal posterior P(state_t | x_1..t)"""
    al, _, _, _ = _fb(emis(x, mu, sd), A, np.full(len(mu), 1 / len(mu)))
    return al
