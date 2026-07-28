"""
Quick sanity checks for bond_calculator.py. Run with:
    python3 test_bond_calculator.py
No pytest dependency required -- plain asserts, exits nonzero on failure.
"""
from bond_calculator import Bond


def approx(a, b, tol=1e-4):
    return abs(a - b) < tol


def test_par_bond_price_equals_face_value():
    # A bond priced at its own coupon rate should be worth par (face value).
    b = Bond(face_value=1000, coupon_rate=0.05, years_to_maturity=10, freq=2)
    assert approx(b.price(0.05), 1000.0, tol=0.5), b.price(0.05)


def test_ytm_roundtrip():
    # Solve for YTM at a known price, then re-price at that YTM and confirm
    # we get the same price back.
    b = Bond(face_value=1000, coupon_rate=0.06, years_to_maturity=15, freq=2)
    market_price = 950.0
    ytm = b.yield_to_maturity(market_price)
    assert approx(b.price(ytm), market_price, tol=0.01)


def test_discount_bond_has_ytm_above_coupon():
    b = Bond(face_value=1000, coupon_rate=0.04, years_to_maturity=10, freq=2)
    ytm = b.yield_to_maturity(900.0)  # trading below par
    assert ytm > 0.04


def test_premium_bond_has_ytm_below_coupon():
    b = Bond(face_value=1000, coupon_rate=0.04, years_to_maturity=10, freq=2)
    ytm = b.yield_to_maturity(1100.0)  # trading above par
    assert ytm < 0.04


def test_duration_and_convexity_positive():
    b = Bond(face_value=1000, coupon_rate=0.05, years_to_maturity=10, freq=2)
    ytm = 0.05
    mac = b.macaulay_duration(ytm)
    mod = b.modified_duration(ytm)
    conv = b.convexity(ytm)
    assert mac > 0 and mod > 0 and conv > 0
    assert mod < mac  # modified duration is always slightly less than Macaulay


def test_zero_coupon_duration_equals_maturity():
    # A zero-coupon bond's Macaulay duration equals its time to maturity.
    b = Bond(face_value=1000, coupon_rate=0.0, years_to_maturity=5, freq=2)
    mac = b.macaulay_duration(0.05)
    assert approx(mac, 5.0, tol=0.01)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {t.__name__}: {e}")
    if failures:
        raise SystemExit(f"{failures} test(s) failed")
    print(f"All {len(tests)} tests passed.")
