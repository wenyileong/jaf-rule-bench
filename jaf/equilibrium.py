# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Equilibrium (specification s 1; plan s 4). Concept (a): elasticity-consistent.
Concept (b): partial anticipation (sensitivity anticipated, network held fixed)."""
from __future__ import annotations
import numpy as np
from .network import flows, resolvent, escape
from .rules import Compiled

_GR = (np.sqrt(5) - 1) / 2


def maximise(f, lo, hi, tol=1e-7):
    """Golden-section search for the maximum of a unimodal f on [lo, hi], with endpoint check."""
    a, b = lo, hi
    c, d = b - _GR * (b - a), a + _GR * (b - a)
    fc, fd = f(c), f(d)
    while b - a > tol:
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - _GR * (b - a); fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + _GR * (b - a); fd = f(d)
    x = (a + b) / 2; fx = f(x)
    for e in (lo, hi):
        fe = f(e)
        if fe > fx:
            x, fx = e, fe
    return x


def theta_of(tau, M, P):
    return P.theta0 + P.beta * escape(tau, M, P.kappa)


def network_state(comp: Compiled, tau, theta):
    s, x = comp.shares(tau, theta)
    Q, gapj = comp.assignment(s)
    F, D = flows(Q, gapj, comp.P.home_bias)
    Pm, M = resolvent(F, D, comp.P.alpha)
    return s, x, Q, gapj, F, D, Pm, M


def theta_batch(T, M, P):
    from .network import softplus
    diff = T[:, :, None] - T[:, None, :]
    S = softplus(diff, P.kappa)
    off = M.copy(); np.fill_diagonal(off, 0.0)
    return P.theta0 + P.beta * (off[None] * S).sum(2)


def best_response(comp, i, tau, M, theta_fixed, concept, points=21, rounds=5):
    """Nested grid search on [0, tau_max], each round one batched evaluation."""
    P = comp.P
    lo, hi = 0.0, P.tau_max
    best = tau[i]
    for _ in range(rounds):
        xs = np.linspace(lo, hi, points)
        T = np.repeat(tau[None, :], points, 0); T[:, i] = xs
        TH = np.repeat(theta_fixed[None, :], points, 0) if concept == "a" else theta_batch(T, M, P)
        r = comp.batch_revenue_i(T, TH, i)
        k = int(np.argmax(r)); best = xs[k]
        step = (hi - lo) / (points - 1)
        lo, hi = max(0.0, best - step), min(P.tau_max, best + step)
    return best


def max_gain(comp, tau, M, theta, concept, br, fixed=None):
    """Largest relative revenue gain any (competitive) state could obtain by moving from tau_i to its best response."""
    P = comp.P; g = 0.0
    for i in range(P.N):
        if fixed is not None and fixed[i]:
            continue
        T = np.repeat(tau[None, :], 2, 0); T[1, i] = br[i]
        TH = np.repeat(theta[None, :], 2, 0) if concept == "a" else theta_batch(T, M, P)
        r = comp.batch_revenue_i(T, TH, i)
        g = max(g, (r[1] - r[0]) / max(abs(r[1]), 1e-12))
    return g


def solve(comp: Compiled, concept="a", tau0=None, damping=0.5, tol=1e-5, max_iter=300, eps_tol=1e-4, eps_from=150):
    P = comp.P
    tau = np.full(P.N, 0.3) if tau0 is None else np.array(tau0, float)
    fixed = getattr(comp, "fixed", None)                     # mixed worlds: some rates fixed at coded values
    if fixed is not None:
        tau = np.where(fixed, comp.fixed_tau, tau)
    M = np.eye(P.N); converged = False; it = 0; prev = np.inf; eps_used = None; hist = []
    for it in range(1, max_iter + 1):
        theta = theta_of(tau, M, P)
        *_, M_new = network_state(comp, tau, theta)
        theta = theta_of(tau, M_new, P)
        br = np.array([comp.fixed_tau[i] if fixed is not None and fixed[i] else best_response(comp, i, tau, M_new, theta, concept)
                       for i in range(P.N)])
        new = (1 - damping) * tau + damping * br
        dt, dM = np.abs(new - tau).max(), np.abs(M_new - M).max()
        if dt > prev * 0.999 and damping > 0.05:      # adaptive damping against cycling (plan s 10)
            damping *= 0.7
        prev = dt
        hist.append(new)
        if it >= eps_from and it % 10 == 0:
            # epsilon-equilibrium check (build plan s 14.2, B9). Where a best-response revenue is almost flat, with
            # two near-equal maxima, rates can cycle indefinitely although no state gains materially. The average of
            # the recent cycle is tested: if no state could raise its revenue by more than eps_tol (relative) by
            # deviating from it, it is accepted and the largest such gain is reported.
            cand = np.mean(hist[-30:], axis=0)
            if fixed is not None:
                cand = np.where(fixed, comp.fixed_tau, cand)
            th_c = theta_of(cand, M_new, P)
            *_, M_c = network_state(comp, cand, th_c)
            th_c = theta_of(cand, M_c, P)
            br_c = np.array([comp.fixed_tau[i] if fixed is not None and fixed[i] else best_response(comp, i, cand, M_c, th_c, concept)
                             for i in range(P.N)])
            gain = max_gain(comp, cand, M_c, th_c, concept, br_c, fixed)
            if gain < eps_tol:
                tau, M = cand, M_c
                converged, eps_used = True, float(gain); break
        tau, M = new, M_new
        if dt < tol and dM < 1e-5:
            converged = True; break
    if not converged:                      # report how far from an equilibrium the final rates are
        th_f = theta_of(tau, M, P)
        br_f = np.array([comp.fixed_tau[i] if fixed is not None and fixed[i] else best_response(comp, i, tau, M, th_f, concept)
                         for i in range(P.N)])
        eps_used = float(max_gain(comp, tau, M, th_f, concept, br_f, fixed))
    theta = theta_of(tau, M, P)
    s, x, Q, gapj, F, D, Pm, M = network_state(comp, tau, theta)
    R = comp.revenue(tau, s)
    assigned = Q.sum()
    fail = comp.failure_measures(tau, s)
    rule_rev = float(R.sum() - fail["backstop"])   # backstop on gap base belongs to residence, not to the rule
    net_part = (theta - P.theta0).mean() / theta.mean()
    return dict(tau=tau, theta=theta, s=s, exit=float(x), Q=Q, gapj=gapj, F=F, D=D, P=Pm, M=M,
                revenue=R, converged=converged, iterations=it,
                corner=bool(np.any(tau > P.tau_max - 1e-3)),
                effective=rule_rev / assigned if assigned > 1e-12 else 0.0,     # rate the rule sustains on what it assigns
                revenue_per_base=float(R.sum() / max(1e-12, 1 - x)),            # yield per unit of base in the class (gap included)
                network_share=float(net_part),
                epsilon=eps_used,     # None if converged in rates; else the largest relative gain any state forgoes
                failure=fail)
