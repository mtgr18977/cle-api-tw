"""Association and specificity measures (plan section 4.6).

Cohesion (domain corpus only), for an n-gram with joint count ``c``, word counts
``cs = [c(w1) .. c(wn)]`` and corpus size ``N``:

* expected count   E = c(w1)...c(wn) / N^(n-1)
* t-score          (c - E) / sqrt(c)                      (as in the mwetoolkit paper)
* PMI              log2(c / E)
* Dice             n*c / (c(w1)+...+c(wn))
* MLE              c / N  (joint relative frequency)

Specificity (domain vs. reference), Dunning's log-likelihood G2 and a smoothed ratio of
relative frequencies.
"""
from __future__ import annotations

from math import log, log2, sqrt, prod
from typing import Sequence


def expected(cs: Sequence[int], n_tokens: int) -> float:
    return prod(cs) / (n_tokens ** (len(cs) - 1))


def t_score(c: int, cs: Sequence[int], n_tokens: int) -> float:
    return (c - expected(cs, n_tokens)) / sqrt(c) if c > 0 else 0.0


def pmi(c: int, cs: Sequence[int], n_tokens: int) -> float:
    e = expected(cs, n_tokens)
    return log2(c / e) if c > 0 and e > 0 else 0.0


def dice(c: int, cs: Sequence[int]) -> float:
    return len(cs) * c / sum(cs) if sum(cs) else 0.0


def mle(c: int, n_tokens: int) -> float:
    return c / n_tokens if n_tokens else 0.0


def log_likelihood(a: int, b: int, n1: int, n2: int) -> float:
    """Dunning's G2 for counts ``a`` (of ``n1``) vs ``b`` (of ``n2``)."""
    if n1 <= 0 or n2 <= 0 or a + b == 0:
        return 0.0
    e1 = n1 * (a + b) / (n1 + n2)
    e2 = n2 * (a + b) / (n1 + n2)
    g = 0.0
    if a > 0:
        g += a * log(a / e1)
    if b > 0:
        g += b * log(b / e2)
    return 2 * g


def rel_freq_ratio(a: int, b: int, n1: int, n2: int, k: float = 0.5) -> float:
    """Ratio of relative frequencies with add-k smoothing (finite when b == 0)."""
    return ((a + k) / n1) / ((b + k) / n2)
