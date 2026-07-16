"""
Harmonies — Next-3-Token Probability Trainer
============================================
Enter how many tokens of each color are already visible (market + all
player boards). The app computes exact hypergeometric probabilities for
the next 3 tokens drawn from the bag.

Run with:  streamlit run harmonies_token_stats.py
"""

from itertools import combinations_with_replacement
from math import comb

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------- constants
TOTALS = {
    "Blue": 23,
    "Gray": 23,
    "Brown": 21,
    "Green": 19,
    "Yellow": 19,
    "Red": 15,
}
COLOR_HEX = {
    "Blue": "#2f6fb2",
    "Gray": "#8a8f98",
    "Brown": "#8a5a2b",
    "Green": "#3f8f4f",
    "Yellow": "#d9a520",
    "Red": "#c0392b",
}
COLORS = list(TOTALS)
DRAW = 3  # tokens refilled into the market

st.set_page_config(page_title="Harmonies token odds", page_icon="🎲", layout="wide")

st.title("🎲 Harmonies — next 3 tokens from the bag")
st.caption(
    "Exact draw-without-replacement (hypergeometric) probabilities. "
    "Enter every token you can see: the 15 market tokens plus everything "
    "already placed on all player boards."
)

# ---------------------------------------------------------------- inputs
st.subheader("Visible tokens (market + boards)")
cols = st.columns(len(COLORS))
visible = {}
for col, name in zip(cols, COLORS):
    with col:
        visible[name] = st.number_input(
            f"{name} (of {TOTALS[name]})",
            min_value=0,
            max_value=TOTALS[name],
            value=0,
            step=1,
            key=f"in_{name}",
        )

remaining = {c: TOTALS[c] - visible[c] for c in COLORS}
N = sum(remaining.values())

# Sanity checks
errors = [f"{c}: more visible than exist ({visible[c]} > {TOTALS[c]})"
          for c in COLORS if remaining[c] < 0]
if errors:
    st.error(" · ".join(errors))
    st.stop()
if N < DRAW:
    st.error(f"Only {N} tokens left in the bag — fewer than {DRAW}. Check your inputs.")
    st.stop()

total_visible = sum(visible.values())
denom = comb(N, DRAW)

# ---------------------------------------------------------------- bag overview
st.subheader("Bag composition")
bag_df = pd.DataFrame(
    {
        "Color": COLORS,
        "In game": [TOTALS[c] for c in COLORS],
        "Visible": [visible[c] for c in COLORS],
        "In bag": [remaining[c] for c in COLORS],
        "Share of bag": [remaining[c] / N for c in COLORS],
        "Expected in next 3": [DRAW * remaining[c] / N for c in COLORS],
    }
)
c1, c2 = st.columns([3, 2])
with c1:
    st.dataframe(
        bag_df.style.format({"Share of bag": "{:.1%}", "Expected in next 3": "{:.2f}"}),
        hide_index=True,
        use_container_width=True,
    )
with c2:
    st.metric("Tokens visible", total_visible)
    st.metric("Tokens in bag", N)
    st.bar_chart(bag_df.set_index("Color")["In bag"], color="#6c8ebf")

# ---------------------------------------------------------------- helpers
def p_multiset(counts: dict) -> float:
    """P that the next 3 tokens are exactly this color multiset."""
    num = 1
    for c, k in counts.items():
        if k:
            if remaining[c] < k:
                return 0.0
            num *= comb(remaining[c], k)
    return num / denom


def p_none(colors) -> float:
    """P that none of the given colors appears in the next 3."""
    n_other = N - sum(remaining[c] for c in colors)
    return comb(n_other, DRAW) / denom if n_other >= DRAW else 0.0


def p_exactly(color: str, k: int) -> float:
    """P of exactly k tokens of `color` in the next 3."""
    other = N - remaining[color]
    if remaining[color] < k or other < DRAW - k:
        return 0.0
    return comb(remaining[color], k) * comb(other, DRAW - k) / denom


def swatch(color: str) -> str:
    return (
        f'<span style="display:inline-block;width:14px;height:14px;'
        f'border-radius:3px;background:{COLOR_HEX[color]};margin-right:2px;'
        f'vertical-align:middle;"></span>'
    )


# ---------------------------------------------------------------- top 20 combos
st.subheader("Top 20 most likely 3-token refills")
rows = []
for combo in combinations_with_replacement(COLORS, DRAW):
    counts = {c: combo.count(c) for c in set(combo)}
    p = p_multiset(counts)
    if p > 0:
        rows.append((combo, p))
rows.sort(key=lambda r: r[1], reverse=True)

top = rows[:20]
html_rows = []
for i, (combo, p) in enumerate(top, 1):
    tokens = " ".join(swatch(c) + c[0] for c in combo)
    bar_w = int(round(p / top[0][1] * 100))
    html_rows.append(
        f"<tr><td style='padding:4px 10px'>{i}</td>"
        f"<td style='padding:4px 10px'>{tokens}</td>"
        f"<td style='padding:4px 10px;text-align:right'>{p:.2%}</td>"
        f"<td style='padding:4px 10px;width:220px'>"
        f"<div style='background:#6c8ebf;height:10px;border-radius:5px;width:{bar_w}%'></div>"
        f"</td></tr>"
    )
st.markdown(
    "<table style='border-collapse:collapse'>"
    "<tr><th style='padding:4px 10px'>#</th><th style='padding:4px 10px'>Combo</th>"
    "<th style='padding:4px 10px'>P</th><th></th></tr>"
    + "".join(html_rows)
    + "</table>",
    unsafe_allow_html=True,
)
covered = sum(p for _, p in top)
st.caption(
    f"These 20 combos cover {covered:.1%} of all outcomes "
    f"({len(rows)} distinct combos are possible in total). "
    "Letters are color initials: B=Blue, G=Gray/Green (see swatch), W=Brown… "
    "trust the swatch color."
)

# ---------------------------------------------------------------- per-color odds
st.subheader("Per-color odds in the next 3 tokens")
per_rows = []
for c in COLORS:
    p1 = 1 - p_none([c])
    per_rows.append(
        {
            "Color": c,
            "≥1 arrives": p1,
            "Exactly 1": p_exactly(c, 1),
            "≥2 arrive": p_exactly(c, 2) + p_exactly(c, 3),
            "All 3": p_exactly(c, 3),
            "None": p_none([c]),
        }
    )
per_df = pd.DataFrame(per_rows)
st.dataframe(
    per_df.style.format(
        {k: "{:.1%}" for k in ["≥1 arrives", "Exactly 1", "≥2 arrive", "All 3", "None"]}
    ).background_gradient(subset=["≥1 arrives"], cmap="Greens"),
    hide_index=True,
    use_container_width=True,
)

# ---------------------------------------------------------------- pair odds
st.subheader("Probability that two specific colors BOTH appear")
st.caption(
    "P(≥1 of color A AND ≥1 of color B in the next 3), by inclusion–exclusion. "
    "Useful when a card needs two different terrains started at once."
)
pair_matrix = pd.DataFrame(index=COLORS, columns=COLORS, dtype=float)
for a, b in combinations_with_replacement(COLORS, 2):
    if a == b:
        pair_matrix.loc[a, b] = p_exactly(a, 2) + p_exactly(a, 3)  # ≥2 of same color
    else:
        p = 1 - p_none([a]) - p_none([b]) + p_none([a, b])
        pair_matrix.loc[a, b] = p
        pair_matrix.loc[b, a] = p
st.dataframe(
    pair_matrix.style.format("{:.1%}").background_gradient(cmap="Blues", axis=None),
    use_container_width=True,
)
st.caption("Diagonal = probability of drawing at least 2 tokens of that same color.")

with st.expander("Check a specific pair"):
    pc1, pc2 = st.columns(2)
    a = pc1.selectbox("Color A", COLORS, index=0)
    b = pc2.selectbox("Color B", COLORS, index=1)
    if a == b:
        p = p_exactly(a, 2) + p_exactly(a, 3)
        st.metric(f"P(≥2 {a} in next 3)", f"{p:.1%}")
    else:
        p = 1 - p_none([a]) - p_none([b]) + p_none([a, b])
        st.metric(f"P(≥1 {a} AND ≥1 {b})", f"{p:.1%}")

# ---------------------------------------------------------------- extra training stats
st.subheader("Extra training stats")
p_all_same = sum(p_exactly(c, 3) for c in COLORS)
p_all_diff = sum(
    remaining[a] * remaining[b] * remaining[c] / denom
    for i, a in enumerate(COLORS)
    for j, b in enumerate(COLORS)
    for k, c in enumerate(COLORS)
    if i < j < k
)
p_pair_plus = 1 - p_all_same - p_all_diff

m1, m2, m3 = st.columns(3)
m1.metric("All 3 same color", f"{p_all_same:.1%}")
m2.metric("Exactly a pair (2+1)", f"{p_pair_plus:.1%}")
m3.metric("All 3 different colors", f"{p_all_diff:.1%}")

st.markdown("**Most and least likely single colors next**")
p1_sorted = sorted(per_rows, key=lambda r: r["≥1 arrives"], reverse=True)
hi, lo = p1_sorted[0], p1_sorted[-1]
st.write(
    f"- Best bet to appear: **{hi['Color']}** ({hi['≥1 arrives']:.1%} chance of ≥1)\n"
    f"- Longest shot: **{lo['Color']}** ({lo['≥1 arrives']:.1%} chance of ≥1)"
)

st.markdown("**Rarity pressure (how depleted each color is)**")
depl = pd.DataFrame(
    {
        "Color": COLORS,
        "Drawn so far": [visible[c] / TOTALS[c] for c in COLORS],
    }
).sort_values("Drawn so far", ascending=False)
st.dataframe(
    depl.style.format({"Drawn so far": "{:.0%}"}).background_gradient(
        subset=["Drawn so far"], cmap="Reds"
    ),
    hide_index=True,
    use_container_width=True,
)
st.caption(
    "A color drawn well above its bag share is getting scarce — don't build a "
    "plan that needs several more of it. A color drawn below its share is "
    "'owed' appearances and is safer to plan around."
)
