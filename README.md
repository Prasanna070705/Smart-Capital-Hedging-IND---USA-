# Regime-Aware FX Hedging for Indian Importers

A decision tool that tells an Indian importer how much of a future US-dollar payment to lock in with a forward
contract, given today's market regime and how much risk they can take.

Team AA11: Deep Amit Lodaya, Harigovind K, Vimal P Menon, Dasigi Prasanna Jagannath.

## Results at a Glance

Snapshot of 2026-09-18 (spot 95.87 INR per USD, market regime: Calm):

- **Unhedged risk:** a USD payment due in 6 months could cost 9.2% more in a 1-in-20 bad case (ES 11.7%).
- **Cost of hedging:** the 6-month forward is 96.62, a 0.78% premium over spot.
- **Recommendation:** a Balanced buyer should hedge 50% today (60% in a Normal market, 75% in a Crisis).
  Example: INR 10 crore due in 6 months -> book USD 521,540 forward; worst 1-in-20 extra cost INR 39.8 lakh
  instead of INR 71.7 lakh unhedged.
- **Backtest (2012-2026, 171 out-of-sample decisions):** the tool cut the worst outcome versus a fixed 50% hedge
  (5.65% vs 14.65% of cost) for 0.25 points more average cost. Regime detection improved the risk forecast but did
  not measurably improve hedging outcomes beyond the risk-budget rule.

## How to Run

    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    python src/run_all.py          # rebuilds every output and runs all 66 tests (about 20 seconds)
    streamlit run app.py           # opens the hedging advisor at http://localhost:8501

Results are fixed to the 2026-09-18 snapshot committed in `data/raw/`. To refresh the data, put
`FRED_API_KEY=...` in a `.env` file and run `python src/run_all.py --fetch`. The snapshot tests
(`tests/test_week1_smoke.py`, `tests/test_regime.py`, `tests/test_advisor.py`, `tests/test_app.py`) will then
fail until you review the new numbers and update their expected values.

## How It Works

| Stage | Script | Writes |
|---|---|---|
| 1. Ingestion | `src/ingestion.py` | `data/raw/*.csv` (8 FRED series) |
| 2. Features | `src/features.py` | `data/processed/processed_fx_master.csv` |
| 3. Baseline risk (Objective 1) | `src/risk_baseline.py`, `src/validate_risk.py` | `outputs/var_es.json`, `outputs/obj1_validation.json` |
| 4. Forward and static hedges (Objective 2) | `src/forward_pricing.py`, `src/static_hedge.py` | `outputs/forward_quotes.csv`, `outputs/static_hedge.csv` |
| 5. Regimes (Objective 3) | `src/regime_features.py`, `src/regime_model.py` | `models/scaler_v1.pkl`, `models/kmeans_v1.pkl`, `outputs/regime_labels.csv` |
| 6. Recommendation (Objective 4a) | `src/optimizer.py` | `outputs/utility_scores.csv`, `outputs/candidates_today.csv` |
| 7. Backtest | `src/backtest.py` | `outputs/backtest_decisions.csv`, `outputs/backtest_summary.csv` |
| 8. App (Objective 4b) | `app.py` using `src/advisor.py` | none (display only) |

All settings live in `src/config.py`. `src/run_all.py` runs stages 2-7 and the tests in order and stops at the
first failure. The app contains no finance of its own; it only calls `src/`.

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
| `us_tbill_rate.csv` | TB3MS | Monthly | 1934-01-01 | 2026-08-01 | 1,112 | 0 |
| `india_tbill_rate.csv` | INDIR3TIB01STM | Monthly | 2011-11-01 | 2026-07-01 | 177 | 0 |

**Common overlap across all series:** 1973-01 to 2025-03 (limited by India CPI). Excluding India CPI: 1973-01 to 2026-07.

**Notes:**
- `us_interest_rate` is the effective Fed Funds rate (replaced the US discount rate, which ended 2021-08).
- `india_interest_rate` is the call money rate (replaced the India discount rate, which ended 2022-07).
- `india_cpi` has no live FRED replacement, so it is used for training only. `india_reer` (CPI-based real effective exchange rate) is the live inflation signal.
- `us_tbill_rate` (US 3-month T-bill) and `india_tbill_rate` (India 3-month interbank rate) are the matching-tenor rates used to price the forward (added Day 5).

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
Real forward quote: not checked (see Limitations).

**Known limitations:**
- CIP estimates a fair forward; real quotes include a bank spread and India's capital-control frictions.
- India's rate is a 3-month interbank rate (no India T-bill series on FRED), priced a 6-month forward; TB3MS is on a discount basis.
- Rates carry a 2-month publication lag, so September's forward uses July's rates.
- Overnight rates would have overstated the premium by 0.28 percentage points a year (INR 132,000 on this exposure).
- The table's expected costs use the simulation's 2000-2026 average drift, not a forecast.

## Objective 3: Regime Detection (K-Means)

Three regimes from 20- and 60-day rupee volatility, 2000-2026 (6,697 days), scikit-learn K-Means, seed 42.

| Regime | vol_20d centre | Share of days | Next 6 months: volatility | Next 6 months: worst 5% move |
|---|---|---|---|---|
| Calm | 2.8% | 45% | 4.0% | 7.0% |
| Normal | 6.4% | 45% | 6.6% | 14.2% |
| Crisis | 12.7% | 11% | 10.2% | 13.2% |

Current regime (2026-09-18): Calm.

**Feature choice (deviation from plan):** the plan's inflation_diff ends in 2025-06 (India CPI), and both it and
rate_diff drift over decades, labelling 96-100% of 2022-2026 as Calm regardless of volatility. Volatility-only
regimes work live and describe market turbulence; the interest-rate gap is already priced by the forward (Objective 2).

**Choosing k:** inertia drops 43% from k=2 to k=3, then 26%, 23%, 17% (elbow at 3); silhouette is highest at
k=2 (0.556) but k=3 (0.468) is well separated and gives a middle state for gradual hedging.

**Validation:** GFC 100% Crisis, taper tantrum 94% Crisis, 2024 100% Calm; labels 99.97% identical across 3 seeds;
regimes predict next-6-month risk (table above); 35 tests pass.

**Known limitations:**
- K-Means labels each day independently: 6.3 regime changes per year, no persistence (an HMM would model it).
- COVID (Mar-May 2020) reads mostly Normal: RBI intervention held rupee volatility near 10%.
- The scaler and clusters are fit on all 2000-2026 data; the backtest refits on past data only.

## Objective 4a: Regime-Aware Hedge Recommendation

Recommended share of a 6-month USD payment to hedge with the forward (2026-09-18 snapshot, today's regime: Calm):

| Risk tolerance | Bad-case limit (VaR 95%, % of cost) | Calm | Normal | Crisis |
|---|---|---|---|---|
| Very cautious | 1.0% | 100% | 100% | 100% |
| Cautious | 2.5% | 75% | 80% | 85% |
| Balanced | 4.0% | 50% | 60% | 75% |
| Relaxed | 6.0% | 20% | 35% | 55% |
| Very relaxed | 9.0% | 0% | 0% | 30% |

**Method:** block bootstrap where each 10-day block comes from days in the path's current regime, with regimes
switching by historical 10-day transition probabilities; paths centred on the CIP forward; the recommendation is
the smallest hedge ratio (5% steps) whose VaR 95% fits the buyer's limit.

**Deviation from plan:** Cost + lambda x VaR is linear in the hedge ratio (both terms mix linearly), so it only ever
picks 0% or 100%; with the simulation's historical drift (1.6% vs a 0.78% premium) it always picked 100%, failing
the plan's sanity check. The risk-budget rule is its constrained form and gives graded answers.

**Validation:** regime simulation reproduces Objective 1's VaR (9.29% vs 9.20%); unhedged VaR rises Calm 7.2% ->
Normal 8.6% -> Crisis 12.2%; recommendations never fall as the regime worsens or tolerance tightens; 45 tests pass.

**Known limitations:**
- Centring on the forward assumes it is an unbiased forecast (supported by the Day 6 history check, not guaranteed).
- The simulation understates risk after Normal days (8.6% vs 14.2% actually observed), because Normal often preceded crises.
- No bank spread is included, and the risk levels (1-9%) are a design choice, not estimated from data.

## Objective 4b: Hedging Advisor App

`streamlit run app.py`. Inputs: payment amount (INR crore or USD), months until payment (1-12), risk tolerance
(5 levels or a custom limit in INR lakh). Three tabs:

- **Recommendation:** today's regime, the forward rate for that date, the hedge to book, the bad-case cost with and
  without it, a histogram of 10,000 simulated outcomes, every option compared, and the risk curve against the limit.
- **Track record:** the backtest table, forward premium vs the rupee's actual move since 2012, and the recommended
  hedge over time.
- **How it works:** method and limits in plain language.

Market data is cached once (`st.cache_resource`) and each payment date's simulation is cached (`st.cache_data`), so
changing the amount or risk level is instant. The app warns when the data snapshot is more than 30 days old.
`tests/test_app.py` runs the app headless (Streamlit `AppTest`) for the default inputs, both risk extremes, every
payment length and a USD / 1-month / tiny-limit edge case.

## Backtest (Walk-Forward, 2012-2026)

171 monthly decisions (2012-01 to 2026-03, about 28 independent 6-month periods). At each decision the scaler,
K-Means and regime names are refit on data up to that day only; the hedge is chosen exactly as the app does;
the cost is measured with the actual rupee rate 126 trading days later.

| Strategy (Balanced where dynamic) | Avg hedge | Avg extra cost | 1-in-20 bad case | Worst |
|---|---|---|---|---|
| Static 0% | 0% | 2.24% | 9.94% | 25.32% |
| Static 50% | 50% | 2.33% | 6.68% | 14.65% |
| Static 100% | 100% | 2.43% | 4.39% | 5.65% |
| Fixed at 79% (same average as regime-aware) | 79% | 2.39% | 4.63% | 8.36% |
| Regime-blind budget rule | 82% | 2.55% | 4.39% | 5.65% |
| Regime-aware budget rule | 79% | 2.58% | 4.39% | 5.65% |

**Findings:**
- Versus static 50%, the tool cuts the worst outcome from 14.65% to 5.65% of cost, for 0.25 points more average cost.
- Adjusting monthly beats a fixed hedge at the same average ratio on tail risk at every tolerance level
  (Balanced worst 5.65% vs 8.36%; Very relaxed 14.65% vs 20.37%), for 0.2-0.3 points more average cost.
- Regime-aware and regime-blind hedges gave nearly identical results: the benefit comes from the risk-budget rule.
- Regimes do improve the risk forecast: unhedged VaR 95% exceeded 2.9% of the time (4.7% regime-blind; target 5%),
  with lower forecasts in Calm months (8.2% vs 9.7%) and higher in Crisis (16.9% vs 12.8%).
- Average forward premium 2.43% vs average actual depreciation 2.24% per 6 months: hedging cost slightly more
  than it saved on average in this period.

**Limitations:** overlapping windows (about 28 independent periods); only 16 Crisis months; in 2012-2016 the premium
(about 4%) exceeded the Balanced limit, forcing 100% hedges; model pickle is not byte-reproducible across runs on
multi-threaded machines (its outputs are).

## Deviations from the Proposal

Each change below was tested before it was made; the evidence is in the section named.

| Proposal | Built | Why | Evidence |
|---|---|---|---|
| Sample random single days | 10-day blocks | Single days destroy volatility clustering | Objective 1: 90% of clustering kept vs 0% |
| Chain 180 days for 6 months | 126 trading days | 180 is calendar days; 180 trading days is 8.5 months | Objective 1 |
| Last 20 years of history | 2000-2026 | Covers GFC, taper tantrum and COVID; pre-2000 rupee was managed | Objective 1 |
| 6-month interest rates | 3-month rates for both countries | No live 6-month India rate on FRED; tenors still match | Objective 2 |
| Inflation differential as a regime feature | Volatility only | India CPI stops in 2025; macro gaps label eras, not market states | Objective 3 |
| Utility = Cost + lambda x VaR | Smallest hedge within a VaR budget | The linear utility only ever picks 0% or 100% | Objective 4a |
| Hold out the last 6-12 months | Walk-forward, 171 monthly decisions | A 6-12 month hold-out gives only 1-2 outcomes | Backtest |

## Limitations and Future Work

**Data**
- Fixed snapshot (2026-09-18); the app does not fetch live data. Future work: refresh automatically when the
  snapshot is more than a day old.
- Monthly rates carry a 2-month publication lag; India's rate is an interbank rate; India CPI stops in 2025-03.

**Pricing**
- The forward is a covered-interest-parity estimate. A bank's quote adds a spread, so real hedging costs slightly
  more than shown. A real quote has not yet been compared (`REAL_FORWARD_PREMIUM_ANNUAL_PCT` in `src/config.py`).

**Model**
- Simulations resample 2000-2026 history, so they cannot produce a daily move larger than any seen since 2000, and
  volatility clustering beyond 10 days is lost.
- K-Means ignores regime persistence (6.3 changes per year). Future work: a Hidden Markov Model.
- The risk levels (1-9% of cost) are a design choice, not estimated from data.

**Evidence**
- The backtest has about 28 independent 6-month periods and 16 Crisis months, so small differences are noise.
- Regime detection improved risk forecasts but not realised hedging outcomes in 2012-2026.

**Reproducibility**
- All outputs are byte-for-byte reproducible from the committed data. `models/kmeans_v1.pkl` itself can differ in
  its last decimals on multi-threaded machines; its labels and scores do not.

This is a model built on past data, not financial advice.

## References

- Engle, R. (2002). Dynamic Conditional Correlation: A Simple Class of Multivariate Generalized Autoregressive
  Conditional Heteroskedasticity Models. *Journal of Business & Economic Statistics*, 20(3), 339-350.
- Cappiello, L., Engle, R. and Sheppard, K. (2006). Asymmetric Dynamics in the Correlations of Global Equity and
  Bond Returns. *Journal of Financial Econometrics*, 4(4), 537-572.
- Data: Federal Reserve Bank of St. Louis, FRED (series listed under Raw Data Coverage).


## Version 1.1: Insights, Charts and an Optional Chatbot

**New in the app:** an answer card with Indian number formatting and tooltips; charts that mark the buyer's limit,
the hedged bad case and the recommended ratio; a regime timeline; an Insights tab (is hedging cheap now, break-even
rate, payment-date curve, replay of 1991/2008/2013/2018/2020, the bank's real quote, a downloadable summary); and an
Ask tab.

**Two modes, chosen automatically:**

| Situation | Behaviour |
|---|---|
| Internet and `CHAT_API_KEY` in `.env` | Full app plus the Ask tab chatbot |
| Offline, no key, or provider down | Full hedge recommendation app; the Ask tab explains why chat is off |

**Chatbot design:** free OpenAI-compatible API (Groq free tier, model in `src/config.py`); retrieval-augmented with
TF-IDF over this README and a glossary; the live recommendation in every prompt; two tools that run the project's
own model (`run_hedge_model`, `hedging_cost_context`); every number in an answer checked against the prompt and tool
results. Questions and on-screen numbers are sent to the provider; no personal data is involved.

**Evaluation** (`tests/chatbot_eval.py`, 15 questions with known answers, checked for facts, grounding and tool use):
[your score]/15 with [model ID] on [date]. [One line per failure and what it shows.]

**Stress replay finding:** a repeat of 2008 or 2013 would cost a Balanced buyer about twice their limit even with
the recommended hedge (INR 80 and 73 lakh vs a 40 lakh limit on INR 10 crore); single historical crises sit
beyond the simulation's 1-in-20 bad case.
