"""
Step 1. Extract raw data tables from the two project workbooks into flat CSV files.

Secondary data  : data/workbooks/CPGRAMS_Complete_Dataset_2016_2026.xlsx
Primary data    : data/workbooks/CPGRAMS_Primary_Research_Raw_Data_Matrix.xlsx

Only typed input values are exported. Every derived column (ratios, residuals,
Little's Law waits and so on) is dropped here and recomputed in 02_analysis.py
so that each number in the report can be traced to one line of Python.

Run from the repository root
    python code/01_extract_raw_data.py
"""

from __future__ import annotations

import re
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WB_DIR = ROOT / "data" / "workbooks"
SEC_OUT = ROOT / "data" / "raw" / "secondary"
PRI_OUT = ROOT / "data" / "raw" / "primary"


BLOCK_NAMES = {
    ("02A_GRAI_Methodology_Breaks", 1): "structural_breaks",
    ("02B_GRAI_Rankings_2024_2026", 1): "groupB_dec2025",
    ("02B_GRAI_Rankings_2024_2026", 2): "postbreak_dimensions_2026",
    ("02D_Secretary_Reviews_Policy", 1): "review_meeting_logs",
    ("04A_StateUT_Monthly_Sevottam", 1): "sevottam_training",
    ("04F_Queuing_MM1_MM2_Hypotheses", 1): "hypothesis_matrix",
}


def _is_formula(v) -> bool:
    return isinstance(v, str) and v.startswith("=")


def _split_blocks(ws):
    """Split a worksheet into tables. A new table starts after a blank row
    followed by a single-cell banner row, the next row being the header."""
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    blocks, current, name = [], [], "main"
    i = 0
    while i < len(rows):
        r = rows[i]
        nonempty = [v for v in r if v not in (None, "")]
        if not nonempty:
            # blank separator, next row is a banner
            if current:
                blocks.append((name, current))
            current = []
            if i + 1 < len(rows):
                name = str(rows[i + 1][0])
                i += 2
                continue
        else:
            current.append(r)
        i += 1
    if current:
        blocks.append((name, current))
    return blocks


def _block_to_frame(block_rows):
    header = [h for h in block_rows[0] if h not in (None, "")]
    body = [r[: len(header)] for r in block_rows[1:]]
    df = pd.DataFrame(body, columns=header)
    # a column is "derived" when most of its filled cells are formulas
    keep_cols = []
    for c in df.columns:
        filled = df[c].dropna()
        filled = filled[filled != ""]
        share = filled.map(_is_formula).mean() if len(filled) else 0
        if share < 0.5:
            keep_cols.append(c)
    df = df[keep_cols]
    # remaining formula cells only sit in total rows, which are recomputed later
    df = df[~df.apply(lambda s: s.map(_is_formula)).any(axis=1)]
    return df.dropna(how="all")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48]


def extract_secondary():
    wb = openpyxl.load_workbook(WB_DIR / "CPGRAMS_Complete_Dataset_2016_2026.xlsx")
    written = []
    for ws in wb:
        if ws.title.startswith("05_"):
            continue  # summary sheet written by 04_build_workbooks.py
        for k, (bname, rows) in enumerate(_split_blocks(ws)):
            df = _block_to_frame(rows)
            if df.empty:
                continue
            suffix = BLOCK_NAMES.get((ws.title, k), _slug(bname))
            stem = ws.title if k == 0 else f"{ws.title}__{suffix}"
            out = SEC_OUT / f"{stem}.csv"
            df.to_csv(out, index=False)
            written.append((out.name, len(df)))
    return written


def extract_primary():
    wb = openpyxl.load_workbook(WB_DIR / "CPGRAMS_Primary_Research_Raw_Data_Matrix.xlsx")
    written = []
    for title in ("Raw_Case_Matrix", "CSAT_Survey_Matrix"):
        rows = [list(r) for r in wb[title].iter_rows(values_only=True)]
        h = next(i for i, r in enumerate(rows) if r[0] in ("Case_ID", "Respondent_ID"))
        body = [r for r in rows[h + 1:] if r[0] and not str(r[0]).startswith("MEAN")]
        df = pd.DataFrame(body, columns=rows[h]).dropna(how="all")
        out = PRI_OUT / f"{title}.csv"
        df.to_csv(out, index=False)
        written.append((out.name, len(df)))
    return written


if __name__ == "__main__":
    SEC_OUT.mkdir(parents=True, exist_ok=True)
    PRI_OUT.mkdir(parents=True, exist_ok=True)
    for name, n in extract_secondary() + extract_primary():
        print(f"{name:<70} {n:>4} rows")
