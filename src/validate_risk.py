# src/validate_risk.py
# Objective 1 validation: does the Monte Carlo engine give sensible numbers?
# Run from the fx-hedging root (after risk_baseline.py):  python src/validate_risk.py
import json
from statistics import NormalDist

import numpy as np

from config import (OUTPUTS_DIR, VAR_ES_FILE, HORIZON_DAYS, BLOCK_LEN, CONFIDENCE, RANDOM_SEED)
from risk_baseline import load_history, block_bootstrap, var_es

VALIDATION_FILE = OUTPUTS_DIR / "obj1_validation.json"
BLOCK_LENGTHS_TO_TEST = [1, 5, 10, 20]   # 1 = plain i.i.d. day sampling
N_SIMS = 10_000
ACF_LAGS = [1, 5, 10, 20]


def parametric_var_es(returns, horizon, confidence):
    """Textbook VaR/ES assuming 6-month log returns are normally distributed.
    Returned as % cost increase, so they compare directly with the Monte Carlo figures."""
    mu = returns.mean() * horizon
    sd = returns.std() * np.sqrt(horizon)
    z = NormalDist().inv_cdf(confidence)
    var_pct = (np.exp(mu + z * sd) - 1) * 100
    # Mean of exp(X) in the worst tail, for normal X (standard lognormal result)
    es_pct = (np.exp(mu + sd**2 / 2) * NormalDist().cdf(sd - z) / (1 - confidence) - 1) * 100
    return var_pct, es_pct


def mc_var_es_pct(returns, block_len, rng):
    """Monte Carlo VaR/ES (% cost increase) for a given block length."""
    sims = block_bootstrap(returns, N_SIMS, HORIZON_DAYS, block_len, rng)
    pct_change = (np.exp(sims.sum(axis=1)) - 1) * 100
    return var_es(pct_change, CONFIDENCE), sims


def abs_return_acf(series_2d, lag):
    """Autocorrelation of absolute daily returns at a given lag, pooled across paths.
    High values = volatility clustering (big moves follow big moves)."""
    x = np.abs(series_2d)
    x = x - x.mean()
    return float((x[:, :-lag] * x[:, lag:]).mean() / (x * x).mean())


def main():
    returns, _, _ = load_history()
    mc = json.loads(VAR_ES_FILE.read_text())
    results = {}

    # ---- 1. Monte Carlo vs parametric VaR ----
    p_var, p_es = parametric_var_es(returns, HORIZON_DAYS, CONFIDENCE)
    ratio = mc["var_pct_of_cost"] / p_var
    print("1. Monte Carlo vs parametric (normal) VaR, % of today's cost")
    print(f"   {'':22s}{'VaR':>8s}{'ES':>8s}")
    print(f"   {'Monte Carlo (block ' + str(BLOCK_LEN) + ')':22s}{mc['var_pct_of_cost']:>7.2f}%{mc['es_pct_of_cost']:>7.2f}%")
    print(f"   {'Parametric normal':22s}{p_var:>7.2f}%{p_es:>7.2f}%")
    print(f"   Ratio MC / parametric VaR: {ratio:.2f}  (pass if 0.75 - 1.25)")
    results["parametric"] = {"var_pct": round(p_var, 3), "es_pct": round(p_es, 3),
                             "mc_var_pct": mc["var_pct_of_cost"], "ratio": round(ratio, 3),
                             "pass": bool(0.75 <= ratio <= 1.25)}

    # ---- 2. Does the block length keep volatility clustering? ----
    hist_2d = returns[None, :]
    hist_acf = {lag: abs_return_acf(hist_2d, lag) for lag in ACF_LAGS}
    print("\n2. Volatility clustering: autocorrelation of |daily return| at each lag")
    print(f"   {'':14s}" + "".join(f"{'lag ' + str(l):>9s}" for l in ACF_LAGS) + f"{'VaR 95%':>10s}")
    print(f"   {'History':14s}" + "".join(f"{hist_acf[l]:>9.3f}" for l in ACF_LAGS))
    results["clustering"] = {"history": {str(l): round(v, 3) for l, v in hist_acf.items()}}

    for bl in BLOCK_LENGTHS_TO_TEST:
        rng = np.random.default_rng(RANDOM_SEED)
        (v, _), sims = mc_var_es_pct(returns, bl, rng)
        acf = {lag: abs_return_acf(sims, lag) for lag in ACF_LAGS}
        label = f"Block {bl}" + (" (iid)" if bl == 1 else "") + (" <-" if bl == BLOCK_LEN else "")
        print(f"   {label:14s}" + "".join(f"{acf[l]:>9.3f}" for l in ACF_LAGS) + f"{v:>9.2f}%")
        results["clustering"][f"block_{bl}"] = {**{str(l): round(a, 3) for l, a in acf.items()},
                                                "var_pct": round(float(v), 3)}

    chosen = results["clustering"][f"block_{BLOCK_LEN}"]
    kept = chosen["1"] / hist_acf[1]
    iid_lag1 = results["clustering"]["block_1"]["1"]
    print(f"\n   Block {BLOCK_LEN} keeps {kept:.0%} of the historical lag-1 clustering "
          f"(pass if >= 80%); iid keeps {iid_lag1 / hist_acf[1]:.0%}")
    results["clustering"]["lag1_kept_share"] = round(kept, 3)
    results["clustering"]["pass"] = bool(kept >= 0.8)

    # ---- Summary ----
    all_pass = results["parametric"]["pass"] and results["clustering"]["pass"]
    results["all_pass"] = all_pass
    VALIDATION_FILE.write_text(json.dumps(results, indent=2))
    print(f"\n{'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'} - saved {VALIDATION_FILE.name} to outputs/")


if __name__ == "__main__":
    main()