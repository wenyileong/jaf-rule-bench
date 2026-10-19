# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Flow network induced by a rule (specification section 2)."""
from __future__ import annotations
import numpy as np


def flows(Q, gapj, home_bias):
    """Cross-border flows F and domestic volumes D between assigned jurisdictions.

    Each unit of base with economic location j trades with counterparties in j with
    probability home_bias, otherwise uniformly elsewhere. A counterparty in j' is assigned
    to n' in proportion to Q[n', j']; unassigned (gap) counterparties are not nodes, so
    flows to them are not cross-border flows between jurisdictions.
    """
    N = Q.shape[0]
    T = np.full((N, N), (1 - home_bias) / (N - 1)); np.fill_diagonal(T, home_bias)
    econ = Q.sum(0) + gapj                               # all digital-asset base by economic location
    R = np.divide(Q, econ[None, :], out=np.zeros_like(Q), where=econ[None, :] > 0)   # R[n', j']
    F = Q @ T @ R.T                                      # F[n, n']
    D = np.diag(F).copy(); np.fill_diagonal(F, 0.0)
    return F, D


def resolvent(F, D, alpha):
    denom = D + F.sum(1)
    P = np.divide(F, denom[:, None], out=np.zeros_like(F), where=denom[:, None] > 0)
    M = np.linalg.inv(np.eye(len(D)) - alpha * P)
    return P, M


def round_trip(M):
    return np.diag(M) - 1.0


def softplus(x, kappa):
    z = np.clip(kappa * x, -50, 50)
    return np.where(kappa * x > 50, x, np.log1p(np.exp(z)) / kappa)


def escape(tau, M, kappa):
    diff = tau[:, None] - tau[None, :]
    S = softplus(diff, kappa)
    np.fill_diagonal(S, 0.0)
    off = M.copy(); np.fill_diagonal(off, 0.0)
    return (off * S).sum(1)
