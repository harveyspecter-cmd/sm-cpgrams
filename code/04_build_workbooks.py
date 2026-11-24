"""
Step 4. Refresh the two Excel workbooks so that they match the analysis.

1. CPGRAMS_Primary_Research_Raw_Data_Matrix.xlsx is rebuilt from the primary CSVs
   with five styled tabs and live Excel formulas
       Raw_Case_Matrix, Service_Mgmt_KPIs (18 KPIs), Dept_Failure_Summary,
       CSAT_Survey_Matrix, Failure_Pareto
2. CPGRAMS_Complete_Dataset_2016_2026.xlsx keeps every source sheet and gets
       a refreshed hypothesis matrix written from outputs/metrics.json
       a new 05_Findings_Summary sheet with the headline numbers

Run from the repository root after 02_analysis.py
    python code/04_build_workbooks.py
"""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
WB = ROOT / "data" / "workbooks"
PRI = ROOT / "data" / "raw" / "primary"
M = json.loads((ROOT / "outputs" / "metrics.json").read_text())

NAVY, ROYAL, TEAL, SUB = "0F172A", "1E3A8A", "0F766E", "334155"
ROW_HDR, ZEBRA, TOTAL, HI = "DBEAFE", "F8FAFC", "E2E8F0", "FEF9C3"
GREEN, RED, AMBER = "DCFCE7", "FEE2E2", "FEF3C7"
thin = Side(style="thin", color="CBD5E1")
med = Side(style="medium", color=NAVY)
B_STD = Border(left=thin, right=thin, top=thin, bottom=thin)
B_HDR = Border(left=thin, right=thin, top=med, bottom=med)
fill = lambda h: PatternFill("solid", fgColor=h)


def banner(ws, title, subtitle, ncol, colour):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c = ws.cell(1, 1, title)
    c.font, c.fill = Font(size=14, bold=True, color="FFFFFF"), fill(colour)
    c.alignment = Alignment(vertical="center", indent=1)
    c = ws.cell(2, 1, subtitle)
    c.font, c.fill = Font(size=10, italic=True, color="E2E8F0"), fill(SUB)
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height, ws.row_dimensions[2].height = 28, 20


def header(ws, row, names, colour, highlight=()):
    for j, h in enumerate(names, 1):
        c = ws.cell(row, j, h)
        c.font = Font(size=10, bold=True, color="FFFFFF")
        c.fill = fill("B45309" if j in highlight else colour)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = B_HDR
    ws.row_dimensions[row].height = 32


def body(ws, r1, r2, ncol, highlight=()):
    for r in range(r1, r2 + 1):
        for j in range(1, ncol + 1):
            c = ws.cell(r, j)
            c.border = B_STD
            if j == 1:
                c.font, c.fill = Font(size=10, bold=True, color=NAVY), fill(ROW_HDR)
            else:
                c.font = Font(size=10, color="1E293B")
                if j in highlight:
                    c.fill = fill(HI)
                elif r % 2:
                    c.fill = fill(ZEBRA)
            c.alignment = Alignment(vertical="center", wrap_text=j > 1 and isinstance(c.value, str) and len(c.value) > 40)


def widths(ws, ncol, lo=10, hi=46):
    for j in range(1, ncol + 1):
        L = 0
        for r in range(3, ws.max_row + 1):
            v = ws.cell(r, j).value
            s = "100.0%" if isinstance(v, str) and v.startswith("=") else str(v or "")
            L = max(L, len(s))
        ws.column_dimensions[get_column_letter(j)].width = min(max(L + 3, lo), hi)


def build_primary():
    raw = pd.read_csv(PRI / "Raw_Case_Matrix.csv")
    csat = pd.read_csv(PRI / "CSAT_Survey_Matrix.csv")
    wb = openpyxl.Workbook()

    # ---- Tab 1 Raw_Case_Matrix, data rows 4 to 28 --------------------------
    ws = wb.active
    ws.title = "Raw_Case_Matrix"
    cols = list(raw.columns)
    banner(ws, "CPGRAMS PRIMARY CITIZEN RESEARCH. RAW CASE MATRIX",
           "25 units in rows 4 to 28. 12 individual cases, 12 veteran portfolio cases, 1 cited case (Cohort_Flag 0)",
           len(cols), NAVY)
    hl = {cols.index(k) + 1 for k in ["CPGRAMS_Days", "Nominal_SLA_21d_Met", "Substantive_SLA_21d_Met",
                                      "Real_World_Resolved", "Hollow_Closure", "SLA_Breach"]}
    header(ws, 3, cols, NAVY, hl)
    for i, row in enumerate(raw.itertuples(index=False), 4):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, None if pd.isna(v) else v)
    body(ws, 4, 3 + len(raw), len(cols), hl)
    for i in range(4, 4 + len(raw)):
        c = ws.cell(i, cols.index("Real_World_Resolved") + 1)
        c.fill = fill(GREEN if c.value == 1 else RED)
        c = ws.cell(i, cols.index("SLA_Breach") + 1)
        if c.value == 1:
            c.fill = fill(RED)
        c = ws.cell(i, cols.index("Hollow_Closure") + 1)
        if c.value == 1:
            c.fill = fill(AMBER)
    ws.freeze_panes = "B4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}{3 + len(raw)}"
    widths(ws, len(cols), hi=30)

    L = {k: get_column_letter(cols.index(k) + 1) for k in cols}
    R = lambda k: f"Raw_Case_Matrix!${L[k]}$4:${L[k]}$28"

    # ---- Tab 4 CSAT first (KPIs reference it), rows 4 to 6 -----------------
    wc = wb.create_sheet("CSAT_Survey_Matrix")
    ccols = list(csat.columns)
    banner(wc, "STRUCTURED CSAT AND CONFIDENCE MATRIX", "Three structured respondents in rows 4 to 6, live summary in row 7",
           len(ccols), NAVY)
    header(wc, 3, ccols, NAVY, {12, 13, 14, 16})
    for i, row in enumerate(csat.itertuples(index=False), 4):
        for j, v in enumerate(row, 1):
            wc.cell(i, j, None if pd.isna(v) else v)
    body(wc, 4, 6, len(ccols), {12, 13, 14, 16})
    wc.cell(7, 1, "MEAN OR RATE")
    wc.cell(7, 2, "Structured sample n = 3")
    for j in range(3, len(ccols)):
        cl = get_column_letter(j)
        wc.cell(7, j, f"=IFERROR(AVERAGE({cl}4:{cl}6),\"\")").number_format = "0.00"
    pl = get_column_letter(len(ccols))
    wc.cell(7, len(ccols), f'=COUNTIF({pl}4:{pl}6,"Decreased")/COUNTA({pl}4:{pl}6)').number_format = "0.0%"
    for j in range(1, len(ccols) + 1):
        c = wc.cell(7, j)
        c.font, c.fill, c.border = Font(bold=True), fill(TOTAL), B_HDR
    wc.freeze_panes = "B4"
    widths(wc, len(ccols))

    # ---- Tab 2 Service_Mgmt_KPIs -------------------------------------------
    wk = wb.create_sheet("Service_Mgmt_KPIs", 1)
    kh = ["KPI_ID", "Service management KPI", "Service domain", "Scope", "Numerator", "Denominator",
          "Live value", "Target", "Status", "Excel formula"]
    banner(wk, "SERVICE MANAGEMENT KPI DASHBOARD, LIVE FORMULAS", "18 KPIs linked to Raw_Case_Matrix and CSAT_Survey_Matrix",
           len(kh), ROYAL)
    header(wk, 3, kh, ROYAL, {7, 9})
    C, IND = R("Cohort_Flag"), R("Research_Stream")
    ind = '"Individual_Submission"'
    F = {
        "KPI-01": f"=SUMIFS({R('Real_World_Resolved')},{C},1)/SUM({C})",
        "KPI-02": f"=COUNTIFS({IND},{ind},{R('Real_World_Resolved')},1)/COUNTIF({IND},{ind})",
        "KPI-03": f"=COUNTIFS({IND},{ind},{R('SLA_Known')},1,{R('Nominal_SLA_21d_Met')},1)/COUNTIFS({IND},{ind},{R('SLA_Known')},1)",
        "KPI-04": f"=COUNTIFS({IND},{ind},{R('SLA_Known')},1,{R('Substantive_SLA_21d_Met')},1)/COUNTIFS({IND},{ind},{R('SLA_Known')},1)",
        "KPI-05": f"=COUNTIFS({C},1,{R('SLA_Known')},1,{R('Nominal_SLA_21d_Met')},1)/COUNTIFS({C},1,{R('SLA_Known')},1)",
        "KPI-06": f"=COUNTIFS({C},1,{R('SLA_Known')},1,{R('Substantive_SLA_21d_Met')},1)/COUNTIFS({C},1,{R('SLA_Known')},1)",
        "KPI-07": f"=COUNTIFS({R('Nominal_SLA_21d_Met')},1,{R('Substantive_SLA_21d_Met')},0)/COUNTIF({R('Nominal_SLA_21d_Met')},1)",
        "KPI-08": f"=COUNTIFS({C},1,{R('SLA_Breach')},1)/COUNTIFS({C},1,{R('SLA_Known')},1)",
        "KPI-09": f"=COUNTIFS({C},1,{R('Hollow_Closure')},1)/SUM({C})",
        "KPI-10": f"=AVERAGEIF({R('Strictly_Closed_Portal')},1,{R('CPGRAMS_Days')})",
        "KPI-11": f"=AVERAGEIF({C},1,{R('CPGRAMS_Days')})",
        "KPI-12": f"=AVERAGEIF({IND},{ind},{R('End_to_End_Days')})",
        "KPI-13": f"=AVERAGEIF({R('Reassignment_Exact_Known')},1,{R('Reassignments')})",
        "KPI-14": f"=COUNTIFS({R('Reassignment_Exact_Known')},1,{R('Reassignments')},0,{R('Real_World_Resolved')},1)/COUNTIFS({R('Reassignment_Exact_Known')},1,{R('Reassignments')},0)",
        "KPI-15": f'=COUNTIFS({C},1,{R("Reassignments")},">=1",{R("Real_World_Resolved")},1)/COUNTIFS({C},1,{R("Reassignments")},">=1")',
        "KPI-16": f"=COUNTIFS({C},1,{R('Used_External_Channel')},1)/SUM({C})",
        "KPI-17": "=AVERAGE(CSAT_Survey_Matrix!$M$4:$M$6)",
        "KPI-18": '=COUNTIF(CSAT_Survey_Matrix!$P$4:$P$6,"Decreased")/COUNTA(CSAT_Survey_Matrix!$P$4:$P$6)',
    }
    k = pd.read_csv(ROOT / "outputs" / "tables" / "B1_primary_18_kpis.csv")
    for i, x in enumerate(k.itertuples(index=False), 4):
        f = F[x.KPI_ID]
        tv = float(x.target.split()[-1].rstrip("%"))
        ok = (x.value >= tv) if x.target.startswith(">=") else (x.value <= tv)
        vals = [x.KPI_ID, x.name, x.domain, x.scope, x.num, x.den, f, x.target, "PASS" if ok else "FAIL", f.lstrip("=")]
        for j, v in enumerate(vals, 1):
            wk.cell(i, j, v)
        wk.cell(i, 7).number_format = "0.0%" if x.unit == "%" else '0.0 "' + x.unit + '"'
    body(wk, 4, 21, len(kh), {7})
    for i in range(4, 22):
        c = wk.cell(i, 9)
        c.fill = fill(GREEN if c.value == "PASS" else RED)
        c.font = Font(bold=True, color="166534" if c.value == "PASS" else "991B1B")
    wk.freeze_panes = "C4"
    widths(wk, len(kh), hi=40)
    wk.column_dimensions["J"].width = 60

    # ---- Tab 3 Dept_Failure_Summary ----------------------------------------
    wd = wb.create_sheet("Dept_Failure_Summary", 2)
    dh = ["Dept_Code", "Ministry or department", "Direct cases", "Resolved", "Resolution rate",
          "21 day breaches", "Hollow closures", "Avg portal days", "Avg hops"]
    banner(wd, "DEPARTMENT ROLL UP, LIVE FORMULAS", "12 departments in rows 4 to 15, total in row 16", len(dh), TEAL)
    header(wd, 3, dh, TEAL, {5, 6, 7})
    names = (raw[raw.Cohort_Flag == 1].groupby("Dept_Code")["Ministry_or_Dept"].first())
    order = raw[raw.Cohort_Flag == 1].Dept_Code.value_counts().index.tolist()
    E = R("Dept_Code")
    for i, dc in enumerate(order, 4):
        row = [dc, names[dc],
               f"=COUNTIFS({E},A{i},{C},1)",
               f"=COUNTIFS({E},A{i},{C},1,{R('Real_World_Resolved')},1)",
               f"=IF(C{i}>0,D{i}/C{i},0)",
               f"=COUNTIFS({E},A{i},{C},1,{R('SLA_Breach')},1)",
               f"=COUNTIFS({E},A{i},{C},1,{R('Hollow_Closure')},1)",
               f'=IFERROR(AVERAGEIFS({R("CPGRAMS_Days")},{E},A{i},{C},1),"n.a.")',
               f'=IFERROR(AVERAGEIFS({R("Reassignments")},{E},A{i},{C},1),"n.a.")']
        for j, v in enumerate(row, 1):
            wd.cell(i, j, v)
        wd.cell(i, 5).number_format = "0.0%"
        wd.cell(i, 8).number_format = wd.cell(i, 9).number_format = "0.0"
    t = 4 + len(order)
    body(wd, 4, t - 1, len(dh), {5, 6, 7})
    tot = ["TOTAL", "All direct grievances", f"=SUM(C4:C{t-1})", f"=SUM(D4:D{t-1})", f"=D{t}/C{t}",
           f"=SUM(F4:F{t-1})", f"=SUM(G4:G{t-1})", f"=AVERAGEIF({C},1,{R('CPGRAMS_Days')})",
           f"=AVERAGEIF({C},1,{R('Reassignments')})"]
    for j, v in enumerate(tot, 1):
        c = wd.cell(t, j, v)
        c.font, c.fill, c.border = Font(bold=True), fill(TOTAL), B_HDR
    wd.cell(t, 5).number_format = "0.0%"
    wd.cell(t, 8).number_format = wd.cell(t, 9).number_format = "0.0"
    wd.freeze_panes = "C4"
    widths(wd, len(dh))

    # ---- Tab 5 Failure_Pareto ----------------------------------------------
    wp = wb.create_sheet("Failure_Pareto")
    ph = ["Failure mode (Mr. BIV lens)", "Raw column", "Occurrences", "Share of events", "Cumulative share"]
    banner(wp, "PARETO OF FAILURE MODES, DIRECT COHORT", "Counts are live COUNTIFS over Raw_Case_Matrix", len(ph), TEAL)
    header(wp, 3, ph, TEAL, {3, 5})
    fp = pd.read_csv(ROOT / "outputs" / "tables" / "B2_failure_mode_pareto_direct.csv")
    n = len(fp)
    for i, x in enumerate(fp.itertuples(index=False), 4):
        wp.cell(i, 1, x.failure)
        wp.cell(i, 2, x.code)
        wp.cell(i, 3, f"=COUNTIFS({C},1,{R(x.code)},1)")
        wp.cell(i, 4, f"=C{i}/SUM($C$4:$C${3 + n})").number_format = "0.0%"
        wp.cell(i, 5, f"=SUM($C$4:C{i})/SUM($C$4:$C${3 + n})").number_format = "0.0%"
    body(wp, 4, 3 + n, len(ph), {3, 5})
    widths(wp, len(ph))

    out = WB / "CPGRAMS_Primary_Research_Raw_Data_Matrix.xlsx"
    wb.save(out)
    return out


def refresh_secondary():
    path = WB / "CPGRAMS_Complete_Dataset_2016_2026.xlsx"
    wb = openpyxl.load_workbook(path)
    ws = wb["04F_Queuing_MM1_MM2_Hypotheses"]
    p, q, fb, its = M["panel"], M["queue"], M["feedback"], M["its"]
    hyp = [
        ("H1. Delay rises non linearly with load and backlog",
         f"TWFE on N = {p['N_time']} ministry months. Backlog ratio +{p['time_twfe']['bf_ratio']['b']} days "
         f"(p = {p['time_twfe']['bf_ratio']['p']}), squared term {p['time_twfe']['bf_ratio_sq']['b']} (p = {p['time_twfe']['bf_ratio_sq']['p']}).",
         "Supported for backlog. Load per active GRO is not a congestion driver once ministry effects are held."),
        ("H2. Ministry differences persist after load",
         f"Ministry effects lift R2 of ATR share from {p['R2_pooled']} to {p['R2_twfe']} (+{p['R2_gain_pp']} pp), N = {p['N_atr']}.",
         "Supported. Process and practice differ by ministry."),
        ("H3. Pooling cuts delay at equal capacity",
         f"M/M/1 vs M/M/2 cuts wait {q['reduction_range'][0]} to {q['reduction_range'][1]} percent. With calibrated Cs2 = {q['cs2']} "
         f"the safe utilisation ceiling rises from {q['rho_threshold_by_desks']['1']} (1 desk) to {q['rho_threshold_by_desks']['4']} (4 desks).",
         "Supported analytically with service time variability calibrated from DARPG ageing data."),
        ("H4. Reforms raised 21 day performance",
         f"Interrupted time series on Little's Law W. Level shift {its['coef']['post21']} days (p = {its['p']['post21']}) after Aug 2024, "
         f"slope change +{its['coef']['t_post21']} (p = {its['p']['t_post21']}).",
         "Partly supported. One time drop in mean time, no lasting change in the aged tail."),
        ("H5. Citizen perceived timeliness lags reported timeliness",
         f"Call centre 2026. {fb['c26_res_pct']} percent confirm resolution, true satisfaction {fb['c26_uncond_sat']} percent. "
         f"Citizen cohort substantive resolution {M['primary']['kpi']['KPI-01']} percent.",
         "Supported by both secondary and primary evidence."),
    ]
    start = None
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        if row[0].value == "Hypothesis":
            start = row[0].row
    ws.cell(start, 2, "Evidence")
    ws.cell(start, 3, "Verdict")
    ws.cell(start, 4).value = None
    for i, (h, e, v) in enumerate(hyp, start + 1):
        ws.cell(i, 1, h)
        ws.cell(i, 2, e)
        ws.cell(i, 3, v)
        ws.cell(i, 4).value = None
        for j in (1, 2, 3):
            ws.cell(i, j).alignment = Alignment(wrap_text=True, vertical="top")

    if "05_Findings_Summary" in wb.sheetnames:
        del wb["05_Findings_Summary"]
    wf = wb.create_sheet("05_Findings_Summary", 0)
    rows = [
        ("Lens", "Metric", "Value", "Source"),
        ("Government", "Mean time in system 2026, Little's Law", f"{M['central']['W_by_year']['2026']} days", "01_Central_Monthly"),
        ("Government", "Clearance ratio Jan 2024 to Oct 2026", f"{M['central']['clearance_total']}%", "01_Central_Monthly"),
        ("Government", "Completions over 21 days (calibrated)", f"{M['tail']['completed_gt21_share']}%", "01 and 02C"),
        ("Government", "Aged 60 days or more held by 10 departments", f"{M['dept35']['top10_share']}%", "04E"),
        ("Government", "Closed within 21 days without ATR", f"{M['atr']['panel_gap_pp']} pp", "02C"),
        ("Government", "Confirmed resolved, call centre 2026", f"{M['feedback']['c26_res_pct']}%", "04B"),
        ("Government", "True satisfaction 2026", f"{M['feedback']['c26_uncond_sat']}%", "04B"),
        ("Citizen", "Substantive resolution", f"{M['primary']['kpi']['KPI-01']}%", "Primary matrix"),
        ("Citizen", "Breach of 21 days", f"{M['primary']['kpi']['KPI-08']}%", "Primary matrix"),
        ("Citizen", "Hollow closures", f"{M['primary']['kpi']['KPI-09']}%", "Primary matrix"),
        ("Citizen", "Mean end to end journey", f"{M['primary']['kpi']['KPI-12']} days", "Primary matrix"),
    ]
    for i, r_ in enumerate(rows, 1):
        for j, v in enumerate(r_, 1):
            c = wf.cell(i, j, v)
            c.border = B_STD
            if i == 1:
                c.font, c.fill = Font(bold=True, color="FFFFFF"), fill(NAVY)
            elif r_[0] == "Citizen":
                c.fill = fill("FFEDD5")
    for col, w in zip("ABCD", (14, 48, 16, 22)):
        wf.column_dimensions[col].width = w
    wb.save(path)
    return path


if __name__ == "__main__":
    print(build_primary())
    print(refresh_secondary())
