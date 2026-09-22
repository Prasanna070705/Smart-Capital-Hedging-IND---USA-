# Regime-Aware FX Hedging

## Raw Data Coverage (`data/raw/`)

Pulled from FRED on 2026-09-22. Dates are the first and last observations that have a value.

| File | FRED series | Frequency | Start | End | Rows | Missing values |
|---|---|---|---|---|---|---|
| `usd_inr_spot.csv` | DEXINUS | Daily | 1973-01-02 | 2026-09-18 | 14,014 | 551 (market holidays) |
| `us_cpi.csv` | CPIAUCSL | Monthly | 1947-01-01 | 2026-08-01 | 956 | 1 (2025-10) |
| `india_cpi.csv` | INDCPIALLMINMEI | Monthly | 1957-01-01 | 2025-03-01 | 819 | 0 |
| `us_interest_rate.csv` | FEDFUNDS | Monthly | 1954-07-01 | 2026-08-01 | 866 | 0 |
| `india_interest_rate.csv` | IRSTCI01INM156N | Monthly | 1968-01-01 | 2026-07-01 | 703 | 0 |
| `india_reer.csv` | CCRETT01INM661N | Monthly | 1970-01-01 | 2026-08-01 | 680 | 0 |

**Common overlap across all series:** 1973-01 to 2025-03 (limited by India CPI). Excluding India CPI: 1973-01 to 2026-07.

**Notes:**
- `us_interest_rate` is the effective Fed Funds rate (replaced the US discount rate, which ended 2021-08).
- `india_interest_rate` is the call money rate (replaced the India discount rate, which ended 2022-07).
- `india_cpi` has no live FRED replacement, so it is used for training only. `india_reer` (CPI-based real effective exchange rate) is the live inflation signal.

## Objective 1: Baseline Risk (Monte Carlo)

Unhedged USD 1,000,000 payment due in 6 months, as of 2026-09-18 (spot 95.87):

| Measure | Value |
|---|---|
| VaR 95% | INR 8.82 million (9.20% of today's cost) |
| ES 95% | INR 11.25 million (11.73% of today's cost) |
| Median rate in 6 months | 97.20 |

**Method:** moving-block bootstrap of daily log returns, 10,000 paths x 126 trading days, 10-day blocks, history from 2000-01-01, seed 42.

**Validation** (`src/validate_risk.py`, `tests/test_risk_baseline.py`):
- Parametric normal VaR is 9.49% (ES 11.63%); Monte Carlo / parametric = 0.97.
- 10-day blocks keep 90% of the historical lag-1 volatility clustering (0.277 vs 0.307); i.i.d. day sampling keeps 0%.
- VaR ranges only 8.99%-9.42% across block lengths 1, 5, 10 and 20.
- 9 unit tests pass, including a hand-calculated VaR/ES.

**Known limitations:**
- Clustering beyond the 10-day block length is not preserved.
- The simulation resamples 2000-2026 history, so it inherits that period's average rupee depreciation (about 1.4% per 6 months) and cannot produce a single-day move larger than any seen since 2000.
- The 6-month VaR is point-in-time (rate on the payment date), not path-dependent.


## Objective 2: Static Hedging (Forward Contract)

6-month forward by covered interest parity, as of 2026-09-18: spot 95.87, India 3-month rate 5.32%,
US 3-month T-bill 3.73% (July values) -> forward 96.6182, premium 0.78% for 6 months (1.56% annualised).

| Hedged | Locked cost | Expected extra cost | VaR 95% | ES 95% |
|---|---|---|---|---|
| 0% | 0.00 | 1.51 | 8.82 | 11.25 |
| 25% | 0.19 | 1.32 | 6.80 | 8.62 |
| 50% | 0.37 | 1.13 | 4.78 | 6.00 |
| 75% | 0.56 | 0.94 | 2.77 | 3.37 |
| 100% | 0.75 | 0.75 | 0.75 | 0.75 |

INR millions of extra cost vs paying at today's spot, USD 1,000,000 exposure, same 10,000 paths as Objective 1.

**History check (2012-2026, 3,554 windows):** average forward premium 2.43% vs average actual depreciation
2.24% per 6 months; the forward beat waiting in 46% of windows (range -13.3% to +20.5%).

**Validation:** forward hand-checked on a calculator; overnight-rate forward 96.7504 reproduced; 22 unit tests pass.
Real forward quote: [value, source, date] -> gap [x] percentage points vs CIP.

**Known limitations:**
- CIP estimates a fair forward; real quotes include a bank spread and India's capital-control frictions.
- India's rate is a 3-month interbank rate (no India T-bill series on FRED), priced a 6-month forward; TB3MS is on a discount basis.
- Rates carry a 2-month publication lag, so September's forward uses July's rates.
- Overnight rates would have overstated the premium by 0.28 percentage points a year (INR 132,000 on this exposure).
- The table's expected costs use the simulation's 2000-2026 average drift, not a forecast.


## How to Run

    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    python src/run_all.py

Rebuilds every output in `outputs/` from the committed raw data in `data/raw/` (about 3 seconds)
and runs all 29 tests. Results are fixed to the 2026-09-18 snapshot.

To refresh the data, put `FRED_API_KEY=...` in a `.env` file and run `python src/run_all.py --fetch`.
The snapshot test in `tests/test_week1_smoke.py` will then fail until you review the new numbers
and update its expected values.
