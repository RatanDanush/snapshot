# snapshot_page.py  v3
# Surfaces actual API errors in the UI (not silent fallback).
# Shows timing for each step so you can see real AI computation happening.

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import time


def _get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return st.session_state.get("gemini_key", "")


def render_snapshot_tab():

    st.markdown("""
    <style>
    .snap-header{
        background:#000;border-bottom:2px solid #c8a84b;
        padding:8px 12px;display:flex;align-items:center;
        justify-content:space-between;margin-bottom:0;
    }
    .snap-title{font-size:13px;font-weight:700;color:#e8e8e8;letter-spacing:.08em;}
    .snap-sub{font-size:9px;color:#3a3a3a;letter-spacing:.05em;}
    .snap-warn{background:#0a0800;border:1px solid #3a2800;border-radius:3px;
               padding:6px 10px;font-size:10px;color:#c8a84b;margin-top:8px;}
    .err-box{background:#1a0000;border:1px solid #5a1a1a;border-radius:3px;
             padding:6px 10px;font-size:10px;color:#ff8888;margin-top:4px;
             font-family:monospace;white-space:pre-wrap;word-break:break-all;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="snap-header">
      <div>
        <span class="snap-title">📊 FX SNAPSHOT GENERATOR</span>
        <span class="snap-sub">&nbsp;·&nbsp; WEEKLY &amp; DAILY · INDIA FM SALES</span>
      </div>
      <div style="font-size:9px;color:#3a3a3a;font-family:monospace;">
        POWERED BY GEMINI AI + YFINANCE
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── API key ──────────────────────────────────────────────────────────────
    api_key = _get_api_key()

    if not api_key:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        with st.expander("🔑 Gemini API Key required", expanded=True):
            st.caption(
                "Get a free key at [aistudio.google.com](https://aistudio.google.com). "
                "Or add `GEMINI_API_KEY` to `.streamlit/secrets.toml`."
            )
            key_input = st.text_input(
                "Paste Gemini API key", type="password",
                placeholder="AIza...", label_visibility="collapsed"
            )
            if key_input:
                st.session_state["gemini_key"] = key_input
                api_key = key_input
                st.success("Key saved for this session.", icon="✅")
    else:
        st.markdown(
            '<div style="font-size:10px;color:#2e7d32;padding:4px 0;">● Gemini API key loaded</div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Manual Bloomberg / FIMMDA rate override ───────────────────────────────
    with st.expander("📋 Manual FX & Rate Override (Bloomberg / FIMMDA / CCIL)", expanded=False):
        st.caption(
            "Enter rates from Bloomberg / FIMMDA for G3/INR pairs and India 10Y. "
            "Leave **open = 0** to keep yfinance data. Non-zero open+close overrides yfinance."
        )

        st.markdown(
            '<div style="font-size:9px;font-weight:700;color:#3a3a3a;letter-spacing:.1em;'
            'padding:4px 0;">G3 / INR PAIRS — WEEK OPEN &amp; CLOSE</div>',
            unsafe_allow_html=True
        )

        _pairs = [
            ('eurinr',  'EUR / INR'),
            ('gbpinr',  'GBP / INR'),
            ('jpyinr',  'JPY / INR (per 100 JPY)'),
            ('cnhinr',  'CNH / INR'),
        ]

        if 'manual_fx' not in st.session_state:
            st.session_state['manual_fx'] = {}

        cols = st.columns(4)
        for i, (key, label) in enumerate(_pairs):
            with cols[i]:
                st.markdown(f"**{label}**")
                o_val = st.number_input(
                    "Week open", key=f"mfx_{key}_open",
                    min_value=0.0, step=0.01, format="%.4f",
                    value=float(st.session_state['manual_fx'].get(key, {}).get('open') or 0.0),
                    label_visibility="visible"
                )
                c_val = st.number_input(
                    "Week close", key=f"mfx_{key}_close",
                    min_value=0.0, step=0.01, format="%.4f",
                    value=float(st.session_state['manual_fx'].get(key, {}).get('close') or 0.0),
                    label_visibility="visible"
                )
                if o_val > 0 and c_val > 0:
                    pct = (c_val - o_val) / o_val * 100
                    color = "#c0392b" if pct > 0 else "#1a7a1a"
                    st.markdown(
                        f'<div style="font-size:10px;font-weight:700;color:{color};">'
                        f'WoW: {pct:+.2f}%</div>',
                        unsafe_allow_html=True
                    )
                    st.session_state['manual_fx'][key] = {'open': o_val, 'close': c_val}
                else:
                    st.session_state['manual_fx'][key] = {'open': None, 'close': None}

        st.markdown(
            '<div style="font-size:9px;font-weight:700;color:#3a3a3a;letter-spacing:.1em;'
            'padding:6px 0 2px;">INDIA 10Y G-SEC (CCIL / FIMMDA) — WEEK CLOSE &amp; PRIOR CLOSE</div>',
            unsafe_allow_html=True
        )
        c1, c2 = st.columns(2)
        with c1:
            in10y_close_m = st.number_input(
                "India 10Y — week close (%)", key="mx_in10y_close",
                min_value=0.0, max_value=20.0, step=0.01, format="%.2f",
                value=float(st.session_state.get('manual_in10y_close') or 0.0)
            )
            st.session_state['manual_in10y_close'] = in10y_close_m if in10y_close_m > 0 else None
        with c2:
            in10y_prior_m = st.number_input(
                "India 10Y — prior week close (%)", key="mx_in10y_prior",
                min_value=0.0, max_value=20.0, step=0.01, format="%.2f",
                value=float(st.session_state.get('manual_in10y_prior') or 0.0)
            )
            st.session_state['manual_in10y_prior'] = in10y_prior_m if in10y_prior_m > 0 else None

        if in10y_close_m > 0 and in10y_prior_m > 0:
            bps = round((in10y_close_m - in10y_prior_m) * 100, 1)
            color = "#c0392b" if bps > 0 else "#1a7a1a"
            st.markdown(
                f'<div style="font-size:10px;font-weight:700;color:{color};">'
                f'WoW: {bps:+.1f} bps</div>',
                unsafe_allow_html=True
            )

        st.caption("💡 Tip: after filling, click Generate — these values will override yfinance automatically.")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:9px;font-weight:700;color:#3a3a3a;'
        'letter-spacing:.12em;padding-bottom:6px;border-bottom:1px solid #181818;'
        'margin-bottom:10px;">SELECT SNAPSHOT TYPE</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        gen_weekly = st.button(
            "📅 Weekly Snapshot", use_container_width=True, type="primary",
            help="Mon–Fri of last completed week · 2-step AI macro stories"
        )
    with col2:
        gen_daily = st.button(
            "🗓 Daily Snapshot", use_container_width=True,
            help="Last 24h price action · 2-step AI macro stories"
        )
    with col3:
        st.markdown(
            '<div style="font-size:10px;color:#37474f;padding:8px 0;">'
            'Each macro story runs 2 Gemini calls: search → structure. '
            'Expect 20–60s total for a full weekly snapshot.'
            '</div>', unsafe_allow_html=True
        )

    with st.expander("📋 Pipeline details", expanded=False):
        st.markdown("""
| Step | What | Time |
|---|---|---|
| 1 · Market data | yfinance: USD/INR, G3, DXY, yields, Brent, Gold | ~5s |
| 2 · Commentary | Gemini (no search): theme bar + per-pair narrative | ~8s |
| 3A · Story search | Gemini + Google Search: raw news prose | ~15s |
| 3B · Story structure | Gemini (no search): prose → JSON story cards | ~8s |
| 4A · Week-ahead search | Gemini + Google Search: upcoming events | ~10s |
| 4B · Week-ahead structure | Gemini (no search): prose → calendar JSON | ~5s |
| 5 · Build HTML | Combine all into email-ready snapshot | <1s |
        """)
        st.caption("⚠ Fed Funds + RBI Repo are hardcoded — update in `data_fetcher.py` when rates change.")

    # ── Generation ────────────────────────────────────────────────────────────
    if not (gen_weekly or gen_daily):
        return

    if not api_key:
        st.error("Please enter a Gemini API key above.", icon="⚠️")
        return

    mode = "weekly" if gen_weekly else "daily"

    try:
        from data_fetcher import get_weekly_data, get_daily_data, fmt_chg, pct_change, bps_change
        from macro_generator import (
            generate_snapshot_commentary,
            get_weekly_stories, get_week_ahead, get_daily_stories,
            fill_missing_data, generate_pair_sublines
        )
        from html_generator import generate_weekly_html, generate_daily_html
    except ImportError as e:
        st.error(f"Missing module: {e}. Make sure all .py files are in the same folder.", icon="❌")
        return

    errors = []   # collect non-fatal errors to show at end
    t_total = time.time()

    with st.status(f"Generating {mode} snapshot…", expanded=True) as status:

        # ── Step 1: Market data ────────────────────────────────────────────────
        st.write("📡 **Step 1/5** — Fetching market data (Yahoo Finance)…")
        t1 = time.time()
        try:
            data = get_weekly_data() if mode == "weekly" else get_daily_data()
            n_ok = len([v for v in data.values() if v != "N/A"])
            st.write(f"✅ Market data ready — {n_ok} data points ({round(time.time()-t1, 1)}s)")
        except Exception as e:
            st.error(f"❌ Market data fetch failed: {e}")
            return

        # ── Step 1.5: Apply manual overrides + N/A fill ───────────────────────
        # 1a) Apply manual Bloomberg FX rates (overrides yfinance cross-rates)
        _pair_keys = [('eurinr','EUR/INR'), ('gbpinr','GBP/INR'),
                      ('jpyinr','JPY/INR (per 100 JPY)'), ('cnhinr','CNH/INR')]
        manual_fx  = st.session_state.get('manual_fx', {})
        manual_pairs_for_sublines = []

        for key, label in _pair_keys:
            fx = manual_fx.get(key, {})
            o, c = fx.get('open'), fx.get('close')
            if o and c and o > 0 and c > 0:
                pct  = round((c - o) / o * 100, 4)
                data[f'{key}_close']   = round(c, 4)
                data[f'{key}_wow_val'] = pct
                data[f'{key}_wow']     = fmt_chg(pct)
                data[f'{key}_open']    = round(o, 4)
                manual_pairs_for_sublines.append({'label': label, 'open': o, 'close': c, 'pct_chg': pct})

        # 1b) Apply manual India 10Y (overrides yfinance)
        in10y_close_m = st.session_state.get('manual_in10y_close')
        in10y_prior_m = st.session_state.get('manual_in10y_prior')
        if in10y_close_m:
            data['in10y_close'] = round(in10y_close_m, 2)
            if in10y_prior_m:
                bps_v = bps_change(in10y_close_m, in10y_prior_m)
                suffix = 'WoW' if mode == 'weekly' else '24h'
                data['in10y_wow'] = fmt_chg(bps_v, unit='bps') if mode == 'weekly' else fmt_chg(bps_v, unit='bps')
                data['in10y_wow_val'] = bps_v
            # Recalc yield spread
            us_close = data.get('us10y_close')
            if us_close and us_close != 'N/A':
                try:
                    spread = round(float(in10y_close_m) - float(us_close), 2)
                    data['yield_spread'] = f"{spread:.2f}%"
                except Exception:
                    pass

        # 1c) Generate Gemini sub-lines for manually entered pairs
        if manual_pairs_for_sublines:
            st.write(f"✍️ **Step 1.5** — Generating sub-lines for {len(manual_pairs_for_sublines)} manually-entered pairs…")
            week_str = data.get('week_start', '') + '–' + data.get('week_end', data.get('date', ''))
            sublines = generate_pair_sublines(api_key, manual_pairs_for_sublines, week_str)
            for key, label in _pair_keys:
                if label in sublines:
                    data[f'{key}_sub_manual'] = sublines[label]

        # 1d) Detect remaining N/A fields and try Gemini fill
        _critical = ['in10y_close', 'us10y_close', 'brent_close', 'usdinr_close',
                     'eurinr_close', 'gbpinr_close', 'jpyinr_close', 'cnhinr_close',
                     'dxy_close', 'gold_usd']
        na_fields = [f for f in _critical if str(data.get(f, 'N/A')) == 'N/A']

        if na_fields:
            st.write(f"🔍 **Step 1.5** — {len(na_fields)} field(s) are N/A: `{'`, `'.join(na_fields)}`. Asking Gemini…")
            t_fill = time.time()
            date_ctx = data.get('week_end') or data.get('date', 'latest available')
            filled, fill_err = fill_missing_data(api_key, na_fields, date_ctx)
            elapsed_fill = round(time.time() - t_fill, 1)

            gemini_filled, still_na = [], []
            for f in na_fields:
                if f in filled and filled[f] is not None:
                    data[f] = filled[f]
                    gemini_filled.append(f'{f}={filled[f]}')
                else:
                    still_na.append(f)

            if gemini_filled:
                st.write(f"✅ Gemini filled: {', '.join(gemini_filled)} ({elapsed_fill}s)")
            if fill_err:
                st.markdown(f'<div class="err-box">Gemini fill error: {fill_err}</div>',
                            unsafe_allow_html=True)

            # 1e) If still N/A after Gemini — prompt user for manual input
            if still_na:
                st.warning(
                    f"⚠️ {len(still_na)} field(s) still N/A after Gemini: "
                    f"`{'`, `'.join(still_na)}`. Please fill below and click **Generate** again."
                )
                _labels = {
                    'in10y_close':  ('India 10Y G-Sec yield',  '%',    0.01, 20.0),
                    'us10y_close':  ('US 10Y Treasury yield',   '%',    0.01, 20.0),
                    'brent_close':  ('Brent crude',             'USD/bbl', 1.0, 300.0),
                    'usdinr_close': ('USD/INR',                 '',     50.0, 200.0),
                    'eurinr_close': ('EUR/INR',                 '',     50.0, 200.0),
                    'gbpinr_close': ('GBP/INR',                 '',     50.0, 200.0),
                    'jpyinr_close': ('JPY/INR per 100',         '',     30.0, 120.0),
                    'cnhinr_close': ('CNH/INR',                 '',     8.0,  20.0),
                    'dxy_close':    ('DXY Dollar Index',        '',     80.0, 130.0),
                    'gold_usd':     ('Gold USD/oz',             '',     1000.0, 5000.0),
                }
                na_cols = st.columns(min(len(still_na), 4))
                for i, f in enumerate(still_na):
                    meta = _labels.get(f, (f, '', 0.0, 9999.0))
                    lbl  = f'{meta[0]} ({meta[1]})' if meta[1] else meta[0]
                    with na_cols[i % len(na_cols)]:
                        v = st.number_input(
                            lbl, key=f'na_fill_{f}',
                            min_value=float(meta[2]), max_value=float(meta[3]),
                            step=0.01, format="%.4f", value=0.0
                        )
                        if v > 0:
                            st.session_state[f'na_prefill_{f}'] = v

                # Check if user already pre-filled from a previous run
                for f in still_na:
                    prefill = st.session_state.get(f'na_prefill_{f}')
                    if prefill and prefill > 0:
                        data[f] = prefill

                # If any are still 0 / N/A, stop and ask user to fill + regenerate
                truly_missing = [f for f in still_na
                                 if str(data.get(f, 'N/A')) in ('N/A', '0', '')]
                if truly_missing:
                    status.update(
                        label="⏸ Fill missing data above, then click Generate again",
                        state="error", expanded=True
                    )
                    return
        st.write("✍️ **Step 2/5** — Generating commentary (theme bar, per-pair narrative, INR insight)…")
        t2 = time.time()
        commentary, c_err = generate_snapshot_commentary(api_key, data)
        elapsed2 = round(time.time() - t2, 1)
        if c_err:
            st.warning(f"⚠️ Commentary partial/failed ({elapsed2}s)")
            st.markdown(f'<div class="err-box">{c_err}</div>', unsafe_allow_html=True)
            errors.append(f"Commentary: {c_err}")
        else:
            n_fields = len([v for v in commentary.values() if v])
            st.write(f"✅ Commentary ready — {n_fields} narrative fields ({elapsed2}s)")

        # Merge manual Gemini sub-lines into commentary (override AI if manually entered)
        for key, _label in _pair_keys:
            manual_sub = data.get(f'{key}_sub_manual')
            if manual_sub:
                commentary[f'{key.replace("inr","")}inr_sub'] = manual_sub

        # ── Step 3: Macro stories ──────────────────────────────────────────────
        st.write("🔍 **Step 3/5** — Macro stories: **Step 3A** searching for news…")
        t3 = time.time()
        stories, s_err = [], None
        try:
            if mode == "weekly":
                stories, s_err = get_weekly_stories(
                    api_key,
                    data.get("week_start", ""),
                    data.get("week_end", ""),
                    data.get("week_num", ""),
                    data=data  # verified market data prevents hallucinated price levels
                )
            else:
                stories, s_err = get_daily_stories(api_key, data.get("date", ""))
        except Exception as e:
            s_err = str(e)
            stories = []

        elapsed3 = round(time.time() - t3, 1)
        if s_err and any(s.get('tag') == 'Data Unavailable' for s in stories):
            st.warning(f"⚠️ Macro stories degraded ({elapsed3}s) — check error below")
            st.markdown(f'<div class="err-box">{s_err}</div>', unsafe_allow_html=True)
            errors.append(f"Stories: {s_err}")
        else:
            st.write(f"✅ {len(stories)} macro stories ready ({elapsed3}s)")

        # ── Step 4: Week ahead ─────────────────────────────────────────────────
        week_ahead = []
        if mode == "weekly":
            st.write("📆 **Step 4/5** — Week ahead: searching for upcoming events…")
            t4 = time.time()
            try:
                week_ahead, wa_err = get_week_ahead(api_key, data.get("week_end", ""))
            except Exception as e:
                wa_err = str(e)
                week_ahead = []
            elapsed4 = round(time.time() - t4, 1)
            if wa_err:
                st.write(f"⚠️ Week ahead partial ({elapsed4}s)")
                st.markdown(f'<div class="err-box">{wa_err}</div>', unsafe_allow_html=True)
            else:
                st.write(f"✅ {len(week_ahead)} upcoming events identified ({elapsed4}s)")

        # ── Step 5: Build HTML ─────────────────────────────────────────────────
        st.write("🏗 **Step 5/5** — Building HTML snapshot…")
        t5 = time.time()
        try:
            if mode == "weekly":
                html = generate_weekly_html(data, stories, week_ahead, commentary)
            else:
                html = generate_daily_html(data, stories, commentary)
            elapsed5 = round(time.time() - t5, 1)
            total = round(time.time() - t_total, 1)
            st.write(f"✅ HTML ready — {len(html):,} chars ({elapsed5}s) · **Total: {total}s**")
        except Exception as e:
            st.error(f"❌ HTML generation failed: {e}")
            return

        if errors:
            status.update(
                label=f"⚠️ Snapshot ready with {len(errors)} warning(s) — check errors above",
                state="complete", expanded=False
            )
        else:
            status.update(label="✅ Snapshot ready", state="complete", expanded=False)

    # ── Preview ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="font-size:9px;font-weight:700;color:#3a3a3a;'
        'letter-spacing:.12em;padding-bottom:6px;border-bottom:1px solid #181818;'
        'margin-bottom:10px;">PREVIEW</div>', unsafe_allow_html=True
    )
    st.caption("Scroll within the preview · Download to open in browser or paste into Outlook/Gmail")
    components.html(html, height=680, scrolling=True)

    # ── Download ──────────────────────────────────────────────────────────────
    st.markdown("---")
    fname = (f"stanc_weekly_w{data.get('week_num','')}_{data.get('year','')}.html"
             if mode == "weekly"
             else f"stanc_daily_{datetime.now().strftime('%Y%m%d')}.html")

    st.download_button(
        label="⬇️  Download HTML",
        data=html.encode("utf-8"),
        file_name=fname,
        mime="text/html",
        use_container_width=True,
        type="primary"
    )

    st.markdown(
        '<div class="snap-warn">'
        '⚑ Distribute: Download → open in browser to verify → '
        'paste into Outlook (Insert HTML) or Gmail, or attach the .html file.'
        '</div>', unsafe_allow_html=True
    )
