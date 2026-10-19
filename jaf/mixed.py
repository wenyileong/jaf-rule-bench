# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Mixed-regime engine: each jurisdiction applies its own rule (build plan s 12).

Options are (residence j, configuration c, placement p) as in 0.2. Under the co-location assumption
(s 12.1, issue 1) every location-based connecting factor of a holding follows its placement p.
Differences from the single-rule engine:
  * claimants come from each jurisdiction's own rule (world.claimants), with up to S_MAX secondaries;
  * observability depends on the claimant and the placement (exchange of information);
  * the residence top-up (phi) and fixed or competitive rates are per jurisdiction.
"""
from __future__ import annotations
import numpy as np
from .params import CONFIGS, Params
from .network import softplus
from .rules import Compiled, option_grid
from .world import World, claimants

S_MAX = 3


def params_for(world: World, base: Params | None = None) -> Params:
    base = base or Params()
    return base.replace(N=world.N, rho=world.settings.treaty_relief)


def default_placement_weight(world: World):
    e = world.vec("exchange_presence")
    banned = ~world.vec("domestic_exchanges_permitted", bool)
    s = world.settings
    def w(j, c, p):
        if c == "custodial" and banned[p]:          # p is the operational base
            return 1e-12
        if p == j:
            return 1.0
        if c == "custodial":
            return s.mobility_custodial * e[p]
        return s.mobility_self_hosted
    return w


class MixedCompiled(Compiled):
    def __init__(self, world: World, P: Params | None = None, placement_weight=None, visibility=None,
                 self_visibility=None, holder_base=None):
        self.world = world
        self.rule = "mixed"
        P = params_for(world, P)
        self.P = P
        N = P.N
        a = world.vec("holder_base") if holder_base is None else np.asarray(holder_base, float)
        self.a = a
        pw = placement_weight or default_placement_weight(world)
        if visibility is None:
            V3 = world.custodial_visibility3()
        else:                                       # (N, N) override as in 0.3: depends on base only
            V2 = np.asarray(visibility, float); V3 = np.repeat(V2[:, :, None], N, 2)
        vself = world.vec("visibility_self_hosted") if self_visibility is None else np.asarray(self_visibility, float)
        self.V3, self.vself = V3, vself
        Rm = world.relief_matrix()
        banned = ~world.vec("domestic_exchanges_permitted", bool)
        self.phi = world.vec("residence_topup")
        self.fixed = np.array([x.rate_mode == "fixed" for x in world.jurisdictions])
        self.fixed_tau = np.array([float(x.effective_rate or 0.0) for x in world.jurisdictions])

        # options (j, c, base p, seat q, seat share): exchange-held holdings split by legal seat (build plan s 13)
        types = {}
        for b, q, sh in world.exchange_types():
            types.setdefault(b, []).append((q, sh))
        opts = []
        for j in range(N):
            for c in CONFIGS:
                for p_ in range(N):
                    if c == "custodial":
                        for q, sh in types.get(p_, [(p_, 1.0)]):
                            opts.append((j, c, p_, q, sh * (1e-12 if banned[q] and q != p_ else 1.0)))
                    else:
                        opts.append((j, c, p_, p_, 1.0))
        self.opts, self.K = [(j, c, p_) for j, c, p_, _, _ in opts], len(opts)
        self.j = np.array([o[0] for o in opts])
        self.c = np.array([CONFIGS.index(o[1]) for o in opts])
        self.p = np.array([o[2] for o in opts])
        self.q = np.array([o[3] for o in opts])
        self.lnbase = np.log(np.array([max(1e-300, a[j] * P.w[c] * pw(j, c, p_) * sh) for j, c, p_, _, sh in opts]))
        self.o = np.array([P.obs[o[1]] for o in opts])      # kept for compatibility; per-claim values below

        k_idx, wt, prim, op, secs, oss, basis = [], [], [], [], [], [], []
        self.truncated = 0.0
        rhos = []
        for k, (j, c, p, q, _sh) in enumerate(opts):
            for w_sub, links in world.personal_subtypes(j):
                if w_sub <= 0:
                    continue
                cl = claimants(world, j, c, p, links, seat=q)
                if len(cl) > S_MAX + 1:
                    self.truncated += w_sub
                    cl = cl[:S_MAX + 1]
                vis = lambda r, p=p, q=q, c=c: V3[r, p, q] if c == "custodial" else vself[r]
                k_idx.append(k); wt.append(w_sub)
                prim.append(cl[0][0] if cl else -1)
                op.append(vis(cl[0][0]) if cl else 0.0)
                s_ = [q for q, _ in cl[1:]] + [-1] * (S_MAX - len(cl[1:]))
                secs.append(s_)
                oss.append([vis(x) if x >= 0 else 0.0 for x in s_])
                rhos.append([Rm[x, cl[0][0]] if x >= 0 else 0.0 for x in s_])
                basis.append([b for _, b in cl])
        self.ek, self.ew = np.array(k_idx), np.array(wt)
        self.ep = np.array(prim)
        self.ES = np.array(secs, dtype=int)                       # E x S
        self.op, self.OS = np.array(op), np.array(oss)            # E, E x S
        self.RHO = np.array(rhos)                                  # E x S relief by (relieving, taxing) pair
        self.basis = basis
        self.es = self.ES[:, 0]                                    # first secondary, for compatibility
        self.egap = self.ep < 0
        self.smask = self.ES >= 0
        self.eover = self.smask.any(1)
        dom = {}
        for n, k in enumerate(self.ek):
            if k not in dom or self.ew[n] > self.ew[dom[k]]:
                dom[k] = n
        self.kprim = np.array([self.ep[dom[k]] for k in range(self.K)])
        self.nu = P.location_draws()
        A = np.zeros((len(self.ek), self.K)); A[np.arange(len(self.ek)), self.ek] = 1.0
        self.A = A
        self.nuK = self.nu[:, self.j]
        self.lnexit = np.log(P.exit_weight)
        self.ej = self.j[self.ek]

    # ---- burden ------------------------------------------------------------------------
    def _terms(self, T):
        """T: (..., N). Returns prim (..., E), secS (..., E, S), gap (..., E)."""
        P = self.P
        tp = np.where(self.egap, 0.0, T[..., np.maximum(self.ep, 0)])
        TS = np.where(self.smask, T[..., np.maximum(self.ES, 0)], 0.0)
        secS = np.where(self.smask, (1 - self.RHO) * TS + self.RHO * softplus(TS - tp[..., None], P.kappa_relief), 0.0) * self.OS
        prim = tp * self.op
        gap = np.where(self.egap, self.phi[self.ej] * T[..., self.ej], 0.0)
        return prim, secS, gap

    def entry_terms(self, tau):
        prim, secS, gap = self._terms(tau)
        sec = secS.sum(-1)
        return prim + sec + gap, prim, sec, gap

    def batch_terms(self, T):
        prim, secS, gap = self._terms(T)
        return prim, secS.sum(-1), gap

    def batch_revenue_i(self, T, TH, i):
        prim, secS, gap = self._terms(T)
        b = prim + secS.sum(-1) + gap
        th = np.where(self.egap, TH[:, self.ej], TH[:, np.maximum(self.ep, 0)])
        expo = (self.ew * th * b) @ self.A
        U = (self.lnbase - expo)[:, None, :] + self.nuK[None, :, :]
        m = np.maximum(U.max(2), self.lnexit)
        eu = np.exp(U - m[..., None]); Z = eu.sum(2) + np.exp(self.lnexit - m)
        s = (eu / Z[..., None]).mean(1)
        mw = s[:, self.ek] * self.ew
        r = (mw * prim * ((self.ep == i) & ~self.egap)).sum(1)
        r += (mw[..., None] * secS * (self.ES == i)).sum((1, 2))
        r += (mw * gap * (self.egap & (self.ej == i))).sum(1)
        return r

    def revenue(self, tau, s):
        prim, secS, gap = self._terms(tau)
        m = s[self.ek] * self.ew
        N = self.P.N
        R = np.bincount(np.maximum(self.ep, 0), weights=m * prim * (~self.egap), minlength=N)
        for q in range(self.ES.shape[1]):
            R += np.bincount(np.maximum(self.ES[:, q], 0), weights=m * secS[:, q] * self.smask[:, q], minlength=N)
        R += np.bincount(self.ej, weights=m * gap * self.egap, minlength=N)
        return R

    def failure_measures(self, tau, s):
        m = s[self.ek] * self.ew
        prim, secS, gap = self._terms(tau)
        tp = np.where(self.egap, 0.0, tau[np.maximum(self.ep, 0)])
        TS = np.where(self.smask, tau[np.maximum(self.ES, 0)], 0.0)
        single_best = np.maximum(tp * self.op, (TS * self.OS).max(1))
        unrelieved = (m * np.where(self.eover, prim + secS.sum(1) - single_best, 0.0)).sum()
        forgone = (m * np.where(self.egap, (1 - self.phi[self.ej]) * tau[self.ej], 0.0)).sum()
        return dict(gap=float(m[self.egap].sum()), overlap=float(m[self.eover].sum()),
                    multiple=float(m[self.smask.sum(1) >= 2].sum()),
                    unrelieved=float(unrelieved), forgone=float(forgone),
                    backstop=float((m * gap * self.egap).sum()),
                    unobserved=float((m * np.where(self.egap, 0.0, 1 - self.op)).sum()))

    # ---- per-jurisdiction views ----------------------------------------------------------
    def by_jurisdiction(self, tau, s):
        """Per-jurisdiction gap, overlap and unobserved base among its residents, and base it claims."""
        N = self.P.N
        m = s[self.ek] * self.ew
        res_gap = np.bincount(self.ej, weights=m * self.egap, minlength=N)
        res_over = np.bincount(self.ej, weights=m * self.eover, minlength=N)
        res_total = np.bincount(self.ej, weights=m, minlength=N)
        claimed_primary = np.bincount(np.maximum(self.ep, 0), weights=m * (~self.egap), minlength=N)
        claimed_secondary = np.zeros(N)
        for q in range(self.ES.shape[1]):
            claimed_secondary += np.bincount(np.maximum(self.ES[:, q], 0), weights=m * self.smask[:, q], minlength=N)
        unseen = np.bincount(np.maximum(self.ep, 0), weights=m * (~self.egap) * (1 - self.op), minlength=N)
        placed = np.bincount(self.p[self.ek], weights=m, minlength=N)
        seated = np.bincount(self.q[self.ek], weights=m * (self.c[self.ek] == 0), minlength=N)
        return dict(incorporated_here=seated, resident_base=res_total, resident_gap=res_gap, resident_overlap=res_over,
                    claimed_primary=claimed_primary, claimed_secondary=claimed_secondary,
                    unseen_primary=unseen, placed_here=placed)
