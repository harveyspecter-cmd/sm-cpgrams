"""
Step 2. Compute every number used in the report, deck and dashboard.

Reads   data/raw/secondary/*.csv  and  data/raw/primary/*.csv
Writes  outputs/metrics.json      (single source of truth for all headline numbers)
        outputs/tables/*.csv      (analysis tables that back each exhibit)

Sections
    A  Government side (secondary data)
       A1 Central stock and flow, Little's Law, arrival variability
       A2 Reform interrupted time series (H4)
       A3 Ageing tail and two-class service time calibration
       A4 35-department ageing audit, Pareto and Spearman tests
       A5 GRAI ministry-month panel regressions (H1, H2)
       A6 ATR gap and active GRO ratio
       A7 Feedback funnel and survey bounds (H5)
       A8 CPENGRAMS and Parliamentary ledgers
       A9 Queuing, pooling and variability (H3)
    B  Citizen side (primary data)
       B1 Eighteen service KPIs
       B2 Department roll up and failure Pareto
       B3 Channels, CSAT, expectation gap
       B4 Routing test (Fisher exact)
    C  Triangulation of both sides

Run from the repository root
    python code/02_analysis.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import optimize, stats

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "data" / "raw" / "secondary"
PRI = ROOT / "data" / "raw" / "primary"
OUT = ROOT / "outputs"
TAB = OUT / "tables"

M: dict = {}  # metrics collector


def r(x, d=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), d)


def save(df: pd.DataFrame, name: str):
    df.to_csv(TAB / f"{name}.csv", index=False)


# =============================================================================
# A1  Central stock and flow
# =============================================================================
def a1_central():
    c = pd.read_csv(SEC / "01_Central_Monthly_2024_2026.csv")
    c["Year"] = c["Month"].str[:4]
    c["Clearance"] = c["Disposals"] / c["Receipts"]
    c["Net_Flow"] = c["Receipts"] - c["Disposals"]
    c["Stock_Change"] = c["Closing_Pending"].diff()
    c["Residual"] = c["Stock_Change"] - c["Net_Flow"]
    # Little's Law  W = L / throughput,  throughput = disposals per day
    c["Daily_Disposals"] = c["Disposals"] / c["Days"]
    c["Little_W_days"] = c["Closing_Pending"] / c["Daily_Disposals"]
    save(c, "A1_central_monthly_derived")

    by_year = c.groupby("Year").agg(
        months=("Month", "count"),
        receipts=("Receipts", "sum"),
        disposals=("Disposals", "sum"),
        mean_monthly_receipts=("Receipts", "mean"),
        sd_monthly_receipts=("Receipts", "std"),
        mean_W=("Little_W_days", "mean"),
        residual_sum=("Residual", "sum"),
    ).reset_index()
    by_year["CV_arrivals"] = by_year["sd_monthly_receipts"] / by_year["mean_monthly_receipts"]
    by_year["clearance"] = by_year["disposals"] / by_year["receipts"]
    save(by_year, "A1_central_by_year")

    res = c["Residual"].dropna()
    M["central"] = {
        "months": int(len(c)),
        "receipts_total": int(c["Receipts"].sum()),
        "disposals_total": int(c["Disposals"].sum()),
        "clearance_total": r(c["Disposals"].sum() / c["Receipts"].sum() * 100),
        "W_by_year": {y: r(v) for y, v in zip(by_year["Year"], by_year["mean_W"])},
        "CV_by_year": {y: r(v, 3) for y, v in zip(by_year["Year"], by_year["CV_arrivals"])},
        "CV_all": r(c["Receipts"].std() / c["Receipts"].mean(), 3),
        "CV_all_ex_mar2024": r(c.loc[c.Month != "2024-03", "Receipts"].std()
                               / c.loc[c.Month != "2024-03", "Receipts"].mean(), 3),
        "mean_receipts_by_year": {y: r(v, 0) for y, v in zip(by_year["Year"], by_year["mean_monthly_receipts"])},
        "residual_positive": int((res > 0).sum()),
        "residual_transitions": int(len(res)),
        "residual_sum": int(res.sum()),
        "residual_by_year": {y: int(v) for y, v in zip(by_year["Year"], by_year["residual_sum"])},
        "W_oct2026": r(c.loc[c.Month == "2026-10", "Little_W_days"].iloc[0]),
        "pending_aug2026": int(c.loc[c.Month == "2026-08", "Closing_Pending"].iloc[0]),
        "pending_oct2026": int(c.loc[c.Month == "2026-10", "Closing_Pending"].iloc[0]),
        "peak_receipts_2026": int(c.loc[c.Year == "2026", "Receipts"].max()),
        "mean_receipts_2025": r(c.loc[c.Year == "2025", "Receipts"].mean(), 0),
        "mean_receipts_2026": r(c.loc[c.Year == "2026", "Receipts"].mean(), 0),
    }
    # appeals (failure demand). Field holds "received / disposed / pending"
    ap = c[c.Month.str.startswith("2026")].copy()
    ap["App_Rec"] = ap["Appeals_Rec_Disp_Pend"].str.split("/").str[0].str.replace(",", "").astype(float)
    M["central"]["appeals_2026"] = int(ap.App_Rec.sum())
    M["central"]["appeal_per_100_disposals_2026"] = r(ap.App_Rec.sum() / ap.Disposals.sum() * 100, 1)
    M["central"]["receipts_growth_2025_2026_pct"] = r(
        (M["central"]["mean_receipts_2026"] / M["central"]["mean_receipts_2025"] - 1) * 100, 1)
    return c


# =============================================================================
# A2  Interrupted time series around the reforms (H4)
# =============================================================================
def a2_its(c: pd.DataFrame):
    d = c.copy().reset_index(drop=True)
    d["t"] = np.arange(len(d))
    d["post21"] = (d["Month"] >= "2024-09").astype(int)       # 21-day rule 23 Aug 2024
    d["postRev"] = (d["Month"] >= "2025-03").astype(int)      # Review Module 14 Feb 2025
    d["t_post21"] = d["t"] * d["post21"]
    d["mar24"] = (d["Month"] == "2024-03").astype(int)
    fit = smf.ols("Little_W_days ~ t + post21 + t_post21 + postRev + mar24", data=d).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3})
    tbl = pd.DataFrame({
        "term": fit.params.index, "coef": fit.params.values,
        "se_HAC": fit.bse.values, "p": fit.pvalues.values})
    save(tbl, "A2_interrupted_time_series_W")
    pre = d.loc[d.post21 == 0, "Little_W_days"]
    post = d.loc[d.post21 == 1, "Little_W_days"]
    welch = stats.ttest_ind(pre, post, equal_var=False)
    M["its"] = {
        "n": int(fit.nobs), "r2": r(fit.rsquared, 3),
        "coef": {k: r(v, 3) for k, v in fit.params.items()},
        "p": {k: r(v, 4) for k, v in fit.pvalues.items()},
        "W_pre21_mean": r(pre.mean()), "W_post21_mean": r(post.mean()),
        "welch_t": r(welch.statistic, 2), "welch_p": r(welch.pvalue, 4),
    }


# =============================================================================
# A3  Ageing tail and two-class (hyperexponential) calibration
# =============================================================================
def a3_tail(c: pd.DataFrame):
    """Government reports a mean time near 12 days yet about 32 percent of open
    stock is older than 21 days. A single exponential cannot give both.
    We fit a two-class mixture. Routine cases have mean m1. Complex cases have
    mean m2 and share q of arrivals.

        Mean time           W  = (1-q) m1 + q m2
        Stock share >21d    S  = [ (1-q) m1 e^(-21/m1) + q m2 e^(-21/m2) ] / W

    m1 is set from the ministry level average resolution days reported in the
    2026 GRAI tables for the fastest quartile of Group A ministries.
    """
    g = pd.read_csv(SEC / "02C_GRAI_Raw_2026_Panel.csv")
    g = g[(g.Group == "A") & g.Avg_Res_Days.notna() & g.QA_Flag.fillna("").eq("")]
    m1 = float(g["Avg_Res_Days"].quantile(0.25))
    W = float(c.loc[c.Month.str.startswith("2026"), "Little_W_days"].mean())
    S_target = 0.32  # share of open Central stock older than 21 days, Oct 2026

    def f(q_m2):
        q, m2 = q_m2
        Wm = (1 - q) * m1 + q * m2
        S = ((1 - q) * m1 * math.exp(-21 / m1) + q * m2 * math.exp(-21 / m2)) / Wm
        return [Wm - W, S - S_target]

    q, m2 = optimize.fsolve(f, [0.2, 30.0])
    # share of COMPLETED cases that took more than 21 days
    breach_completed = (1 - q) * math.exp(-21 / m1) + q * math.exp(-21 / m2)
    single_exp_stock = math.exp(-21 / W)
    # squared coefficient of variation of the mixture
    ET = (1 - q) * m1 + q * m2
    ET2 = 2 * ((1 - q) * m1 ** 2 + q * m2 ** 2)
    cs2 = ET2 / ET ** 2 - 1
    # 95th percentile of completion time
    p95 = optimize.brentq(lambda t: (1 - q) * math.exp(-t / m1) + q * math.exp(-t / m2) - 0.05, 0, 2000)
    M["tail"] = {
        "m1_routine_days": r(m1, 1), "W_2026": r(W), "stock_gt21_target": S_target,
        "q_complex_share": r(q, 3), "m2_complex_days": r(m2, 1),
        "completed_gt21_share": r(breach_completed * 100, 1),
        "single_exponential_stock_gt21": r(single_exp_stock * 100, 1),
        "Cs2": r(cs2, 2), "p95_days": r(p95, 1),
    }
    curve = pd.DataFrame({"days": np.arange(0, 121)})
    curve["survival_mixture"] = (1 - q) * np.exp(-curve.days / m1) + q * np.exp(-curve.days / m2)
    curve["survival_single_exp"] = np.exp(-curve.days / W)
    save(curve, "A3_completion_time_survival")


# =============================================================================
# A4  35-department ageing audit
# =============================================================================
def a4_departments():
    d = pd.read_csv(SEC / "04E_Repaired_35Dept_Dashboard.csv")
    d["Total_Pending"] = d[["Pending_0_60d", "Pending_60_180d", "Pending_180_365d"]].sum(axis=1)
    d["Pending_ge60"] = d["Pending_60_180d"] + d["Pending_180_365d"]
    d["Share_ge60"] = d["Pending_ge60"] / d["Total_Pending"]
    d["Clearance"] = d["Disposals_2026"] / d["Receipts_2026"]
    d["Cohort_check"] = d["Total_Pending"] - (d["Receipts_2026"] - d["Disposals_2026"])
    d = d.sort_values("Pending_ge60", ascending=False).reset_index(drop=True)
    d["Cum_share_of_aged"] = d["Pending_ge60"].cumsum() / d["Pending_ge60"].sum()
    save(d, "A4_35dept_ageing_pareto")
    sp = {}
    for col in ("Receipts_2026", "Total_Pending", "Clearance"):
        rho, p = stats.spearmanr(d[col], d["Share_ge60"])
        sp[col] = {"rho": r(rho, 4), "p": r(p, 4)}
    top10 = d.head(10)
    M["dept35"] = {
        "receipts": int(d.Receipts_2026.sum()), "disposals": int(d.Disposals_2026.sum()),
        "pending": int(d.Total_Pending.sum()), "aged_ge60": int(d.Pending_ge60.sum()),
        "aged_share": r(d.Pending_ge60.sum() / d.Total_Pending.sum() * 100),
        "top10_aged": int(top10.Pending_ge60.sum()),
        "top10_share": r(top10.Pending_ge60.sum() / d.Pending_ge60.sum() * 100),
        "top3_aged": int(d.head(3).Pending_ge60.sum()),
        "max_cohort_residual": int(d.Cohort_check.abs().max()),
        "spearman": sp,
        "pareto_80_count": int((d["Cum_share_of_aged"] < 0.80).sum() + 1),
    }


# =============================================================================
# A5  GRAI ministry-month panel regressions (H1 and H2)
# =============================================================================
def a5_panel():
    g = pd.read_csv(SEC / "02C_GRAI_Raw_2026_Panel.csv")
    clean = g[(g.Group == "A")
              & g.Month.isin(["2026-03", "2026-04", "2026-05", "2026-07", "2026-08", "2026-10"])
              & ~g.QA_Flag.fillna("").str.contains("truncated|QUARANTINE", case=False)].copy()
    clean = clean.dropna(subset=["BF", "Receipts", "ATR_Lt21d", "Mapped_GROs", "Active_GROs_gt5", "App_Rec"])
    clean = clean[clean.Active_GROs_gt5 > 0]
    counts = clean.Ministry_Department.value_counts()
    clean = clean[clean.Ministry_Department.isin(counts[counts >= 2].index)].copy()
    clean["exposure"] = clean.BF + clean.Receipts
    clean["atr_share"] = clean.ATR_Lt21d / clean.exposure
    clean["res_share"] = clean.Res_Lt21d / clean.exposure
    clean["log_load_active"] = np.log1p(clean.Receipts / clean.Active_GROs_gt5)
    clean["bf_ratio"] = clean.BF / clean.Receipts
    clean["bf_ratio_sq"] = clean.bf_ratio ** 2
    clean["active_ratio"] = clean.Active_GROs_gt5 / clean.Mapped_GROs
    clean["appeal_ratio"] = clean.App_Rec / clean.Receipts
    clean["ministry"] = clean.Ministry_Department
    save(clean, "A5_grai_panel_clean")

    rhs = "log_load_active + bf_ratio + bf_ratio_sq + active_ratio + appeal_ratio"
    res = {}

    def fit(formula, data):
        return smf.wls(formula, data=data, weights=data.exposure).fit(
            cov_type="cluster", cov_kwds={"groups": pd.factorize(data.ministry)[0]})

    pooled = fit(f"atr_share ~ {rhs} + C(Month)", clean)
    twfe = fit(f"atr_share ~ {rhs} + C(Month) + C(ministry)", clean)
    t_data = clean.dropna(subset=["Avg_Res_Days"])
    tcount = t_data.ministry.value_counts()
    t_data = t_data[t_data.ministry.isin(tcount[tcount >= 2].index)]
    time_pooled = fit("Avg_Res_Days ~ log_load_active + bf_ratio + bf_ratio_sq + active_ratio + C(Month)", t_data)
    time_twfe = fit("Avg_Res_Days ~ log_load_active + bf_ratio + bf_ratio_sq + active_ratio + C(Month) + C(ministry)", t_data)

    rows = []
    for name, f in [("ATR share pooled", pooled), ("ATR share TWFE", twfe),
                    ("Avg days pooled", time_pooled), ("Avg days TWFE", time_twfe)]:
        for v in ["log_load_active", "bf_ratio", "bf_ratio_sq", "active_ratio", "appeal_ratio"]:
            if v in f.params:
                rows.append({"model": name, "term": v, "coef": f.params[v], "se": f.bse[v], "p": f.pvalues[v]})
        rows.append({"model": name, "term": "N", "coef": f.nobs, "se": None, "p": None})
        rows.append({"model": name, "term": "R2", "coef": f.rsquared, "se": None, "p": None})
        rows.append({"model": name, "term": "adj_R2", "coef": f.rsquared_adj, "se": None, "p": None})
        res[name] = f
    save(pd.DataFrame(rows), "A5_panel_regressions")

    # quadratic turning point of backlog ratio in time model (SM 8.6 logic)
    b1, b2 = time_twfe.params["bf_ratio"], time_twfe.params["bf_ratio_sq"]
    turn = -b1 / (2 * b2) if b2 != 0 else None
    M["panel"] = {
        "N_atr": int(twfe.nobs), "M_atr": int(clean.ministry.nunique()),
        "N_time": int(time_twfe.nobs), "M_time": int(t_data.ministry.nunique()),
        "R2_pooled": r(pooled.rsquared, 4), "R2_twfe": r(twfe.rsquared, 4),
        "adjR2_pooled": r(pooled.rsquared_adj, 4), "adjR2_twfe": r(twfe.rsquared_adj, 4),
        "R2_gain_pp": r((twfe.rsquared - pooled.rsquared) * 100, 2),
        "R2_time_pooled": r(time_pooled.rsquared, 4), "R2_time_twfe": r(time_twfe.rsquared, 4),
        "atr_twfe": {k: {"b": r(twfe.params[k], 4), "p": r(twfe.pvalues[k], 4)}
                     for k in ["log_load_active", "bf_ratio", "bf_ratio_sq", "active_ratio", "appeal_ratio"]},
        "atr_pooled": {k: {"b": r(pooled.params[k], 4), "p": r(pooled.pvalues[k], 4)}
                       for k in ["log_load_active", "bf_ratio", "bf_ratio_sq", "active_ratio", "appeal_ratio"]},
        "time_twfe": {k: {"b": r(time_twfe.params[k], 3), "p": r(time_twfe.pvalues[k], 4)}
                      for k in ["log_load_active", "bf_ratio", "bf_ratio_sq", "active_ratio"]},
        "bf_turning_point": r(turn, 2),
        "bf_ratio_median": r(clean.bf_ratio.median(), 2),
        "bf_ratio_p90": r(clean.bf_ratio.quantile(0.9), 2),
        "load_median": r((clean.Receipts / clean.Active_GROs_gt5).median(), 1),
        "load_p90": r((clean.Receipts / clean.Active_GROs_gt5).quantile(0.9), 1),
    }
    return clean


# =============================================================================
# A6  ATR gap and active GRO ratio
# =============================================================================
def a6_atr(clean: pd.DataFrame):
    aug = clean[clean.Month == "2026-08"].copy()
    aug["res21_pct"] = aug.Res_Lt21d / aug.exposure * 100
    aug["atr21_pct"] = aug.ATR_Lt21d / aug.exposure * 100
    aug["gap_pp"] = aug.res21_pct - aug.atr21_pct
    aug["active_pct"] = aug.Active_GROs_gt5 / aug.Mapped_GROs * 100
    aug = aug.sort_values("gap_pp", ascending=False)
    save(aug[["Ministry_Department", "Receipts", "res21_pct", "atr21_pct", "gap_pp",
              "Mapped_GROs", "Active_GROs_gt5", "active_pct", "Avg_Res_Days"]], "A6_aug2026_atr_gap")
    allp = clean.copy()
    allp["gap_pp"] = (allp.Res_Lt21d - allp.ATR_Lt21d) / allp.exposure * 100
    w_res = clean.Res_Lt21d.sum() / clean.exposure.sum() * 100
    w_atr = clean.ATR_Lt21d.sum() / clean.exposure.sum() * 100
    M["atr"] = {
        "panel_res21_pct": r(w_res, 1), "panel_atr21_pct": r(w_atr, 1),
        "panel_gap_pp": r(w_res - w_atr, 1),
        "aug_max_gap_ministry": aug.iloc[0].Ministry_Department,
        "aug_max_gap_pp": r(aug.iloc[0].gap_pp, 1),
        "aug_min_active_ministry": aug.sort_values("active_pct").iloc[0].Ministry_Department,
        "aug_min_active_pct": r(aug.active_pct.min(), 1),
        "panel_active_ratio_median": r((clean.Active_GROs_gt5 / clean.Mapped_GROs).median() * 100, 1),
        "rows_gap_gt30": int((allp.gap_pp > 30).sum()), "rows_total": int(len(allp)),
    }


# =============================================================================
# A7  Feedback funnel and survey bounds (H5)
# =============================================================================
def a7_feedback(c: pd.DataFrame):
    f = pd.read_csv(SEC / "04B_Feedback_Funnels_2025_26.csv")
    f["Resolution_pct"] = f.Marked_Resolved / f.Total_Feedback * 100
    f["CondSat_pct"] = f.Satisfied / f.Marked_Resolved * 100
    f["UncondSat_pct"] = f.Satisfied / f.Total_Feedback * 100
    save(f, "A7_feedback_funnel")
    cen = f[f.Scope == "Central"]
    c25 = cen[cen.Month.between("2025-01", "2025-09")]
    c26 = cen[cen.Month.str.startswith("2026")]

    def agg(x):
        T, R, S = x.Total_Feedback.sum(), x.Marked_Resolved.sum(), x.Satisfied.sum()
        return T, R, S
    T25, R25, S25 = agg(c25)
    T26, R26, S26 = agg(c26)
    disp26 = int(c.loc[c.Month.str.startswith("2026"), "Disposals"].sum())
    # survey bounds (SM repository 4.5): known resolved over all disposals, up to
    # known resolved plus every non respondent
    lb = R26 / disp26
    ub = (R26 + (disp26 - T26)) / disp26
    st = f[f.Scope == "States/UTs"]
    M["feedback"] = {
        "c25_total": int(T25), "c25_res_pct": r(R25 / T25 * 100), "c25_cond_sat": r(S25 / R25 * 100),
        "c25_uncond_sat": r(S25 / T25 * 100),
        "c26_total": int(T26), "c26_resolved": int(R26), "c26_satisfied": int(S26),
        "c26_res_pct": r(R26 / T26 * 100), "c26_cond_sat": r(S26 / R26 * 100),
        "c26_uncond_sat": r(S26 / T26 * 100), "c26_inflation_pp": r((S26 / R26 - S26 / T26) * 100, 1),
        "c26_unresolved_pct": r((1 - R26 / T26) * 100, 1),
        "disposals_2026": disp26, "response_rate_2026": r(T26 / disp26 * 100, 1),
        "bounds_resolved_lower": r(lb * 100, 1), "bounds_resolved_upper": r(ub * 100, 1),
        "states_res_range": [r(st.Resolution_pct.min(), 1), r(st.Resolution_pct.max(), 1)],
        "states_uncond_range": [r(st.UncondSat_pct.min(), 1), r(st.UncondSat_pct.max(), 1)],
    }


# =============================================================================
# A8  CPENGRAMS and Parliamentary ledgers
# =============================================================================
def a8_ledgers():
    p = pd.read_csv(SEC / "04C_CPENGRAMS_2026_Snapshot.csv")
    get = lambda k: int(p.loc[p.Category_Or_Bucket == k, "Exact_Count"].iloc[0])
    rec = sum(get(k) for k in ["Online", "Call Center", "Postal", "Email"])
    pend = sum(get(k) for k in ["Up to 3 Months", "3-6 Months", "6-12 Months", "> 1 Year"])
    M["cpengrams"] = {
        "receipts": rec, "pending": pend, "pending_share": r(pend / rec * 100),
        "within_timeline": get("Resolved Within Timeline"),
        "within_timeline_pct": r(get("Resolved Within Timeline") / rec * 100),
        "avg_days": get("Average Disposal Time (Days)"), "sat_index_pct": 23.72,
        "feedbacks": get("Feedback Satisfaction Index"),
        "online_share": r(get("Online") / rec * 100, 1),
        "pending_gt3m": pend - get("Up to 3 Months"),
    }
    n = pd.read_csv(SEC / "03C_Parl_National_10Yr_Series.csv")
    n["resid"] = n.Brought_Forward + n.Receipt_During_Period - n.Total_Disposed - n.Total_Pending
    peak = n.loc[n.Total_Pending.idxmax()]
    y25 = n.loc[n.Year == "2025"].iloc[0]
    m91 = pd.read_csv(SEC / "03A_Parl_91_Ministries_2016_26.csv")
    m91["resid"] = m91.Brought_Forward + m91.Receipt - m91.Disposed - m91.Pending
    s37 = pd.read_csv(SEC / "03B_Parl_37_States_2016_26.csv")
    s37["resid"] = s37.Brought_Forward + s37.Receipt - s37.Disposed - s37.Pending
    top = m91.sort_values("Receipt", ascending=False).head(7)
    save(m91.sort_values("Receipt", ascending=False), "A8_parl_91_ministries_sorted")
    M["parl"] = {
        "receipts_10yr": int(n.Receipt_During_Period.sum()),
        "disposed_10yr": int(n.Total_Disposed.sum()),
        "peak_year": str(peak.Year), "peak_pending": int(peak.Total_Pending),
        "pending_2025": int(y25.Total_Pending),
        "drop_from_peak_pct": r((1 - y25.Total_Pending / peak.Total_Pending) * 100),
        "max_abs_resid_national": int(n.resid.abs().max()),
        "max_abs_resid_91": int(m91.resid.abs().max()),
        "max_abs_resid_37": int(s37.resid.abs().max()),
        "central_receipts_10yr": int(m91.Receipt.sum()),
        "state_receipts_10yr": int(s37.Receipt.sum()),
        "top7_receipt_share": r(top.Receipt.sum() / m91.Receipt.sum() * 100, 1),
        "top7": list(top.Ministry_Department),
    }


# =============================================================================
# A9  Queuing, pooling and variability (H3)
# =============================================================================
def erlang_c_wq(lam, mu, c):
    rho = lam / (c * mu)
    if rho >= 1:
        return float("inf")
    a = lam / mu
    s = sum(a ** k / math.factorial(k) for k in range(c))
    tail = a ** c / (math.factorial(c) * (1 - rho))
    pw = tail / (s + tail)
    return pw / (c * mu - lam)


def a9_queues():
    q = pd.read_csv(SEC / "04F_Queuing_MM1_MM2_Hypotheses.csv")
    rows = []
    for _, x in q.iterrows():
        lam, la, lb, mu = x.Total_Arrivals_Day, x.Desk_A_Arrivals, x.Desk_B_Arrivals, x.Service_Per_GRO_Day
        silo = (la / lam) * erlang_c_wq(la, mu, 1) + (lb / lam) * erlang_c_wq(lb, mu, 1)
        pool = erlang_c_wq(lam, mu, 2)
        rows.append({"lambda": lam, "desk_A": la, "desk_B": lb, "mu": mu, "rho": lam / (2 * mu),
                     "rho_desk_A": la / mu, "Wq_silo": silo, "Wq_pool": pool,
                     "reduction_pct": (1 - pool / silo) * 100})
    t = pd.DataFrame(rows)
    save(t, "A9_pooling_mm1_vs_mm2")

    # Variability extension (Kingman single desk, Sakasegawa multi desk)
    cs2 = M["tail"]["Cs2"]
    ca2 = M["central"]["CV_by_year"]["2026"] ** 2
    ES = 1.0  # one GRO day of work per case, the unit used above
    kin = []
    for rho in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]:
        for cdesk in [1, 2, 4, 8]:
            wq_mm = erlang_c_wq(rho * cdesk, 1.0, cdesk)
            wq_gg = wq_mm * (ca2 + cs2) / 2.0  # Allen-Cunneen scaling of the M/M/c wait
            kin.append({"rho": rho, "servers": cdesk, "Wq_MMc": wq_mm, "Wq_GGc": wq_gg})
    k = pd.DataFrame(kin)
    save(k, "A9_variability_pooling_grid")

    # Threshold utilisation where the G/G/1 wait plus routine handling crosses 21 days.
    # Work unit is a routine case of m1 days, so wait in days = Wq_units * m1.
    m1 = M["tail"]["m1_routine_days"]

    def total_days(rho, cdesk):
        return erlang_c_wq(rho * cdesk, 1.0, cdesk) * (ca2 + cs2) / 2.0 * m1 + m1

    thr = {}
    for cdesk in [1, 2, 4, 8]:
        thr[cdesk] = optimize.brentq(lambda x: total_days(x, cdesk) - 21, 0.01, 0.9999)
    M["queue"] = {
        "reduction_range": [r(t.reduction_pct.min(), 1), r(t.reduction_pct.max(), 1)],
        "rho90_silo": r(t.loc[t["lambda"] == 1.8, "Wq_silo"].iloc[0]),
        "rho90_pool": r(t.loc[t["lambda"] == 1.8, "Wq_pool"].iloc[0]),
        "skew_silo": r(t.loc[(t["lambda"] == 1.6) & (t.desk_A == 0.96), "Wq_silo"].iloc[0]),
        "skew_pool": r(t.loc[(t["lambda"] == 1.6) & (t.desk_A == 0.96), "Wq_pool"].iloc[0]),
        "ca2": r(ca2, 4), "cs2": cs2, "variability_factor": r((ca2 + cs2) / 2, 2),
        "rho_threshold_by_desks": {str(k2): r(v, 3) for k2, v in thr.items()},
        "pooled4_capacity_saving_pct": r((1 - thr[1] / thr[4]) * 100, 1),
        "mm1_wq_rho": {str(x): r(x / (1 - x), 2) for x in [0.7, 0.85, 0.95]},
    }


# =============================================================================
# B  Primary citizen research
# =============================================================================
def b_primary():
    p = pd.read_csv(PRI / "Raw_Case_Matrix.csv")
    s = pd.read_csv(PRI / "CSAT_Survey_Matrix.csv")
    direct = p[p.Cohort_Flag == 1]
    ind = p[p.Research_Stream == "Individual_Submission"]
    vet = p[p.Research_Stream == "Veteran_Portfolio"]
    dsla = direct[direct.SLA_Known == 1]
    isla = ind[ind.SLA_Known == 1]
    closed = ind[ind.Strictly_Closed_Portal == 1]
    dated_ind = ind.dropna(subset=["CPGRAMS_Days"])
    dated_dir = direct.dropna(subset=["CPGRAMS_Days"])
    e2e = ind.dropna(subset=["End_to_End_Days"])
    exact = p[p.Reassignment_Exact_Known == 1]
    zero = exact[exact.Reassignments == 0]
    multi = direct[direct.Reassignments >= 1]
    nominal = p[p.Nominal_SLA_21d_Met == 1]

    k = {}
    def add(kid, name, domain, num, den, value, unit, target, scope):
        k[kid] = dict(name=name, domain=domain, num=num, den=den, value=value, unit=unit,
                      target=target, scope=scope)

    add("KPI-01", "Substantive resolution rate, direct cohort", "Service effectiveness",
        int(direct.Real_World_Resolved.sum()), len(direct), direct.Real_World_Resolved.mean() * 100, "%", ">= 85%", "n = 24")
    add("KPI-02", "Substantive resolution rate, individual cases", "Service effectiveness",
        int(ind.Real_World_Resolved.sum()), len(ind), ind.Real_World_Resolved.mean() * 100, "%", ">= 85%", "n = 12")
    add("KPI-03", "Nominal 21 day compliance, individual", "Queue speed",
        int(isla.Nominal_SLA_21d_Met.sum()), len(isla), isla.Nominal_SLA_21d_Met.mean() * 100, "%", ">= 90%", "n = 11")
    add("KPI-04", "Substantive 21 day compliance, individual", "Value based SLA",
        int(isla.Substantive_SLA_21d_Met.sum()), len(isla), isla.Substantive_SLA_21d_Met.mean() * 100, "%", ">= 85%", "n = 11")
    add("KPI-05", "Nominal 21 day compliance, direct cohort", "Queue speed",
        int(dsla.Nominal_SLA_21d_Met.sum()), len(dsla), dsla.Nominal_SLA_21d_Met.mean() * 100, "%", ">= 90%", "n = 23")
    add("KPI-06", "Substantive 21 day compliance, direct cohort", "Value based SLA",
        int(dsla.Substantive_SLA_21d_Met.sum()), len(dsla), dsla.Substantive_SLA_21d_Met.mean() * 100, "%", ">= 85%", "n = 23")
    add("KPI-07", "Hollow closure share among closures within 21 days", "Watermelon index",
        int((nominal.Substantive_SLA_21d_Met == 0).sum()), len(nominal),
        (nominal.Substantive_SLA_21d_Met == 0).mean() * 100, "%", "<= 5%", "n = 5")
    add("KPI-08", "21 day breach rate, direct cohort", "SLA non compliance",
        int(dsla.SLA_Breach.sum()), len(dsla), dsla.SLA_Breach.mean() * 100, "%", "<= 10%", "n = 23")
    add("KPI-09", "Overall hollow closure rate, direct cohort", "False closure",
        int(direct.Hollow_Closure.sum()), len(direct), direct.Hollow_Closure.mean() * 100, "%", "<= 5%", "n = 24")
    add("KPI-10", "Mean time to disposal, strictly closed", "Portal cycle time",
        int(closed.CPGRAMS_Days.sum()), len(closed), closed.CPGRAMS_Days.mean(), "days", "<= 21", "n = 7")
    add("KPI-11", "Mean portal duration, all dated direct", "Portal cycle time",
        int(dated_dir.CPGRAMS_Days.sum()), len(dated_dir), dated_dir.CPGRAMS_Days.mean(), "days", "<= 21", "n = 11")
    add("KPI-12", "Mean end to end citizen journey", "Journey cycle time",
        int(e2e.End_to_End_Days.sum()), len(e2e), e2e.End_to_End_Days.mean(), "days", "<= 30", "n = 11")
    add("KPI-13", "Mean reassignments, exact known", "Hand off friction",
        int(exact.Reassignments.sum()), len(exact), exact.Reassignments.mean(), "hops", "<= 1", "n = 9")
    add("KPI-14", "Resolution rate with zero reassignment", "Single owner effectiveness",
        int(zero.Real_World_Resolved.sum()), len(zero), zero.Real_World_Resolved.mean() * 100, "%", ">= 85%", "n = 4")
    add("KPI-15", "Resolution rate with one or more reassignment", "Escalation collapse",
        int(multi.Real_World_Resolved.sum()), len(multi), multi.Real_World_Resolved.mean() * 100, "%", ">= 75%", "n = 18")
    add("KPI-16", "External channel use", "Failure demand",
        int(direct.Used_External_Channel.sum()), len(direct), direct.Used_External_Channel.mean() * 100, "%", "<= 10%", "n = 24")
    add("KPI-17", "Mean outcome fairness score", "Perceived justice",
        float(s.Outcome_Fairness_1_5.sum()), len(s), s.Outcome_Fairness_1_5.mean(), "of 5", ">= 4", "n = 3")
    add("KPI-18", "Digital confidence erosion", "Trust",
        int((s.Digital_Confidence_Shift == "Decreased").sum()), len(s),
        (s.Digital_Confidence_Shift == "Decreased").mean() * 100, "%", "<= 10%", "n = 3")
    kt = pd.DataFrame([{"KPI_ID": kk, **vv} for kk, vv in k.items()])
    kt["value"] = kt["value"].round(1)
    save(kt, "B1_primary_18_kpis")

    # extra descriptive stats
    appeals_known = direct.dropna(subset=["Appeals"])
    M["primary"] = {
        "units": len(p), "direct": len(direct), "individual": len(ind), "veteran": len(vet),
        "kpi": {kk: r(vv["value"], 1) for kk, vv in k.items()},
        "kpi_frac": {kk: f"{vv['num']:g} of {vv['den']}" for kk, vv in k.items()},
        "closed_days": sorted(closed.CPGRAMS_Days.astype(int).tolist()),
        "closed_median": r(closed.CPGRAMS_Days.median(), 1),
        "dated_dir_median": r(dated_dir.CPGRAMS_Days.median(), 1),
        "e2e_median": r(e2e.End_to_End_Days.median(), 1), "e2e_max": int(e2e.End_to_End_Days.max()),
        "dated_ind_mean": r(dated_ind.CPGRAMS_Days.mean(), 1),
        "dated_ind_median": r(dated_ind.CPGRAMS_Days.median(), 1),
        "hops_direct_mean": r(direct.Reassignments.mean(), 2),
        "appeal_rate": r(appeals_known.Appeals.sum() / len(appeals_known) * 100, 1),
        "appeals": int(appeals_known.Appeals.sum()), "appeals_den": len(appeals_known),
        "nonresolution_direct": r((1 - direct.Real_World_Resolved.mean()) * 100, 1),
    }

    # B2 department roll up
    dep = direct.groupby("Dept_Code").agg(
        cases=("Case_ID", "count"), resolved=("Real_World_Resolved", "sum"),
        breaches=("SLA_Breach", "sum"), hollow=("Hollow_Closure", "sum"),
        avg_days=("CPGRAMS_Days", "mean"), avg_hops=("Reassignments", "mean")).reset_index()
    dep["resolution_rate"] = dep.resolved / dep.cases * 100
    save(dep.sort_values("cases", ascending=False), "B2_primary_department_rollup")

    # failure Pareto across the 12 individual cases
    fcols = {"Hollow_Closure": "Closed without fixing the problem", "SLA_Breach": "Breach of 21 days",
             "Copy_Paste_Template": "Copy and paste template reply",
             "Suggestion_Reclassified": "Complaint relabelled as suggestion",
             "Premature_1d_Closure": "Closed within one day", "Missing_Attachment": "Missing proof or attachment",
             "Central_State_Loop": "Centre to State referral loop", "Interstate_Misrouting": "Routed to wrong State",
             "Multi_Hop_PingPong": "Bounced across many desks", "Bribery_Unpunished": "Bribe demand left unpunished"}
    fm = pd.DataFrame([{"failure": v, "code": c_, "count": int(ind[c_].fillna(0).sum())} for c_, v in fcols.items()])
    fm = fm.sort_values("count", ascending=False).reset_index(drop=True)
    fm["share_of_cases_pct"] = fm["count"] / len(ind) * 100
    fm["cum_share_of_events_pct"] = fm["count"].cumsum() / fm["count"].sum() * 100
    save(fm, "B2_failure_mode_pareto")

    # Pareto over the whole direct cohort, which is what the report quotes
    fm_d = pd.DataFrame([{"failure": v, "code": c_, "count": int(direct[c_].fillna(0).sum())} for c_, v in fcols.items()])
    fm_d = fm_d.sort_values("count", ascending=False).reset_index(drop=True)
    fm_d["cum_share_pct"] = fm_d["count"].cumsum() / fm_d["count"].sum() * 100
    save(fm_d, "B2_failure_mode_pareto_direct")
    M["primary"]["pareto_direct"] = {row.failure: int(row["count"]) for _, row in fm_d.iterrows()}
    M["primary"]["pareto_top3_share"] = r(fm_d["cum_share_pct"].iloc[2], 1)

    # B3 channels over the 13 records (12 individual cases plus one portfolio record)
    ch = {"Ch_CivicForum": "Public civic forums", "Ch_X_Twitter": "X (Twitter)",
          "Ch_DeptPortal_Phone": "Department portal or phone", "Ch_RTI": "RTI application",
          "Ch_PhysicalLetters": "Letters to Ministers or PMO", "Ch_StateIGRS": "State IGRS portal",
          "Ch_LegalNotice": "Legal notice", "Ch_Reminder": "Formal reminder"}
    rec13 = pd.concat([ind, vet.head(1)])
    cht = pd.DataFrame([{"channel": v, "records": int(rec13[c_].sum()),
                         "share_pct": rec13[c_].mean() * 100} for c_, v in ch.items()])
    save(cht.sort_values("records", ascending=False), "B3_external_channels")

    # Expectation versus standard versus delivery (Gap 2 and Gap 3 in days)
    exp_days = s.Max_Acceptable_Days_Ordinary
    M["expectation"] = {
        "max_acceptable_days": [r(v, 0) for v in exp_days], "mean_acceptable": r(exp_days.mean(), 1),
        "median_acceptable": r(exp_days.median(), 1), "standard": 21,
        "standards_gap_days": r(21 - exp_days.median(), 1),
        "delivery_gap_days_mean_dated": r(dated_dir.CPGRAMS_Days.mean() - 21, 1),
        "first_substantive_reply_mean": r(s.First_Substantive_Reply_Days.mean(), 1),
        "ratings_mean": {cname: r(s[cname].mean(), 2) for cname in
                         ["Intuitiveness_1_5", "Final_ATR_Clarity_1_5", "Outcome_Fairness_1_5",
                          "Timeliness_Satisfaction_1_5"]},
        "interim_reply_rate": r(s.Informative_Interim_Reply.mean() * 100, 1),
    }

    # B4 Fisher exact test, reassignment and resolution (direct cohort with known hops)
    known = direct.dropna(subset=["Reassignments"])
    a = int(((known.Reassignments == 0) & (known.Real_World_Resolved == 1)).sum())
    b = int(((known.Reassignments == 0) & (known.Real_World_Resolved == 0)).sum())
    c_ = int(((known.Reassignments >= 1) & (known.Real_World_Resolved == 1)).sum())
    d = int(((known.Reassignments >= 1) & (known.Real_World_Resolved == 0)).sum())
    odds, pval = stats.fisher_exact([[a, b], [c_, d]], alternative="greater")
    M["fisher"] = {"table": [[a, b], [c_, d]], "p_one_sided": r(pval, 4)}

    # Survey style bounds for the citizen sample (self selection, SM 4.5)
    return p, s


# =============================================================================
# C  Triangulation
# =============================================================================
def c_triangulate():
    tri = pd.DataFrame([
        # dept, primary code, 35 dept dashboard name
        ("Ministry of Railways", "RL", "Railways (Railway Board)"),
        ("Labour and Employment (EPFO)", "EP", "Labour and Employment"),
        ("Department of Posts", "PS", "Posts"),
        ("Personnel and Training", "PT", "Personnel and Training"),
        ("Petroleum and Natural Gas", "PG", None),
        ("Housing and Urban Affairs", "UD", None),
    ], columns=["Department", "code", "dash"])
    d35 = pd.read_csv(TAB / "A4_35dept_ageing_pareto.csv").set_index("Department")
    dep = pd.read_csv(TAB / "B2_primary_department_rollup.csv").set_index("Dept_Code")
    rows = []
    for _, x in tri.iterrows():
        dr = d35.loc[x.dash] if x.dash in d35.index else None
        pr = dep.loc[x.code]
        rows.append({
            "Department": x.Department,
            "Govt_clearance_pct": None if dr is None else round(dr.Clearance * 100, 2),
            "Govt_share_ge60_pct": None if dr is None else round(dr.Share_ge60 * 100, 2),
            "Citizen_cases": int(pr.cases), "Citizen_resolved": int(pr.resolved),
            "Citizen_hollow": int(pr.hollow), "Citizen_breaches": int(pr.breaches)})
    t = pd.DataFrame(rows)
    save(t, "C_triangulation_departments")

    gov = {
        "Mean time (Little's Law, 2026)": f"{M['central']['W_by_year']['2026']} days",
        "Clearance, Jan 2024 to Oct 2026": f"{M['central']['clearance_total']}%",
        "Open stock within 21 days, Oct 2026": "about 68%",
        "Conditional satisfaction 2026": f"{M['feedback']['c26_cond_sat']}%",
    }
    cit = {
        "Substantive resolution": f"{M['primary']['kpi']['KPI-01']}%",
        "Breach of 21 days": f"{M['primary']['kpi']['KPI-08']}%",
        "Hollow closures": f"{M['primary']['kpi']['KPI-09']}%",
        "Outcome fairness": f"{M['primary']['kpi']['KPI-17']} of 5",
    }
    M["contrast"] = {"government": gov, "citizen": cit,
                     "bridge_confirmed_resolved_2026": M["feedback"]["c26_res_pct"],
                     "bridge_uncond_sat_2026": M["feedback"]["c26_uncond_sat"],
                     "bridge_cpengrams_sat": M["cpengrams"]["sat_index_pct"],
                     "bridge_atr_gap_pp": M["atr"]["panel_gap_pp"]}


def main():
    TAB.mkdir(parents=True, exist_ok=True)
    c = a1_central()
    a2_its(c)
    a3_tail(c)
    a4_departments()
    clean = a5_panel()
    a6_atr(clean)
    a7_feedback(c)
    a8_ledgers()
    a9_queues()
    b_primary()
    c_triangulate()
    (OUT / "metrics.json").write_text(json.dumps(M, indent=2, default=str))
    print(json.dumps(M, indent=1, default=str))


if __name__ == "__main__":
    main()
