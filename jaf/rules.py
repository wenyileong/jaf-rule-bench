# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Options, assignment rules and the mixed-logit share model (build plan s 3, revised s 10)."""
from __future__ import annotations
import numpy as np
from .params import CONFIGS, Params
from .network import softplus


def option_grid(N):
    return [(j, c, p) for j in range(N) for c in CONFIGS for p in range(N)]


def claims(rule, j, c, p, P: Params):
    """Weighted list of claim tuples; first element of a tuple is the primary claimant; () is a gap."""
    N = P.N
    if rule == "owner_residence":
        return [(1 - P.dual_residence, (j,)), (P.dual_residence, (j, (j + 1) % N))]
    if rule == "intermediary":
        return [(1.0, (p,))] if c == "custodial" else [(1.0, ())]
    if rule == "control":
        if c == "multisig" and p != j:
            return [(1.0, (p, j))]
        return [(1.0, (p,))]
    if rule in ("enclosure", "registration", "validation"):
        return [(1.0, (p,))]
    if rule == "non_assignment":
        return [(1.0, ())]
    # matched pair (Proposition 3): identical except where a self-hosted key sits abroad
    if rule == "X_gap":
        if c == "custodial":
            return [(1.0, (p,))]
        return [(1.0, (j,))] if p == j else [(1.0, ())]
    if rule == "Y_overlap":
        if c == "custodial":
            return [(1.0, (p,))]
        return [(1.0, (j,))] if p == j else [(1.0, (j, p))]
    raise ValueError(rule)


def location_weight(rule, j, c, p, P: Params, e, g, v):
    if p == j:
        return 1.0
    m = P.mobility.get((rule, c))
    if m is None:
        return P.immobile
    if rule == "registration":
        scale = g[p]
    elif rule == "validation":
        scale = v[p]
    elif c == "custodial":
        scale = e[p]
    else:
        scale = 1.0
    return m * scale


class Compiled:
    def __init__(self, rule, P: Params):
        self.rule, self.P = rule, P
        a, e, g, v = P.jurisdictions()
        self.a, self.e, self.g, self.v = a, e, g, v
        opts = option_grid(P.N)
        self.opts, self.K = opts, len(opts)
        self.j = np.array([o[0] for o in opts])
        self.c = np.array([CONFIGS.index(o[1]) for o in opts])
        self.p = np.array([o[2] for o in opts])
        self.lnbase = np.log(np.array([max(1e-300, a[j] * P.w[c] * location_weight(rule, j, c, p, P, e, g, v))
                                       for j, c, p in opts]))
        obs = P.obs
        self.o = np.array([obs[c] for _, c, _ in opts])
        k_idx, wt, prim, sec = [], [], [], []
        for k, (j, c, p) in enumerate(opts):
            for w_, cl in claims(rule, j, c, p, P):
                if w_ <= 0:
                    continue
                k_idx.append(k); wt.append(w_)
                prim.append(cl[0] if len(cl) >= 1 else -1)
                sec.append(cl[1] if len(cl) >= 2 else -1)
        self.ek, self.ew = np.array(k_idx), np.array(wt)
        self.ep, self.es = np.array(prim), np.array(sec)
        self.egap, self.eover = self.ep < 0, self.es >= 0
        # option-level labels (dominant entry)
        dom = {}
        for n, k in enumerate(self.ek):
            if k not in dom or self.ew[n] > self.ew[dom[k]]:
                dom[k] = n
        self.kprim = np.array([self.ep[dom[k]] for k in range(self.K)])      # -1 if gap
        self.nu = P.location_draws()                                          # R x N
        A = np.zeros((len(self.ek), self.K)); A[np.arange(len(self.ek)), self.ek] = 1.0
        self.A = A                                                             # entry -> option aggregation
        self.nuK = self.nu[:, self.j]                                          # R x K
        self.lnexit = np.log(P.exit_weight)

    # ---- burden and revenue -------------------------------------------------------
    def entry_terms(self, tau):
        P = self.P
        tp = np.where(self.egap, 0.0, tau[np.maximum(self.ep, 0)])
        ts = np.where(self.eover, tau[np.maximum(self.es, 0)], 0.0)
        o = self.o[self.ek]
        sec = np.where(self.eover, (1 - P.rho) * ts + P.rho * softplus(ts - tp, P.kappa_relief), 0.0) * o
        prim = np.where(self.egap, 0.0, tp) * o
        gap = np.where(self.egap, P.phi * tau[self.j[self.ek]], 0.0)
        return prim + sec + gap, prim, sec, gap

    def exponent(self, tau, theta):
        """Σ_entries w · θ_claimant · burden; θ attaches to the jurisdiction whose rate it is (paper eq. n 18)."""
        b, *_ = self.entry_terms(tau)
        th = np.where(self.egap, theta[self.j[self.ek]], theta[np.maximum(self.ep, 0)])
        return np.bincount(self.ek, weights=self.ew * th * b, minlength=self.K)

    def draw_shares(self, tau, theta):
        """R x K option shares and R exit shares (logit kernel within each draw)."""
        V = self.lnbase - self.exponent(tau, theta)                     # K
        U = V[None, :] + self.nu[:, self.j]                             # R x K
        m = np.maximum(U.max(1), self.lnexit)
        eu = np.exp(U - m[:, None]); ex = np.exp(self.lnexit - m)
        Z = eu.sum(1) + ex
        return eu / Z[:, None], ex / Z

    def shares(self, tau, theta):
        S, X = self.draw_shares(tau, theta)
        return S.mean(0), X.mean()

    # ---- batched evaluation (rows of tau) for best responses ------------------------
    def batch_terms(self, T):
        P = self.P
        tp = np.where(self.egap, 0.0, T[:, np.maximum(self.ep, 0)])
        ts = np.where(self.eover, T[:, np.maximum(self.es, 0)], 0.0)
        o = self.o[self.ek]
        sec = np.where(self.eover, (1 - P.rho) * ts + P.rho * softplus(ts - tp, P.kappa_relief), 0.0) * o
        prim = np.where(self.egap, 0.0, tp) * o
        gap = np.where(self.egap, P.phi * T[:, self.j[self.ek]], 0.0)
        return prim, sec, gap

    def batch_revenue_i(self, T, TH, i):
        """Revenue of jurisdiction i for each row of T (B x N) with sensitivities TH (B x N)."""
        prim, sec, gap = self.batch_terms(T)
        b = prim + sec + gap
        th = np.where(self.egap, TH[:, self.j[self.ek]], TH[:, np.maximum(self.ep, 0)])
        expo = (self.ew * th * b) @ self.A                                   # B x K
        U = (self.lnbase - expo)[:, None, :] + self.nuK[None, :, :]          # B x R x K
        m = np.maximum(U.max(2), self.lnexit)
        eu = np.exp(U - m[..., None]); Z = eu.sum(2) + np.exp(self.lnexit - m)
        s = (eu / Z[..., None]).mean(1)                                       # B x K
        mw = s[:, self.ek] * self.ew
        r = (mw * prim * ((self.ep == i) & ~self.egap)).sum(1)
        r += (mw * sec * (self.eover & (self.es == i))).sum(1)
        r += (mw * gap * (self.egap & (self.j[self.ek] == i))).sum(1)
        return r

    def revenue(self, tau, s):
        _, pr, sr, gr = self.entry_terms(tau)
        m = s[self.ek] * self.ew
        N = self.P.N
        R = np.bincount(np.maximum(self.ep, 0), weights=m * pr * (~self.egap), minlength=N)
        R += np.bincount(np.maximum(self.es, 0), weights=m * sr * self.eover, minlength=N)
        R += np.bincount(self.j[self.ek], weights=m * gr * self.egap, minlength=N)
        return R

    def failure_measures(self, tau, s):
        m = s[self.ek] * self.ew
        b, pr, sr, gr = self.entry_terms(tau)
        tp = np.where(self.egap, 0, tau[np.maximum(self.ep, 0)])
        ts = np.where(self.eover, tau[np.maximum(self.es, 0)], 0)
        o = self.o[self.ek]
        unrelieved = (m * np.where(self.eover, (pr + sr) - np.maximum(tp, ts) * o, 0)).sum()
        forgone = (m * np.where(self.egap, (1 - self.P.phi) * tau[self.j[self.ek]], 0)).sum()
        return dict(gap=float(m[self.egap].sum()), overlap=float(m[self.eover].sum()),
                    unrelieved=float(unrelieved), forgone=float(forgone),
                    backstop=float((m * gr * self.egap).sum()),
                    unobserved=float((m * np.where(self.egap, 0, 1 - o)).sum()))

    def assignment(self, s):
        N = self.P.N
        m = s[self.ek] * self.ew
        Q = np.zeros((N, N)); ok = ~self.egap
        np.add.at(Q, (self.ep[ok], self.j[self.ek][ok]), m[ok])
        gapj = np.bincount(self.j[self.ek][self.egap], weights=m[self.egap], minlength=N)
        return Q, gapj
