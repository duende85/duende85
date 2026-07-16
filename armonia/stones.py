"""
Harmonies — Next-3-Token Probability Dashboard
==============================================
Enter how many tokens of each color are visible (market + all player
boards) in the sidebar. Everything else updates as one dense screen of
exact hypergeometric stats for the next 3 tokens drawn from the bag.

Run with:  streamlit run harmonies_token_stats.py
"""

from itertools import combinations_with_replacement
from math import comb

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------- constants
TOTALS = {"Blue": 23, "Gray": 23, "Brown": 21, "Green": 19, "Yellow": 19, "Red": 15}
HEX = {
    "Blue": "#3B82C4", "Gray": "#9AA0A8", "Brown": "#9A6A38",
    "Green": "#4C9A5C", "Yellow": "#D9A520", "Red": "#C44536",
}
COLORS = list(TOTALS)
DRAW = 3

st.set_page_config(page_title="Harmonies odds", page_icon="🎲", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------- global CSS
st.markdown("""
<style>
/* tighten the whole page */
.block-container {padding-top: 1.1rem; padding-bottom: 1rem; max-width: 1500px;}
header[data-testid="stHeader"] {height: 0; visibility: hidden;}
h1, h2, h3 {margin: 0;}
div[data-testid="stVerticalBlock"] {gap: 0.55rem;}
section[data-testid="stSidebar"] .block-container {padding-top: 1rem;}
section[data-testid="stSidebar"] div[data-testid="stNumberInput"] label {font-size: 12px;}
section[data-testid="stSidebar"] div[data-testid="stNumberInput"] input {padding: 2px 6px; font-size: 14px;}

/* dashboard typography */
.dash-title {font-size: 20px; font-weight: 700; letter-spacing: -0.01em;}
.dash-sub {font-size: 12px; color: #6b7280; margin-bottom: 4px;}
.sec {font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
      color: #6b7280; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; margin: 6px 0 6px 0;}

/* KPI cards */
.kpis {display: flex; gap: 8px; flex-wrap: wrap;}
.kpi {flex: 1 1 0; min-width: 110px; background: #f8fafc; border: 1px solid #e5e7eb;
      border-radius: 8px; padding: 7px 10px;}
.kpi .v {font-size: 20px; font-weight: 700; line-height: 1.1;}
.kpi .l {font-size: 10.5px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;}

/* dense tables */
table.dense {border-collapse: collapse; width: 100%; font-size: 12.5px;}
table.dense th {text-align: left; font-size: 10.5px; text-transform: uppercase;
                letter-spacing: 0.05em; color: #6b7280; padding: 2px 6px;
                border-bottom: 1px solid #e5e7eb; font-weight: 600;}
table.dense td {padding: 2.5px 6px; border-bottom: 1px solid #f1f5f9; white-space: nowrap;}
table.dense td.num {text-align: right; font-variant-numeric: tabular-nums;}
.sw {display:inline-block; width:11px; height:11px; border-radius:3px;
     vertical-align:-1px; margin-right:5px;}
.tok {display:inline-block; width:15px; height:15px; border-radius:50%;
      vertical-align:-3px; margin-right:3px; border:1px solid rgba(0,0,0,.15);}
.bar-wrap {background:#eef2f6; border-radius:3px; height:8px; width:100%;}
.bar {height:8px; border-radius:3px; background:#3B82C4;}
.hot  {color:#166534; font-weight:600;}
.cold {color:#991b1b; font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- sidebar inputs
with st.sidebar:
    st.markdown('<div class="dash-title">Visible tokens</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-sub">Market + all player boards</div>', unsafe_allow_html=True)
    visible = {}
    sc = st.columns(2)
    for i, name in enumerate(COLORS):
        with sc[i % 2]:
            visible[name] = st.number_input(
                f"{name} /{TOTALS[name]}", 0, TOTALS[name], 0, 1, key=f"in_{name}"
            )
    st.caption("Tip: at game start, type the 15 market tokens you see.")

remaining = {c: TOTALS[c] - visible[c] for c in COLORS}
N = sum(remaining.values())
if N < DRAW:
    st.error(f"Only {N} tokens left in the bag — fewer than {DRAW}.")
    st.stop()

denom = comb(N, DRAW)
total_visible = sum(visible.values())

# ---------------------------------------------------------------- math helpers
def p_multiset(counts):
    num = 1
    for c, k in counts.items():
        if remaining[c] < k:
            return 0.0
        num *= comb(remaining[c], k)
    return num / denom

def p_none(cols):
    n_other = N - sum(remaining[c] for c in cols)
    return comb(n_other, DRAW) / denom if n_other >= DRAW else 0.0

def p_exactly(c, k):
    other = N - remaining[c]
    if remaining[c] < k or other < DRAW - k:
        return 0.0
    return comb(remaining[c], k) * comb(other, DRAW - k) / denom

def sw(c):
    return f'<span class="sw" style="background:{HEX[c]}"></span>'

def tok(c):
    return f'<span class="tok" style="background:{HEX[c]}"></span>'

# ---------------------------------------------------------------- precompute
per = {c: {
    "p1": 1 - p_none([c]),
    "e1": p_exactly(c, 1),
    "e2": p_exactly(c, 2),
    "e3": p_exactly(c, 3),
} for c in COLORS}

combos = []
for combo in combinations_with_replacement(COLORS, DRAW):
    counts = {c: combo.count(c) for c in set(combo)}
    p = p_multiset(counts)
    if p > 0:
        combos.append((combo, p))
combos.sort(key=lambda r: r[1], reverse=True)
top = combos[:20]
covered = sum(p for _, p in top)

p_all_same = sum(per[c]["e3"] for c in COLORS)
p_all_diff = sum(
    remaining[a] * remaining[b] * remaining[c] / denom
    for i, a in enumerate(COLORS) for j, b in enumerate(COLORS)
    for k, c in enumerate(COLORS) if i < j < k
)
p_pair = 1 - p_all_same - p_all_diff

p1_sorted = sorted(COLORS, key=lambda c: per[c]["p1"], reverse=True)
hi, lo = p1_sorted[0], p1_sorted[-1]

# ---------------------------------------------------------------- header + KPIs
st.markdown('<div class="dash-title">🎲 Harmonies — next 3 tokens from the bag</div>'
            '<div class="dash-sub">Exact hypergeometric odds · updates live from the sidebar</div>',
            unsafe_allow_html=True)

st.markdown(f"""
<div class="kpis">
  <div class="kpi"><div class="v">{N}</div><div class="l">In bag</div></div>
  <div class="kpi"><div class="v">{total_visible}</div><div class="l">Visible</div></div>
  <div class="kpi"><div class="v">{sw(hi)}{per[hi]['p1']:.0%}</div><div class="l">Best bet · {hi}</div></div>
  <div class="kpi"><div class="v">{sw(lo)}{per[lo]['p1']:.0%}</div><div class="l">Long shot · {lo}</div></div>
  <div class="kpi"><div class="v">{p_all_diff:.0%}</div><div class="l">All different</div></div>
  <div class="kpi"><div class="v">{p_pair:.0%}</div><div class="l">Pair + 1</div></div>
  <div class="kpi"><div class="v">{p_all_same:.0%}</div><div class="l">All same</div></div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- main grid
left, mid, right = st.columns([1.05, 1.0, 1.15], gap="medium")

# ---- LEFT: bag composition + depletion
with left:
    st.markdown('<div class="sec">Bag composition</div>', unsafe_allow_html=True)
    rows = []
    for c in sorted(COLORS, key=lambda x: remaining[x], reverse=True):
        share = remaining[c] / N
        exp = DRAW * share
        w = int(round(remaining[c] / max(remaining.values()) * 100)) if max(remaining.values()) else 0
        rows.append(
            f"<tr><td>{sw(c)}{c}</td>"
            f"<td class='num'>{remaining[c]}/{TOTALS[c]}</td>"
            f"<td class='num'>{share:.0%}</td>"
            f"<td class='num'>{exp:.2f}</td>"
            f"<td style='width:34%'><div class='bar-wrap'><div class='bar' "
            f"style='width:{w}%;background:{HEX[c]}'></div></div></td></tr>"
        )
    st.markdown("<table class='dense'><tr><th>Color</th><th>Bag</th><th>Share</th>"
                "<th>E[next 3]</th><th></th></tr>" + "".join(rows) + "</table>",
                unsafe_allow_html=True)

    st.markdown('<div class="sec">Depletion pressure</div>', unsafe_allow_html=True)
    rows = []
    for c in sorted(COLORS, key=lambda x: visible[x] / TOTALS[x], reverse=True):
        d = visible[c] / TOTALS[c]
        cls = "cold" if d >= 0.5 else ("hot" if d <= 0.2 else "")
        rows.append(
            f"<tr><td>{sw(c)}{c}</td><td class='num {cls}'>{d:.0%}</td>"
            f"<td style='width:45%'><div class='bar-wrap'><div class='bar' "
            f"style='width:{int(d*100)}%;background:{HEX[c]}'></div></div></td></tr>"
        )
    st.markdown("<table class='dense'><tr><th>Color</th><th>Drawn</th><th></th></tr>"
                + "".join(rows) + "</table>", unsafe_allow_html=True)
    st.markdown('<div class="dash-sub">Red % = scarce, don\'t plan around it. '
                'Green % = "owed" appearances.</div>', unsafe_allow_html=True)

# ---- MID: per-color odds + pair matrix
with mid:
    st.markdown('<div class="sec">Per-color odds · next 3</div>', unsafe_allow_html=True)
    rows = []
    for c in sorted(COLORS, key=lambda x: per[x]["p1"], reverse=True):
        d = per[c]
        rows.append(
            f"<tr><td>{sw(c)}{c}</td>"
            f"<td class='num'><b>{d['p1']:.0%}</b></td>"
            f"<td class='num'>{d['e1']:.0%}</td>"
            f"<td class='num'>{d['e2'] + d['e3']:.1%}</td>"
            f"<td class='num'>{d['e3']:.2%}</td></tr>"
        )
    st.markdown("<table class='dense'><tr><th>Color</th><th>≥1</th><th>=1</th>"
                "<th>≥2</th><th>=3</th></tr>" + "".join(rows) + "</table>",
                unsafe_allow_html=True)

    st.markdown('<div class="sec">Both colors appear (A ∧ B)</div>', unsafe_allow_html=True)
    # compact matrix, upper triangle; diagonal = P(≥2 same)
    head = "<tr><th></th>" + "".join(f"<th style='text-align:right'>{sw(c)}</th>" for c in COLORS) + "</tr>"
    body = []
    pair_p = {}
    for i, a in enumerate(COLORS):
        cells = [f"<td>{sw(a)}{a[:3]}</td>"]
        for j, b in enumerate(COLORS):
            if j < i:
                cells.append("<td></td>")
                continue
            if a == b:
                p = per[a]["e2"] + per[a]["e3"]
            else:
                p = 1 - p_none([a]) - p_none([b]) + p_none([a, b])
            pair_p[(a, b)] = pair_p[(b, a)] = p
            shade = int(255 - min(p, 0.35) / 0.35 * 90)
            cells.append(f"<td class='num' style='background:rgb({shade},{shade+int((255-shade)*0.4)},255)'>{p:.0%}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown("<table class='dense'>" + head + "".join(body) + "</table>",
                unsafe_allow_html=True)
    st.markdown('<div class="dash-sub">Diagonal = P(≥2 of that same color).</div>',
                unsafe_allow_html=True)

# ---- RIGHT: top 20 combos
with right:
    st.markdown(f'<div class="sec">Top 20 refills · cover {covered:.0%} of outcomes</div>',
                unsafe_allow_html=True)
    half = (len(top) + 1) // 2
    cols2 = st.columns(2, gap="small")
    pmax = top[0][1]
    for ci, chunk in enumerate([top[:half], top[half:]]):
        rows = []
        for i, (combo, p) in enumerate(chunk, 1 + ci * half):
            tokens = "".join(tok(c) for c in combo)
            w = int(round(p / pmax * 100))
            rows.append(
                f"<tr><td class='num' style='color:#9ca3af'>{i}</td>"
                f"<td>{tokens}</td>"
                f"<td class='num'><b>{p:.1%}</b></td>"
                f"<td style='width:30%'><div class='bar-wrap'><div class='bar' "
                f"style='width:{w}%'></div></div></td></tr>"
            )
        with cols2[ci]:
            st.markdown("<table class='dense'>" + "".join(rows) + "</table>",
                        unsafe_allow_html=True)

    st.markdown('<div class="sec">Pair check</div>', unsafe_allow_html=True)
    pc1, pc2 = st.columns(2)
    a = pc1.selectbox("Color A", COLORS, index=0, label_visibility="collapsed")
    b = pc2.selectbox("Color B", COLORS, index=5, label_visibility="collapsed")
    p = pair_p[(a, b)]
    label = f"P(≥2 {a})" if a == b else f"P(≥1 {a} ∧ ≥1 {b})"
    st.markdown(f"""
    <div class="kpi" style="max-width:260px"><div class="v">{sw(a)}{sw(b)}{p:.1%}</div>
    <div class="l">{label}</div></div>
    """, unsafe_allow_html=True)
