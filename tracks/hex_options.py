#!/usr/bin/env python3
"""Tantrix bag tracker + dashboard.

STREAMLIT DASHBOARD (recommended):
    pip install streamlit mss
    streamlit run tantrix_app.py        # normal way
    python tantrix_app.py               # ALSO works (incl. Spyder runfile):
                                        # starts the server + opens the browser
  Then use the sidebar: Scan screen (game must be visible), or upload a
  screenshot; enter forced-space combos like  RGB, YYB ; set the draw count
  for probabilities.

CLI (Spyder / terminal):
    python tantrix_app.py                      # scan all monitors
    python tantrix_app.py shot.png             # analyze a screenshot
    python tantrix_app.py --combo RGB --combo YYB
"""

import sys, math, time, json, collections
from itertools import permutations, combinations

def _pip_install(pkg):
    """pip install that works across normal, PEP-668, and user-only setups."""
    import subprocess
    for extra in ([], ['--user'], ['--break-system-packages']):
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install',
                                   '--quiet', pkg] + extra,
                                  stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False

def _ensure(mod, pkg, required=True):
    import importlib
    try:
        importlib.import_module(mod)
        return True
    except ImportError:
        print(f"first run: installing {pkg} ...")
        if _pip_install(pkg):
            importlib.invalidate_caches()
            try:
                importlib.import_module(mod)
                return True
            except ImportError:
                pass
        if required:
            sys.exit(f"could not install required package '{pkg}'. "
                     f"Please run:  pip install {pkg}")
        return False

def _bootstrap():
    for mod, pkg in [('numpy', 'numpy'), ('PIL', 'pillow'), ('scipy', 'scipy')]:
        _ensure(mod, pkg, required=True)
_bootstrap()

import numpy as np
from PIL import Image
from scipy import ndimage

# ---------------------------------------------------------------- tiles
COLORS = ['R', 'B', 'G', 'Y']
SHAPES = {
    'AABBCC': [(0, 1), (2, 3), (4, 5)],   # 3 short curves
    'AABCCB': [(0, 1), (2, 5), (3, 4)],   # 2 short curves + straight
    'AABCBC': [(0, 1), (2, 4), (3, 5)],   # 1 short + 2 long curves
    'ABACBC': [(0, 2), (1, 4), (3, 5)],   # 2 long curves + straight
}

def canon(t):
    return min(tuple(t[(i + r) % 6] for i in range(6)) for r in range(6))

def all_tiles():
    seen, out = set(), []
    for shape, pairs in SHAPES.items():
        for trio in combinations(COLORS, 3):
            for perm in permutations(trio):
                t = [None] * 6
                for pair, c in zip(pairs, perm):
                    for e in pair:
                        t[e] = c
                c = ''.join(canon(t))
                if c not in seen:
                    seen.add(c)
                    out.append((shape, ''.join(trio), c))
    return out

TILES = all_tiles()
FULL = {t for _, _, t in TILES}
SHAPE_OF = {t: (s, tr) for s, tr, t in TILES}
assert len(FULL) == 56

# ------------------------------------------------------------ pixel classes
REF = {'R': (253, 0, 0), 'B': (50, 50, 253), 'G': (30, 170, 60), 'Y': (211, 212, 4)}

def make_classifier(img):
    """Vectorized-ish per-pixel classifier. Returns cls(y,x) -> D/L/R/B/G/Y."""
    def cls(y, x):
        r, g, b = img[y, x]
        mx = max(r, g, b)
        if mx < 80:
            return 'D'                      # black tile body
        if mx - min(r, g, b) < 60:
            return 'L'                      # gray background / seams
        best, bd = None, 1 << 30
        for k, (rr, gg, bb) in REF.items():
            d = (r - rr) ** 2 + (g - gg) ** 2 + (b - bb) ** 2
            if d < bd:
                best, bd = k, d
        return best
    return cls

# ------------------------------------------------------------ calibration
def calibrate(img, bri):
    """Return list of (apothem, row_pitch) candidates, best first, or None.
    Derived from autocorrelation of the seam pattern inside the board blob."""
    dark = bri < 80
    if int(dark.sum()) < 2000:
        return None
    lab, n = ndimage.label(dark)
    if n == 0:
        return None
    sizes = ndimage.sum(dark, lab, range(1, n + 1))
    ys, xs = np.nonzero(lab == int(np.argmax(sizes)) + 1)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    if y1 - y0 < 80 or x1 - x0 < 80:
        return None
    reg = bri[y0:y1, x0:x1]
    seam = (reg > 90) & (reg < 160)

    def top_periods(v, lo, hi, k=6):
        v = v - v.mean()
        scored = []
        for p in range(lo, min(hi, len(v) // 2)):
            s, c = 0.0, 0
            for m in (1, 2, 3):
                if m * p < len(v) - 5:
                    r = np.corrcoef(v[:-m * p], v[m * p:])[0, 1]
                    if not np.isnan(r):
                        s += r; c += 1
            if c:
                scored.append((s / c, p))
        scored.sort(reverse=True)
        return scored[:k]

    pxs = top_periods(seam.sum(axis=0), 15, 140)
    pys = top_periods(seam.sum(axis=1), 15, 140)
    if not pxs or not pys:
        return None

    cands = []
    for sx, px in pxs:
        for sy, py in pys:
            for fx in (1, 2, 0.5):
                for fy in (1, 2, 0.5):
                    ax, vy = px * fx, py * fy
                    if 15 <= ax <= 150 and 1.55 < vy / ax < 1.95:
                        score = sx + sy - 3 * abs(vy / ax - math.sqrt(3))
                        cands.append((score, float(ax), float(vy)))
    if not cands:
        return None
    cands.sort(reverse=True)
    seen, out = set(), []
    for _, ax, vy in cands:
        key = (round(ax), round(vy))
        if key not in seen:
            seen.add(key)
            out.append((ax, vy))
    return out

# ------------------------------------------------------------ tile reading
def read_tile(cls, H, W, cx, cy, a):
    """Read 6 edge colors of pointy-top hex at (cx,cy), apothem a."""
    out = []
    for i in range(6):
        ang = math.radians(30 + 60 * i - 90)
        votes = {}
        for f in np.linspace(0.68, 0.97, 12):
            for perp in (-2, -1, 0, 1, 2):
                x = int(cx + f * a * math.cos(ang) - perp * math.sin(ang))
                y = int(cy + f * a * math.sin(ang) + perp * math.cos(ang))
                if 0 <= y < H and 0 <= x < W:
                    c = cls(y, x)
                    if c in REF:
                        votes[c] = votes.get(c, 0) + 1
        if not votes:
            return None
        out.append(max(votes, key=votes.get))
    return ''.join(out)

def voted_read(cls, H, W, cx, cy, a, jitter=4):
    """Majority tile over a small grid of center jitters. -> (tile, votes)."""
    votes = collections.Counter()
    for dx in range(-jitter, jitter + 1, 2):
        for dy in range(-jitter, jitter + 1, 2):
            s = read_tile(cls, H, W, cx + dx, cy + dy, a)
            if s and len(set(s)) == 3:
                c = ''.join(canon(list(s)))
                if c in FULL:
                    votes[c] += 1
    if not votes:
        return None, 0
    t, n = votes.most_common(1)[0]
    return t, n

# ------------------------------------------------------------ board
def read_board_region(img, cls, bri, a, vy, x_lo, x_hi, y_lo, y_hi):
    """Global hex lattice anchored on the board blob, with the lattice pitch
    re-derived exactly from the blob extents (kills cumulative drift)."""
    H, W = bri.shape
    yt, yb = y_lo, y_hi
    xl, xr = x_lo, x_hi
    dark = bri < 80
    sub = dark[y_lo:y_hi + 1, x_lo:x_hi + 1]
    ys, xs = np.nonzero(sub)
    ys = ys + y_lo; xs = xs + x_lo

    # exact pitches from blob extents (span = integer number of steps)
    R = 2 * a / math.sqrt(3)
    kx = max(1, round((xr - xl - 2 * a) / a))
    a_ex = (xr - xl - 2 * a) / kx if kx else a
    if abs(a_ex - a) < 0.15 * a:
        a = a_ex
    R = 2 * a / math.sqrt(3)
    ky = max(1, round((yb - yt - 2 * R) / vy))
    vy_ex = (yb - yt - 2 * R) / ky if ky else vy
    if abs(vy_ex - vy) < 0.15 * vy:
        vy = vy_ex

    # topmost vertex: use the first contiguous run of dark pixels on the
    # topmost dark row (there may be several tiles starting at that height)
    ytop = int(ys.min())
    row = np.sort(xs[ys == ytop])
    runs, cur = [], [row[0]]
    for v in row[1:]:
        if v - cur[-1] <= 3:
            cur.append(v)
        else:
            runs.append(cur); cur = [v]
    runs.append(cur)
    run = max(runs, key=len)
    cx0, cy0 = float(np.mean(run)), ytop + R      # center of top tile

    def frac_tileish(x, y, rad):
        cnt = tot = 0
        for dy in range(-rad, rad + 1, 3):
            for dx in range(-rad, rad + 1, 3):
                if dx * dx + dy * dy > rad * rad:
                    continue
                yy, xx = int(y + dy), int(x + dx)
                if not (0 <= yy < H and 0 <= xx < W):
                    return 0.0
                if cls(yy, xx) != 'L':
                    cnt += 1
                tot += 1
        return cnt / tot if tot else 0.0

    rad = int(a * 0.6)
    board = {}
    jmax = int((yb - cy0) / vy) + 2
    for j in range(-1, jmax + 1):
        y = cy0 + j * vy
        if not (a < y < H - a):
            continue
        for m in range(-40, 41):
            if (m + j) % 2:
                continue                      # lattice parity
            x = cx0 + a * m
            if not (xl - a < x < xr + a):
                continue
            if frac_tileish(x, y, rad) < 0.92:
                continue
            t, nv = voted_read(cls, H, W, x, y, a)
            if t and nv >= 6:
                board[(m, j)] = (int(x), int(y), t, nv)
    return board

# ------------------------------------------------------------ hand panels
def read_panel(img, cls, bri, x0, x1, a_panel=35.0, pitch=82):
    H, W = bri.shape
    sub_dark = bri[:, x0:x1] < 80
    lab, n = ndimage.label(sub_dark)
    res = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < 1200:
            continue
        y0b, y1b = ys.min(), ys.max()
        h = y1b - y0b + 1
        k = max(1, round(h / pitch))
        cx = x0 + xs.mean()
        for m in range(k):
            cy = y0b + h * (2 * m + 1) / (2 * k)
            t, nv = voted_read(cls, H, W, cx, cy, a_panel)
            if t and nv >= 3:
                res.append((int(cy), t, nv))
    res.sort()
    return [t for _, t, _ in res]

# ------------------------------------------------------------ full frame
def analyze(img_arr, verbose=False):
    """Read every Tantrix tile visible anywhere in the frame (board, hands,
    any window position). bag = 56 - seen."""
    img = img_arr.astype(int)
    H, W = img.shape[:2]
    bri = img.max(axis=2)
    cls = make_classifier(img)

    mx = img.max(axis=2); mn = img.min(axis=2)
    dark = mx < 80
    vivid = (mx - mn > 70) & (mx > 80)
    is_r = vivid & (img[..., 0] > img[..., 1]) & (img[..., 0] > img[..., 2]) & (img[..., 1] < 120)
    is_y = vivid & (img[..., 0] > 150) & (img[..., 1] > 150) & (img[..., 2] < 120)
    is_g = vivid & (img[..., 1] > img[..., 0]) & (img[..., 1] > img[..., 2])
    is_b = vivid & (img[..., 2] > img[..., 0]) & (img[..., 2] > img[..., 1])

    lab, n = ndimage.label(dark | vivid)   # tile body + its colored lines
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        area = len(ys)
        if area < 1500:
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        w, h = x1 - x0 + 1, y1 - y0 + 1
        if w < 30 or h < 30:
            continue
        box = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        vfrac = vivid[box].sum() / area
        fill = area / (w * h)
        ncols = sum(1 for m in (is_r, is_y, is_g, is_b) if m[box].sum() > 0.01 * area)
        # relaxed: any plausible tile region (sprawling boards can have low
        # bbox fill); strict: unmistakably tile-shaped (used for sizing)
        relaxed = 0.15 < fill < 0.97 and 0.08 < vfrac < 0.60 and ncols >= 3
        strict = 0.55 < fill < 0.90 and 0.15 < vfrac < 0.45 and ncols >= 3
        if not relaxed:
            continue
        comps.append({'ys': ys, 'xs': xs, 'x0': x0, 'x1': x1,
                      'y0': y0, 'y1': y1, 'area': area, 'strict': strict})
    if not comps:
        if verbose:
            print("!! no Tantrix tiles found in this frame")
        return None

    # ---- estimate apothem: narrowest STRICT tile component = one tile wide
    widths = sorted(c['x1'] - c['x0'] + 1 for c in comps
                    if c['strict'] and 30 < c['x1'] - c['x0'] < 320)
    if not widths:
        if verbose:
            print("!! could not estimate tile size")
        return None
    w_tile = widths[0]
    a = w_tile / 2.0 - 0.5
    # cross-check with seam calibration on the biggest blob if it is a board
    cands = calibrate(img, bri)
    if cands:
        for ca, cvy in cands[:3]:
            if abs(ca - a) / a < 0.15:
                a = ca
                break
    R = 2 * a / math.sqrt(3)
    vy = a * math.sqrt(3)

    reads = []          # (x, y, tile, votes, kind)
    for c in comps:
        w = c['x1'] - c['x0'] + 1
        h = c['y1'] - c['y0'] + 1
        if w < 1.4 * w_tile:
            # vertical stack of k tiles (hand panel) or a single tile
            k = max(1, round(h / (2 * R)))
            cx = c['xs'].mean()
            for m in range(k):
                cy = c['y0'] + h * (2 * m + 1) / (2 * k)
                t, nv = voted_read(cls, H, W, cx, cy, a * 0.985)
                if t and nv >= 3:
                    reads.append((cx, cy, t, nv, 'stack'))
        else:
            # multi-column region: hex-lattice board
            board = read_board_region(img, cls, bri, a, vy,
                                      c['x0'], c['x1'], c['y0'], c['y1'])
            for _, (x, y, t, nv) in board.items():
                reads.append((x, y, t, nv, 'board'))

    # de-duplicate physical positions (a tile can straddle two components)
    reads.sort(key=lambda r: -r[3])
    kept = []
    for x, y, t, nv, kind in reads:
        if any((x - kx) ** 2 + (y - ky) ** 2 < (1.2 * a) ** 2
               for kx, ky, *_ in kept):
            continue
        kept.append((x, y, t, nv, kind))
    seen_tiles = [t for _, _, t, _, _ in kept]
    n_board = sum(1 for k in kept if k[4] == 'board')
    n_stack = len(kept) - n_board

    dups = [t for t, k in collections.Counter(seen_tiles).items() if k > 1]
    missing = sorted(FULL - set(seen_tiles))
    return {'seen': seen_tiles, 'missing': missing, 'dups': dups,
            'n_board': n_board, 'n_stack': n_stack, 'apothem': a}


# ================================================================ combos
from math import comb

def triples_of(tile):
    """All 3-consecutive-edge color sequences of a tile (both directions),
    canonicalized as min(seq, reversed(seq))."""
    out = set()
    for i in range(6):
        s = tile[i] + tile[(i + 1) % 6] + tile[(i + 2) % 6]
        out.add(min(s, s[::-1]))
    return out

def canon_combo(s):
    s = ''.join(ch for ch in s.upper() if ch in 'RBGY')
    if len(s) != 3:
        return None
    return min(s, s[::-1])

def combo_clusters(bag):
    """dict canonical-combo -> sorted list of bag tiles containing it."""
    clusters = collections.defaultdict(list)
    for t in bag:
        for c in triples_of(t):
            clusters[c].append(t)
    return {c: sorted(v) for c, v in clusters.items()}

def p_at_least_one(k, N, n):
    """P(>=1 of k special tiles among n drawn from bag of N)."""
    if N <= 0 or n <= 0 or k <= 0:
        return 0.0
    n = min(n, N)
    if k >= N or n + k > N:
        pass
    none = comb(N - k, n) / comb(N, n) if N - k >= n else 0.0
    return 1.0 - none

# ================================================================ CLI
def report_cli(res, wanted):
    bag = res['missing']
    N = len(bag)
    print(f"visible tiles read: {len(res['seen'])} "
          f"(board {res['n_board']}, hands/loose {res['n_stack']})")
    if res['dups']:
        print(f"!! WARNING duplicate reads: {res['dups']}")
    print(f"\nBAG — {N} tiles remaining\n")
    clusters = combo_clusters(bag)
    wanted_c, lbl = [], {}
    for x in wanted:
        c = canon_combo(x)
        if c:
            wanted_c.append(c)
            lbl[c] = ''.join(ch for ch in x.upper() if ch in 'RBGY')
    order = sorted(clusters, key=lambda c: (c not in wanted_c, c))
    for c in order:
        tiles = clusters[c]
        mark = '  << WANTED' if c in wanted_c else ''
        print(f"{lbl.get(c, c)}  ({len(tiles)}/{N}){mark}")
        print('   ' + '  '.join(tiles))
    missing_wanted = [w for w in wanted_c if w not in clusters]
    for w in missing_wanted:
        print(f"{w}  (0/{N})  << WANTED — no tile in the bag fits!")

# ================================================================ Streamlit
def running_in_streamlit():
    try:
        import logging
        logging.getLogger('streamlit').setLevel(logging.ERROR)
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False

def streamlit_app():
    import streamlit as st
    st.set_page_config(page_title='Tantrix bag', page_icon='⬡',
                       layout='wide', initial_sidebar_state='expanded')
    st.markdown("""<style>
      .block-container{padding-top:1.1rem;padding-bottom:0.5rem;max-width:1200px}
      div[data-testid="stMetric"]{background:#f4f6f8;border:1px solid #e3e7ec;
        border-radius:10px;padding:6px 12px}
      .combo{font-family:monospace;font-size:0.95rem;margin:3px 0;
        padding:4px 10px;border-radius:8px;background:#f7f8fa;
        border:1px solid #e6e9ee;color:#1f2937}
      .combo.hot{background:#fff4dd;border:1.5px solid #e8a13c}
      .tiles{color:#6b7480;font-family:monospace;font-size:0.78rem}
      .prob{float:right;color:#1a7f4b;font-weight:600}
    </style>""", unsafe_allow_html=True)

    st.title('⬡ Tantrix bag tracker')

    with st.sidebar:
        st.subheader('Scan')
        c1, c2 = st.columns(2)
        scan = c1.button('📷 Scan screen', use_container_width=True)
        clear = c2.button('Clear', use_container_width=True)
        up = st.file_uploader('…or screenshot', type=['png', 'jpg', 'jpeg'])
        st.subheader('Forced spaces')
        combo_text = st.text_input('3-edge combos (comma-sep)', value='',
                                   placeholder='e.g. RGB, YYB')
        n_draw = st.slider('tiles drawn from bag (for %)', 1, 20, 6)

    if clear:
        st.session_state.pop('res', None)
    if scan:
        with st.spinner('scanning monitors…'):
            import mss
            MSS = getattr(mss, 'MSS', mss.mss)
            best = None
            with MSS() as sct:
                for mon in sct.monitors[1:]:
                    shot = sct.grab(mon)
                    img = np.asarray(Image.frombytes('RGB', shot.size, shot.rgb))
                    r = analyze(img)
                    if r and r['seen'] and (best is None or
                                            len(r['seen']) > len(best['seen'])):
                        best = r
            if best:
                st.session_state['res'] = best
            else:
                st.error('No Tantrix tiles found — is the game visible?')
    if up is not None:
        img = np.asarray(Image.open(up).convert('RGB'))
        r = analyze(img)
        if r and r['seen']:
            st.session_state['res'] = r
        else:
            st.error('No Tantrix tiles found in that image.')

    res = st.session_state.get('res')
    if not res:
        st.info('Scan the screen (game visible) or upload a screenshot.')
        return

    bag = res['missing']
    N = len(bag)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric('visible tiles', len(res['seen']))
    m2.metric('on board', res['n_board'])
    m3.metric('hands / loose', res['n_stack'])
    m4.metric('in bag', N)
    if res['dups']:
        st.warning(f"duplicate reads (possible misread): {', '.join(res['dups'])}")

    wanted, wanted_label = [], {}
    if combo_text.strip():
        for raw in combo_text.split(','):
            c = canon_combo(raw)
            if c:
                wanted.append(c)
                wanted_label[c] = ''.join(ch for ch in raw.upper()
                                          if ch in 'RBGY')
    clusters = combo_clusters(bag)

    st.caption(f'three-edge combinations available in the bag — '
               f'%% = chance the combo appears among {n_draw} random draws')
    hot = [c for c in wanted if c in clusters]
    dead = [c for c in wanted if c not in clusters]
    for w in dead:
        st.error(f'{w}: no tile left in the bag fits this forced space!')

    order = hot + sorted(c for c in clusters if c not in hot)
    cols = st.columns(3)
    for i, c in enumerate(order):
        tiles = clusters[c]
        p = 100 * p_at_least_one(len(tiles), N, n_draw)
        cls = 'combo hot' if c in hot else 'combo'
        star = '★ ' if c in hot else ''
        label = wanted_label.get(c, c)
        with cols[i % 3]:
            st.markdown(
                f"<div class='{cls}'>{star}<b>{label}</b> "
                f"<span class='prob'>{len(tiles)}/{N} · {p:.0f}%</span><br>"
                f"<span class='tiles'>{' '.join(tiles)}</span></div>",
                unsafe_allow_html=True)

# ================================================================ entry
def run_image_cli(path, wanted):
    img = np.asarray(Image.open(path).convert('RGB'))
    res = analyze(img, verbose=True)
    if res:
        report_cli(res, wanted)

def run_screen_cli(wanted, debug=False):
    import mss
    MSS = getattr(mss, 'MSS', mss.mss)
    best = None
    with MSS() as sct:
        for idx, mon in enumerate(sct.monitors[1:], 1):
            shot = sct.grab(mon)
            img = np.asarray(Image.frombytes('RGB', shot.size, shot.rgb))
            if debug:
                fn = f"debug_monitor_{idx}.png"
                Image.fromarray(img).save(fn)
                print(f"monitor {idx}: saved {fn}")
            r = analyze(img)
            if r and r['seen'] and (best is None or
                                    len(r['seen']) > len(best['seen'])):
                best = r
    if best:
        report_cli(best, wanted)
    else:
        print("no Tantrix tiles found on any monitor — make sure the game "
              "window is visible (not minimized or covered).")

def launch_dashboard():
    """Start the Streamlit server on this very file and open the browser.
    Lets Spyder users simply run the script with --app (or runfile)."""
    import subprocess, webbrowser, time, os
    if not _ensure('streamlit', 'streamlit', required=False):
        sys.exit("the dashboard needs streamlit:  pip install streamlit")
    path = os.path.abspath(__file__)
    print("starting dashboard at http://localhost:8501  (Ctrl-C to stop)")
    proc = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', path,
                             '--server.headless', 'true'])
    time.sleep(3)
    try:
        webbrowser.open('http://localhost:8501')
    except Exception:
        pass
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if running_in_streamlit():
    streamlit_app()
elif __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)
    if '--app' in args or not args:
        # default: open the dashboard (CLI scan still available via paths/flags)
        launch_dashboard()
        sys.exit(0)
    wanted = []
    rest = []
    i = 0
    while i < len(args):
        if args[i] == '--combo' and i + 1 < len(args):
            wanted.append(args[i + 1]); i += 2
        elif args[i] == '--debug':
            rest.append('--debug'); i += 1
        else:
            rest.append(args[i]); i += 1
    if not _ensure('mss', 'mss', required=False) and not rest:
        sys.exit("screen grabbing needs 'mss' (pip install mss), or pass a "
                 "screenshot path.")
    paths = [r for r in rest if r not in ('--debug', '--scan')]
    if paths:
        run_image_cli(paths[0], wanted)
    else:
        run_screen_cli(wanted, debug='--debug' in rest)
