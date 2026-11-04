from math import log2, sqrt

import pytest

from apiterm import measures as M


def test_t_score_matches_formula():
    # c=10, c1=20, c2=30, N=1000 -> E=0.6
    assert M.t_score(10, [20, 30], 1000) == pytest.approx((10 - 0.6) / sqrt(10))


def test_t_score_trigram_expected_uses_n_squared():
    assert M.expected([10, 10, 10], 100) == pytest.approx(0.1)  # 10*10*10 / 100^2


def test_t_score_bounded_by_sqrt_c():
    # t <= sqrt(c): t >= 2 therefore needs c >= 4
    assert M.t_score(3, [3, 3], 10 ** 6) <= sqrt(3) < 2
    assert M.t_score(4, [4, 4], 10 ** 6) >= 1.99


def test_pmi_dice_mle():
    assert M.pmi(10, [20, 30], 1000) == pytest.approx(log2(10 / 0.6))
    assert M.dice(10, [20, 30]) == pytest.approx(2 * 10 / 50)
    assert M.mle(10, 1000) == pytest.approx(0.01)


def test_log_likelihood_known_value_and_symmetry():
    # Equal relative frequencies -> 0
    assert M.log_likelihood(10, 100, 1000, 10000) == pytest.approx(0.0, abs=1e-9)
    # Dunning-style example computed by hand: a=100/N1=10000 vs b=10/N2=10000
    g = M.log_likelihood(100, 10, 10000, 10000)
    e = 55
    assert g == pytest.approx(2 * (100 * __import__("math").log(100 / e) + 10 * __import__("math").log(10 / e)))
    assert g > 3.84
    assert M.log_likelihood(0, 0, 10, 10) == 0.0


def test_ratio_is_finite_when_absent_from_reference():
    r = M.rel_freq_ratio(5, 0, 1000, 10 ** 6)
    assert r > 1 and r < float("inf")
