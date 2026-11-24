"""
Step 3. Draw every exhibit used in the report and the deck.

Reads   outputs/metrics.json and outputs/tables/*.csv
Writes  outputs/figures/*.png

Run from the repository root
    python code/03_figures.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
M = json.loads((ROOT / "outputs" / "metrics.json").read_text())

# ---- palette (validated reference categorical order) and ink -----------------
BLUE, ORANGE, AQUA, YELLOW, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6", "#e34948"
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
GOV, CIT = BLUE, ORANGE

for f in font_manager.findSystemFonts():
    if "Inter" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": "Inter", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 10.5, "axes.titlelocation": "left",
    "figure.facecolor": "white", "axes.facecolor": "white", "legend.frameon": False,
    "savefig.dpi": 220, "axes.axisbelow": True, "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)


def note(ax, text, y=-0.18):
    ax.text(0, y, text, transform=ax.transAxes, fontsize=7.2, color=MUTED, va="top")


# =============================================================================
def f01_contrast():
    """Resolution funnel. What is counted as closed versus what citizens confirm."""
    fb, pr = M["feedback"], M["primary"]["kpi"]
    labels = ["Disposed on portal\n(DARPG count)", "Confirmed resolved\n(DARPG call centre)",
              "Resolved and satisfied\n(DARPG call centre)", "Substantively resolved\n(our citizen cohort)"]
    vals = [100.0, fb["c26_res_pct"], fb["c26_uncond_sat"], pr["KPI-01"]]
    cols = [GOV, GOV, GOV, CIT]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    y = np.arange(len(vals))[::-1]
    ax.barh(y, vals, color=cols, height=0.62)
    for yi, v in zip(y, vals):
        ax.text(v + 1.2, yi, f"{v:.1f}%", va="center", fontsize=9, fontweight="bold", color=INK)
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 112)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="y", visible=False)
    ax.set_title("The same grievances, four different success rates (2026)")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=GOV), plt.Rectangle((0, 0), 1, 1, color=CIT)],
              labels=["Government data (secondary)", "Citizen data (primary)"], loc="lower right", fontsize=8)
    note(ax, "Sources. DARPG Feedback Call Centre, Jan to Oct 2026 (n = 699,593). Group 5 citizen cohort (n = 24).", -0.14)
    save(fig, "F01_resolution_funnel")


def f02_central_flows():
    c = pd.read_csv(TAB / "A1_central_monthly_derived.csv")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.1), gridspec_kw={"width_ratios": [1.5, 1]})
    ax = axes[0]
    x = np.arange(len(c))
    ax.plot(x, c.Receipts / 1000, color=BLUE, lw=2, label="Receipts")
    ax.plot(x, c.Disposals / 1000, color=ORANGE, lw=2, label="Disposals")
    ax.set_ylim(0, 520)
    ax.annotate("Mar 2024 Assam surge\n476k receipts", xy=(2, 476.5), xytext=(6, 430),
                fontsize=7, color=INK2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7))
    ax.set_xticks(x[::3], c.Month[::3], rotation=45, fontsize=7)
    ax.set_ylabel("Thousand grievances per month")
    ax.set_title("Central Ministries. Monthly receipts and disposals")
    ax.legend(loc="lower right", fontsize=8)
    ax = axes[1]
    ax.fill_between(x, c.Closing_Pending / 1000, color=BLUE, alpha=0.18, lw=0)
    ax.plot(x, c.Closing_Pending / 1000, color=BLUE, lw=2)
    ax.set_xticks(x[::6], c.Month[::6], rotation=45, fontsize=7)
    ax.set_ylim(0, 120)
    ax.set_title("Closing pendency (thousand)")
    ax.annotate(f"{M['central']['pending_aug2026']:,}", xy=(31, 93.9), xytext=(20, 106), fontsize=7.5,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7))
    note(axes[0], "Source. DARPG monthly reports for Central Ministries, Jan 2024 to Oct 2026 (34 months).", -0.32)
    fig.tight_layout()
    save(fig, "F02_central_flows")


def f03_mean_vs_tail():
    c = pd.read_csv(TAB / "A1_central_monthly_derived.csv")
    its = pd.read_csv(TAB / "A2_interrupted_time_series_W.csv").set_index("term").coef
    x = np.arange(len(c))
    post = (c.Month >= "2024-09").astype(int)
    rev = (c.Month >= "2025-03").astype(int)
    fit = its.Intercept + its.t * x + its.post21 * post + its.t_post21 * x * post + its.postRev * rev
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.0))
    ax = axes[0]
    mask = c.Month != "2024-03"
    ax.plot(x[mask], c.Little_W_days[mask], "o", color=BLUE, ms=4, label="Monthly W = L / daily disposals")
    ax.plot(x[mask], fit[mask], color=INK2, lw=1.4, ls="--", label="Interrupted time series fit")
    ax.axvline(7.5, color=RED, lw=1)
    ax.text(8.0, 2.0, "21 day rule\n23 Aug 2024", fontsize=7, color=RED)
    ax.axhline(21, color=MUTED, lw=0.8, ls=":")
    ax.set_ylim(0, 30)
    ax.set_xticks(x[::4], c.Month[::4], rotation=45, fontsize=7)
    ax.set_ylabel("Days")
    ax.set_title("Mean time in system keeps falling")
    ax.legend(fontsize=7, loc="upper right", ncol=1)
    ax = axes[1]
    months = ["Apr 25", "Sep 25", "Nov 25", "Dec 25", "Jul 26", "Aug 26", "Sep 26", "Oct 26"]
    gt21 = [37.75, 34.91, 35, 32, 31, 31, 32, 32]
    ax.bar(months, gt21, color=RED, width=0.6)
    for i, v in enumerate(gt21):
        ax.text(i, v + 0.8, f"{v:.0f}%", ha="center", fontsize=7.5)
    ax.set_ylim(0, 45)
    ax.tick_params(axis="x", labelsize=7, rotation=45)
    ax.set_title("Yet one third of open stock is older than 21 days")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    note(axes[0], "Source. DARPG monthly reports. March 2024 omitted from the plot (W = 6.9 days, receipt spike).", -0.34)
    fig.tight_layout()
    save(fig, "F03_mean_vs_tail")


def f04_survival():
    s = pd.read_csv(TAB / "A3_completion_time_survival.csv")
    t = M["tail"]
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    ax.plot(s.days, s.survival_single_exp * 100, color=MUTED, lw=1.6, ls="--",
            label=f"Single class, mean {t['W_2026']} days")
    ax.plot(s.days, s.survival_mixture * 100, color=BLUE, lw=2.2,
            label=f"Two class fit. {100 - t['q_complex_share'] * 100:.1f}% routine (mean {t['m1_routine_days']:.0f} d), "
                  f"{t['q_complex_share'] * 100:.1f}% complex (mean {t['m2_complex_days']:.0f} d)")
    ax.axvline(21, color=RED, lw=1)
    ax.text(22, 82, "21 day standard", color=RED, fontsize=7.5)
    ax.plot([21], [t["completed_gt21_share"]], "o", color=RED, ms=6)
    ax.text(24, t["completed_gt21_share"] + 4, f"{t['completed_gt21_share']}% of completions\nexceed 21 days",
            fontsize=7.5, color=INK)
    ax.set_xlabel("Days since filing")
    ax.set_ylabel("Share of cases still open")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_xlim(0, 120)
    ax.set_title("Calibrated completion time curve for Central grievances, 2026")
    ax.legend(fontsize=7, loc="upper right")
    save(fig, "F04_completion_survival")


def f05_dept_pareto():
    d = pd.read_csv(TAB / "A4_35dept_ageing_pareto.csv").head(12)
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    y = np.arange(len(d))[::-1]
    cols = [RED if s > 0.15 else BLUE for s in d.Share_ge60]
    ax.barh(y, d.Pending_ge60, color=cols, height=0.65)
    for yi, (v, cum, sh) in zip(y, zip(d.Pending_ge60, d.Cum_share_of_aged, d.Share_ge60)):
        ax.text(v + 12, yi, f"{v:,}   cum {cum * 100:.0f}%   ({sh * 100:.1f}% of own stock)", va="center", fontsize=7)
    ax.set_yticks(y, d.Department, fontsize=7.5)
    ax.set_xlim(0, 1500)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Cases pending 60 days or more")
    ax.set_title("Pareto of aged backlog. 10 departments hold 90.6% of 5,018 aged cases")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=RED), plt.Rectangle((0, 0), 1, 1, color=BLUE)],
              labels=["Over 15% of own stock aged", "Under 15%"], fontsize=7, loc="lower right")
    note(ax, "Source. pgportal.gov.in DARPG dashboard extract, 1 Jan to 10 Nov 2026, 35 departments.", -0.2)
    save(fig, "F05_dept_aged_pareto")


def f06_atr_gap():
    a = pd.read_csv(TAB / "A6_aug2026_atr_gap.csv").head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    y = np.arange(len(a))
    ax.hlines(y, a.atr21_pct, a.res21_pct, color=GRID, lw=3)
    ax.plot(a.res21_pct, y, "o", color=MUTED, ms=7, label="Closed within 21 days")
    ax.plot(a.atr21_pct, y, "o", color=BLUE, ms=7, label="Closed within 21 days with an Action Taken Report")
    for yi, g in zip(y, a.gap_pp):
        ax.text(101, yi, f"{g:.0f} pp", va="center", fontsize=7, color=INK2)
    ax.set_yticks(y, a.Ministry_Department, fontsize=7.5)
    ax.set_xlim(0, 110)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_title("Closure without an ATR. August 2026 Group A ministries")
    ax.legend(fontsize=7, loc="lower left", bbox_to_anchor=(0, -0.3), ncol=2)
    note(ax, "Share of exposure (brought forward plus receipts). Source. DARPG GRAI Section 2.2 raw table, Aug 2026.", -0.36)
    save(fig, "F06_atr_gap")


def f07_regression():
    p = M["panel"]
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.0))
    ax = axes[0]
    labels = ["Load, backlog,\nactive GROs, appeals\n+ month effects", "Same model\n+ ministry effects"]
    vals = [p["R2_pooled"] * 100, p["R2_twfe"] * 100]
    ax.bar(labels, vals, color=[MUTED, BLUE], width=0.55)
    for i, v in enumerate(vals):
        ax.text(i, v + 1.5, f"R² {v / 100:.3f}", ha="center", fontsize=8.5, fontweight="bold")
    ax.set_ylim(0, 110)
    ax.set_title(f"H2. Ministry identity adds {p['R2_gain_pp']} pp of R²")
    ax.set_ylabel("Variance of ATR share explained (%)")
    ax = axes[1]
    b1, b2 = p["time_twfe"]["bf_ratio"]["b"], p["time_twfe"]["bf_ratio_sq"]["b"]
    xs = np.linspace(0, 1.4, 100)
    ax.plot(xs, b1 * xs + b2 * xs ** 2, color=BLUE, lw=2.2)
    for q, lab in [(p["bf_ratio_median"], "median"), (p["bf_ratio_p90"], "90th pct")]:
        yv = b1 * q + b2 * q ** 2
        ax.plot([q], [yv], "o", color=ORANGE, ms=6)
        ax.text(q + 0.05, yv - 3.2, f"{lab} {q}\n+{yv:.1f} days", fontsize=7)
    ax.set_xlabel("Backlog ratio, brought forward / receipts")
    ax.set_ylabel("Added average resolution days")
    ax.set_title("H1. Backlog raises resolution time at a falling rate")
    note(axes[0], f"Exposure weighted least squares, ministry clustered errors. N = {p['N_atr']}, {p['M_atr']} ministries, 2026.", -0.36)
    fig.tight_layout()
    save(fig, "F07_regression")


def f08_feedback():
    fb = M["feedback"]
    groups = ["Central\nJan to Sep 2025", "Central\nJan to Oct 2026"]
    res = [fb["c25_res_pct"], fb["c26_res_pct"]]
    cond = [fb["c25_cond_sat"], fb["c26_cond_sat"]]
    unc = [fb["c25_uncond_sat"], fb["c26_uncond_sat"]]
    x = np.arange(2)
    w = 0.25
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for i, (vals, col, lab) in enumerate([(cond, MUTED, "Headline satisfaction (satisfied / resolved)"),
                                          (res, BLUE, "Confirmed resolved (resolved / all feedback)"),
                                          (unc, ORANGE, "True satisfaction (satisfied / all feedback)")]):
        ax.bar(x + (i - 1) * w, vals, w * 0.92, color=col, label=lab)
        for xi, v in zip(x, vals):
            ax.text(xi + (i - 1) * w, v + 1.2, f"{v:.1f}", ha="center", fontsize=7.5)
    ax.set_xticks(x, groups)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_title("H5. Headline satisfaction hides the unresolved majority")
    ax.legend(fontsize=7, loc="upper right")
    save(fig, "F08_feedback_funnel")


def f09_pooling():
    k = pd.read_csv(TAB / "A9_variability_pooling_grid.csv")
    m1 = M["tail"]["m1_routine_days"]
    fig, ax = plt.subplots(figsize=(6.6, 3.1))
    for cd, col in zip([1, 2, 4, 8], [RED, ORANGE, BLUE, AQUA]):
        rho = np.linspace(0.3, 0.97, 80)
        from math import factorial
        def wq(lam, mu, c):
            a = lam / mu; r_ = lam / (c * mu)
            s = sum(a ** j / factorial(j) for j in range(c))
            t = a ** c / (factorial(c) * (1 - r_))
            return t / (s + t) / (c * mu - lam)
        days = np.array([wq(x * cd, 1, cd) * M["queue"]["variability_factor"] * m1 + m1 for x in rho])
        keep = days <= 60
        ax.plot(rho[keep] * 100, days[keep], color=col, lw=2, label=f"{cd} pooled desk{'s' if cd > 1 else ''}, crosses 21 d at "
                f"{M['queue']['rho_threshold_by_desks'][str(cd)] * 100:.0f}%")
    ax.axhline(21, color=INK2, lw=1, ls="--")
    ax.text(31, 22.5, "21 day standard", fontsize=7.5, color=INK2)
    ax.set_ylim(0, 60)
    ax.set_xlim(30, 97)
    ax.set_xlabel("GRO utilisation ρ (%)")
    ax.set_ylabel("Expected days to close (wait + work)")
    ax.set_title("H3. Pooling raises the safe utilisation ceiling")
    ax.legend(fontsize=7, loc="upper left")
    note(ax, f"G/G/c by Allen Cunneen scaling of Erlang C. Ca² = {M['queue']['ca2']}, Cs² = {M['queue']['cs2']} "
             f"(calibrated), routine work = {m1:.0f} days.", -0.2)
    save(fig, "F09_pooling_threshold")


def f10_primary_kpis():
    k = pd.read_csv(TAB / "B1_primary_18_kpis.csv")
    pct = k[k.unit == "%"].copy()
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    y = np.arange(len(pct))[::-1]
    good_high = ~pct.target.str.startswith("<=")
    cols = []
    for v, gh, t in zip(pct.value, good_high, pct.target):
        tv = float(t.split()[-1].rstrip("%"))
        ok = v >= tv if gh else v <= tv
        cols.append(AQUA if ok else RED)
    ax.barh(y, pct.value, color=cols, height=0.65)
    for yi, (v, t, fr) in zip(y, zip(pct.value, pct.target, pct.num.astype(int).astype(str) + " of " + pct.den.astype(str))):
        ax.text(v + 1.5, yi, f"{v:.1f}%  ({fr})   target {t}", va="center", fontsize=7)
    ax.set_yticks(y, pct.KPI_ID + "  " + pct.name, fontsize=7.2)
    ax.set_xlim(0, 150)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="y", visible=False)
    ax.set_title("Citizen cohort scorecard. All 14 rate KPIs miss their target")
    save(fig, "F10_primary_kpis")


def f11_timeline():
    labels = ["TG-01 drainage", "EP-01 PF advance", "PS-01 postal claim", "RD-01 road repair", "RL-01 railways",
              "RL-02 railways", "UD-01 Prayagraj road", "PP-02 pension", "RL-03 railways", "PG-01 LPG",
              "PP-01 family pension"]
    days = [1, 1, 5, 9, 13, 24, 24, 28, 33, 42, 289]
    status = ["h", "h", "r", "r", "h", "b", "b", "b", "b", "b", "b"]
    cmap = {"r": AQUA, "h": YELLOW, "b": RED}
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    y = np.arange(len(days))[::-1]
    ax.barh(y, [min(d_, 90) for d_ in days], color=[cmap[s] for s in status], height=0.65)
    for yi, v in zip(y, days):
        if v <= 90:
            ax.text(v + 1.5, yi, f"{v} d", va="center", fontsize=7.5)
    ax.set_xlim(0, 100)
    for dx in (0, 1.6):
        ax.plot([86 + dx, 88 + dx], [y[-1] - 0.42, y[-1] + 0.42], color="white", lw=2.5)
    ax.text(91.5, y[-1], "289 d", fontsize=7.5, color=INK, va="center")
    ax.axvline(21, color=INK2, lw=1, ls="--")
    ax.text(21.8, 10.4, "21 days", fontsize=7.5)
    ax.set_yticks(y, ["Case-" + l for l in labels], fontsize=7.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Calendar days on the portal (PP-01 bar broken, actual 289 days)")
    ax.set_title("Citizen cases. Days to closure or last action")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c_) for c_ in (AQUA, YELLOW, RED)],
              labels=["Resolved within 21 d", "Closed within 21 d, not fixed", "Breached 21 d, not fixed"],
              fontsize=7, loc="upper right")
    save(fig, "F11_citizen_timeline")


def f12_failure_pareto():
    f = pd.read_csv(TAB / "B2_failure_mode_pareto_direct.csv")
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    y = np.arange(len(f))[::-1]
    cols = [RED if c <= 82 else MUTED for c in f.cum_share_pct]
    ax.barh(y, f["count"], color=cols, height=0.65)
    for yi, (v, cs) in zip(y, zip(f["count"], f.cum_share_pct)):
        ax.text(v + 0.3, yi, f"{v}   cum {cs:.0f}%", va="center", fontsize=7.5)
    ax.set_yticks(y, f.failure, fontsize=7.5)
    ax.set_xlim(0, 26)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Occurrences across 24 direct grievances")
    ax.set_title(f"Mr. BIV in CPGRAMS. Three defects make {M['primary']['pareto_top3_share']}% of all failures")
    save(fig, "F12_failure_pareto")


def f13_channels():
    c = pd.read_csv(TAB / "B3_external_channels.csv")
    fig, ax = plt.subplots(figsize=(5.6, 2.8))
    y = np.arange(len(c))[::-1]
    ax.barh(y, c.share_pct, color=AQUA, height=0.62)
    for yi, (v, n) in zip(y, zip(c.share_pct, c.records)):
        ax.text(v + 1, yi, f"{v:.1f}%  ({n} of 13)", va="center", fontsize=7.5)
    ax.set_yticks(y, c.channel, fontsize=7.5)
    ax.set_xlim(0, 95)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="y", visible=False)
    ax.set_title("Failure demand. Channels citizens used beyond CPGRAMS")
    save(fig, "F13_channels")


def f14_gap_model():
    e = M["expectation"]
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    ax.axis("off")
    ax.set_xlim(0, 10.6)
    ax.set_ylim(0, 6.2)
    W, H = 3.6, 1.05
    boxes = [
        (0.1, 4.9, "Citizen expectation", f"Median acceptable time {e['median_acceptable']:.0f} days\nfor an ordinary grievance", CIT),
        (0.1, 0.3, "Citizen perception", f"Substantive resolution {M['primary']['kpi']['KPI-01']}%\nOutcome fairness {M['primary']['kpi']['KPI-17']} of 5", CIT),
        (6.3, 4.9, "Management view of need", "Speed of disposal, GRAI rank,\nclearance ratio", GOV),
        (6.3, 2.6, "Service standard", "21 days, interim reply if longer\n(Aug 2024 guidelines)", GOV),
        (6.3, 0.3, "Actual delivery", f"Mean {M['central']['W_by_year']['2026']} d in system, "
                   f"{M['tail']['completed_gt21_share']}%\nof completions take over 21 d", GOV),
    ]
    for x, y, t, s_, col in boxes:
        ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="white", ec=col, lw=1.6))
        ax.text(x + 0.15, y + 0.78, t, fontsize=8.5, fontweight="bold", color=col)
        ax.text(x + 0.15, y + 0.12, s_, fontsize=7.3, color=INK)
    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="<->", color=RED, lw=1.3))
    arrow(3.75, 5.42, 6.25, 5.42)
    ax.text(5.0, 5.62, "Gap 1 Knowledge", ha="center", fontsize=7.3, color=RED, fontweight="bold")
    ax.text(5.0, 4.95, "No citizen verified\nresolution measure", ha="center", fontsize=6.8, color=INK2)
    arrow(3.75, 0.82, 6.25, 0.82)
    ax.text(5.0, 1.02, "Gap 4 Communication", ha="center", fontsize=7.3, color=RED, fontweight="bold")
    ax.text(5.0, 0.38, f"Informative interim\nreplies {e['interim_reply_rate']:.0f}%", ha="center", fontsize=6.8, color=INK2)
    arrow(8.1, 4.85, 8.1, 3.7)
    ax.text(8.2, 4.05, f"Gap 2 Standards\n21 d set vs {e['median_acceptable']:.0f} d expected", fontsize=7, color=RED, fontweight="bold")
    arrow(8.1, 2.55, 8.1, 1.4)
    ax.text(8.2, 1.65, f"Gap 3 Delivery\n{M['atr']['panel_gap_pp']} pp closed without ATR", fontsize=7, color=RED, fontweight="bold")
    ax.annotate("", xy=(1.9, 1.45), xytext=(1.9, 4.85), arrowprops=dict(arrowstyle="<->", color=INK, lw=2))
    ax.text(2.05, 3.0, f"Customer gap\n= Gap 1 + 2 + 3 + 4\n{M['primary']['kpi']['KPI-09']}% hollow closures", fontsize=8, fontweight="bold", color=INK)
    ax.set_title("Gap model applied to CPGRAMS, every gap measured", loc="left")
    save(fig, "F14_gap_model")


def f15_national():
    n = pd.read_csv(ROOT / "data/raw/secondary/03C_Parl_National_10Yr_Series.csv").iloc[:10]
    fig, ax = plt.subplots(figsize=(6.0, 2.8))
    ax.bar(n.Year.astype(str), n.Total_Pending / 1000, color=BLUE, width=0.62)
    for i, v in enumerate(n.Total_Pending / 1000):
        ax.text(i, v + 15, f"{v:.0f}k", ha="center", fontsize=7)
    ax.set_ylim(0, 1200)
    ax.set_ylabel("Pending grievances, thousand")
    ax.set_title(f"National closing pendency fell {M['parl']['drop_from_peak_pct']}% from the 2019 peak")
    note(ax, "Source. Lok Sabha Unstarred Question 6033, Annexure III (1 Apr 2026).", -0.14)
    save(fig, "F15_national_pendency")


def f16_triangulation():
    t = pd.read_csv(TAB / "C_triangulation_departments.csv").dropna()
    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    y = np.arange(len(t))[::-1]
    ax.barh(y + 0.18, t.Govt_clearance_pct, 0.34, color=GOV, label="Govt clearance ratio 2026")
    ax.barh(y - 0.18, t.Citizen_resolved / t.Citizen_cases * 100, 0.34, color=CIT, label="Citizen cases resolved")
    for yi, (g, cr, cc) in zip(y, zip(t.Govt_clearance_pct, t.Citizen_resolved, t.Citizen_cases)):
        ax.text(g + 1, yi + 0.18, f"{g:.1f}%", va="center", fontsize=7)
        ax.text(cr / cc * 100 + 1, yi - 0.18, f"{cr} of {cc}", va="center", fontsize=7)
    ax.set_yticks(y, t.Department, fontsize=7.5)
    ax.set_xlim(0, 115)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="y", visible=False)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    ax.set_title("Same ministry, two verdicts")
    save(fig, "F16_triangulation")


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    for fn in [f01_contrast, f02_central_flows, f03_mean_vs_tail, f04_survival, f05_dept_pareto, f06_atr_gap,
               f07_regression, f08_feedback, f09_pooling, f10_primary_kpis, f11_timeline, f12_failure_pareto,
               f13_channels, f14_gap_model, f15_national, f16_triangulation]:
        fn()
        print("drew", fn.__name__)
