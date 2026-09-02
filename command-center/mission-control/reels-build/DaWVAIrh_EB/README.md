# Bond Yield Calculator

## Source material and what I actually built

The source reel ("10 Finance Projects to Build This Weekend") is a listicle:
10 finance app ideas, each with a one-sentence description and a generic
tech-stack tag (React/Supabase, Next.js/PostgreSQL, etc.). None of the 10
items is described in enough depth to be a real spec — no formulas, no data
schema, no algorithm. It's inspiration/hype content, not a buildable design
doc.

Rather than decline outright, I picked the single item on the list that has
a well-defined, well-known, *computable* technique behind it and implemented
that fully and correctly: **item #4, the Bond Yield Calculator** ("Calculate
yield to maturity, duration, convexity, and bond pricing with interactive
graphs"). Bond pricing/YTM/duration/convexity are standard fixed-income
formulas — unlike the other 9 items (which mostly imply pulling in brokerage
transaction data, insider-trading filings, 13F filings, or live market feeds
that this tool has no access to and that would require real setup/API keys
to be meaningful), this one is fully self-contained: you supply bond terms
and it does the math. No external data source, scraping, or API key needed.

## What it does

Given a bond's face value, coupon rate, years to maturity, and payment
frequency, this tool computes:

- **Price** at a given yield (present value of coupon + principal cash flows)
- **Yield to Maturity (YTM)** given a market price (solved numerically via
  Newton-Raphson with a bisection fallback for robustness)
- **Macaulay duration** — weighted-average time to receive cash flows
- **Modified duration** — approximate % price sensitivity to a 1% yield change
- **Convexity** — second-order price sensitivity, for more accurate estimates
  on larger yield moves
- **Price-vs-yield curve** — a list of `(yield, price)` points you can feed
  straight into a plotting library (matplotlib, Chart.js, Plotly, etc.) —
  this stands in for the "interactive graphs" mentioned in the original idea
  without pulling in a GUI dependency for a CLI tool.

## Setup / API keys

None. Pure Python standard library — no dependencies, no signup, no API key.
Requires Python 3.8+.

## How to run

**Solve for YTM given a market price** (semiannual $1,000 face bond, 5%
coupon, 10 years to maturity, trading at $950):

```bash
python3 bond_calculator.py --coupon 0.05 --years 10 --price 950
```

Output:
```json
{
  "face_value": 1000.0,
  "coupon_rate": 0.05,
  "years_to_maturity": 10.0,
  "payments_per_year": 2,
  "market_price": 950.0,
  "yield_to_maturity": 0.056617,
  "macaulay_duration_years": 7.9273,
  "modified_duration": 7.709,
  "convexity": 72.4089
}
```

**Solve for price given a yield** (add `--price-only` for just the price):

```bash
python3 bond_calculator.py --coupon 0.05 --years 10 --yield 0.06 --price-only
```

**Include a price/yield curve for plotting**:

```bash
python3 bond_calculator.py --coupon 0.05 --years 10 --price 950 --curve
```

**Custom face value / payment frequency** (e.g. annual-pay bond, $100 face):

```bash
python3 bond_calculator.py --face 100 --coupon 0.03 --years 5 --freq 1 --price 98
```

**Use as a library**:

```python
from bond_calculator import Bond

b = Bond(face_value=1000, coupon_rate=0.05, years_to_maturity=10, freq=2)
ytm = b.yield_to_maturity(market_price=950)
print(b.macaulay_duration(ytm), b.modified_duration(ytm), b.convexity(ytm))
print(b.price_yield_curve())  # [(yield, price), ...] for a chart
```

**Run the test suite** (plain asserts, no pytest needed):

```bash
python3 test_bond_calculator.py
```

## Files

- `bond_calculator.py` — the `Bond` class + CLI entry point
- `test_bond_calculator.py` — sanity tests (par pricing, YTM roundtrip,
  discount/premium yield direction, duration/convexity sign and ordering,
  zero-coupon duration-equals-maturity check)
- `README.md` — this file
