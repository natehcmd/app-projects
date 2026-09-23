#!/usr/bin/env python3
"""
Bond Yield Calculator
======================
Standalone implementation of item #4 from the source listicle
("Bond Yield Calculator: yield to maturity, duration, convexity, and bond
pricing with interactive graphs"). No external market-data feed or API key
is needed -- all inputs are numbers you supply (face value, coupon rate,
market price, years to maturity, payments/year).

Computes, for a standard fixed-coupon bond:
  - Clean price given a yield (bond pricing)
  - Yield to Maturity (YTM) given a market price, via Newton-Raphson with
    a bisection fallback for robustness
  - Macaulay duration
  - Modified duration
  - Convexity
  - A price-vs-yield curve (list of (yield, price) points) you can feed
    into any plotting library (matplotlib, Chart.js, Plotly, etc.) -- this
    stands in for the "interactive graphs" the original idea mentions,
    without pulling in a GUI/plotting dependency.

Usage (CLI):
    python3 bond_calculator.py --face 1000 --coupon 0.05 --price 950 \
        --years 10 --freq 2

    python3 bond_calculator.py --face 1000 --coupon 0.05 --yield 0.06 \
        --years 10 --freq 2 --price-only

Usage (library):
    from bond_calculator import Bond
    b = Bond(face_value=1000, coupon_rate=0.05, years_to_maturity=10, freq=2)
    ytm = b.yield_to_maturity(market_price=950)
    print(b.macaulay_duration(ytm), b.modified_duration(ytm), b.convexity(ytm))
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass


@dataclass
class Bond:
    face_value: float
    coupon_rate: float  # annual coupon rate, e.g. 0.05 for 5%
    years_to_maturity: float
    freq: int = 2  # coupon payments per year (2 = semiannual)

    def _periods(self) -> int:
        return round(self.years_to_maturity * self.freq)

    def _coupon_per_period(self) -> float:
        return self.face_value * self.coupon_rate / self.freq

    def price(self, annual_yield: float) -> float:
        """Present value of all cash flows discounted at annual_yield."""
        n = self._periods()
        c = self._coupon_per_period()
        r = annual_yield / self.freq
        if n <= 0:
            return self.face_value
        pv = 0.0
        for t in range(1, n + 1):
            cash_flow = c + (self.face_value if t == n else 0.0)
            pv += cash_flow / (1 + r) ** t
        return pv

    def yield_to_maturity(
        self,
        market_price: float,
        guess: float = 0.05,
        tol: float = 1e-8,
        max_iter: int = 100,
    ) -> float:
        """Solve for the annual yield that makes price(yield) == market_price.

        Uses Newton-Raphson (fast) with a bisection fallback (robust) in
        case the derivative estimate misbehaves or the guess is far off.
        """
        y = guess
        for _ in range(max_iter):
            p = self.price(y)
            diff = p - market_price
            if abs(diff) < tol:
                return y
            # Numerical derivative dP/dy
            h = 1e-6
            dp = (self.price(y + h) - self.price(y - h)) / (2 * h)
            if dp == 0:
                break
            y_next = y - diff / dp
            if y_next <= -0.99:  # keep it in a sane range
                y_next = (y - 0.99) / 2
            y = y_next

        # Fallback: bisection over a wide, sane yield range.
        lo, hi = -0.5, 2.0
        p_lo, p_hi = self.price(lo) - market_price, self.price(hi) - market_price
        if p_lo * p_hi > 0:
            raise ValueError(
                "Could not bracket a YTM solution for the given inputs; "
                "check that market_price is between deeply-discounted and "
                "deeply-premium bond prices."
            )
        for _ in range(200):
            mid = (lo + hi) / 2
            p_mid = self.price(mid) - market_price
            if abs(p_mid) < tol:
                return mid
            if p_lo * p_mid < 0:
                hi, p_hi = mid, p_mid
            else:
                lo, p_lo = mid, p_mid
        return (lo + hi) / 2

    def macaulay_duration(self, annual_yield: float) -> float:
        """Weighted-average time (in years) to receive the bond's cash flows."""
        n = self._periods()
        c = self._coupon_per_period()
        r = annual_yield / self.freq
        price = self.price(annual_yield)
        if price == 0:
            return 0.0
        weighted_sum = 0.0
        for t in range(1, n + 1):
            cash_flow = c + (self.face_value if t == n else 0.0)
            pv = cash_flow / (1 + r) ** t
            weighted_sum += (t / self.freq) * pv
        return weighted_sum / price

    def modified_duration(self, annual_yield: float) -> float:
        mac = self.macaulay_duration(annual_yield)
        r = annual_yield / self.freq
        return mac / (1 + r)

    def convexity(self, annual_yield: float) -> float:
        """Second-order sensitivity of price to yield (per year^2), used
        alongside modified duration to better approximate price changes
        for larger yield moves."""
        n = self._periods()
        c = self._coupon_per_period()
        r = annual_yield / self.freq
        price = self.price(annual_yield)
        if price == 0:
            return 0.0
        total = 0.0
        for t in range(1, n + 1):
            cash_flow = c + (self.face_value if t == n else 0.0)
            pv = cash_flow / (1 + r) ** t
            total += pv * t * (t + 1)
        convexity_periods = total / (price * (1 + r) ** 2)
        # Convert from per-period^2 to per-year^2
        return convexity_periods / (self.freq ** 2)

    def price_yield_curve(self, y_min: float = 0.0, y_max: float = 0.20, steps: int = 41):
        """Returns [(yield, price), ...] points for plotting a price/yield curve."""
        if steps < 2:
            steps = 2
        step_size = (y_max - y_min) / (steps - 1)
        return [
            (round(y_min + i * step_size, 6), round(self.price(y_min + i * step_size), 4))
            for i in range(steps)
        ]

    def summary(self, market_price: float | None = None, annual_yield: float | None = None) -> dict:
        """Convenience: given either a market price or a yield, compute the rest."""
        if market_price is None and annual_yield is None:
            raise ValueError("Provide either market_price or annual_yield.")
        if annual_yield is None:
            annual_yield = self.yield_to_maturity(market_price)
        if market_price is None:
            market_price = self.price(annual_yield)

        return {
            "face_value": self.face_value,
            "coupon_rate": self.coupon_rate,
            "years_to_maturity": self.years_to_maturity,
            "payments_per_year": self.freq,
            "market_price": round(market_price, 4),
            "yield_to_maturity": round(annual_yield, 6),
            "macaulay_duration_years": round(self.macaulay_duration(annual_yield), 4),
            "modified_duration": round(self.modified_duration(annual_yield), 4),
            "convexity": round(self.convexity(annual_yield), 4),
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="Bond yield / duration / convexity calculator")
    ap.add_argument("--face", type=float, default=1000.0, help="Face (par) value, default 1000")
    ap.add_argument("--coupon", type=float, required=True, help="Annual coupon rate as a decimal, e.g. 0.05")
    ap.add_argument("--years", type=float, required=True, help="Years to maturity")
    ap.add_argument("--freq", type=int, default=2, help="Coupon payments per year, default 2 (semiannual)")
    ap.add_argument("--price", type=float, default=None, help="Market price (solves for YTM)")
    ap.add_argument("--yield", dest="ytm", type=float, default=None, help="Annual yield as a decimal (solves for price)")
    ap.add_argument("--price-only", action="store_true", help="Only print price for the given --yield")
    ap.add_argument("--curve", action="store_true", help="Also print a price/yield curve as JSON")
    args = ap.parse_args()

    if args.price is None and args.ytm is None:
        ap.error("Provide --price (to solve YTM) or --yield (to solve price).")

    bond = Bond(face_value=args.face, coupon_rate=args.coupon, years_to_maturity=args.years, freq=args.freq)

    if args.price_only:
        if args.ytm is None:
            ap.error("--price-only requires --yield")
        print(json.dumps({"price": round(bond.price(args.ytm), 4)}, indent=2))
        return 0

    result = bond.summary(market_price=args.price, annual_yield=args.ytm)
    if args.curve:
        result["price_yield_curve"] = bond.price_yield_curve()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
