# snapshot_page.py  v2
# FX Snapshot Generator tab.
# Called from app.py with: render_snapshot_tab()
#
# Pipeline (weekly):
#   1. Fetch market data  (yfinance)
#   2. Generate commentary  (Gemini, no search — fast)
#   3. Generate macro stories  (Gemini + Google Search)
#   4. Generate week-ahead  (Gemini + Google Search)
#   5. Build HTML
#
# Pipeline (daily):
#   1. Fetch market data
#   2. Generate commentary
#   3. Generate daily stories
#   4. Build HTML

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime


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
                "Paste Gemini API key",
                type="password",
                placeholder="AIza...",
                label_visibility="collapsed"
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

    # ── Mode selector ────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:9px;font-weight:700;color:#3a3a3a;'
        'letter-spacing:.12em;padding-bottom:6px;border-bottom:1px solid #181818;'
        'margin-bottom:10px;">SELECT SNAPSHOT TYPE</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        gen_weekly = st.button(
            "📅 Weekly Snapshot",
            use_container_width=True,
            type="primary",
            help="Mon–Fri of last completed week · AI commentary + 3 macro stories"
        )
    with col2:
        gen_daily = st.button(
            "🗓 Daily Snapshot",
            use_container_width=True,
            help="Last 24h price action · AI commentary + 2 macro stories"
        )
    with col3:
        st.markdown(
            '<div style="font-size:10px;color:#37474f;padding:8px 0;">'
            'Weekly: Mon–Fri of most recently completed week · '
            'Daily: last completed trading session'
            '</div>',
            unsafe_allow_html=True
        )

    with st.expander("📋 Data sources & pipeline", expanded=False):
        st.markdown("""
| Step | What happens |
|---|---|
| 1 · Market data | yfinance: USD/INR, G3, DXY, US/India 10Y, Brent, Gold |
| 2 · Commentary | Gemini (no search) — theme bar, per-pair narrative, INR insight |
| 3 · Macro stories | Gemini + Google Search — 3 sourced news stories |
| 4 · Week ahead | Gemini + Google Search — upcoming high-impact events |
| 5 · Build HTML | Combine all into email-ready snapshot |
        """)
        st.caption(
            "⚠ Fed Funds + RBI Repo are hardcoded — "
            "update manually in `data_fetcher.py` when rates change."
        )

    # ── Generation logic ─────────────────────────────────────────────────────
    if gen_weekly or gen_daily:

        if not api_key:
            st.error("Please enter a Gemini API key above.", icon="⚠️")
            return

        mode = "weekly" if gen_weekly else "daily"

        try:
            from data_fetcher import get_weekly_data, get_daily_data
            from macro_generator import (
                generate_snapshot_commentary,
                get_weekly_stories, get_week_ahead, get_daily_stories
            )
            from html_generator import generate_weekly_html, generate_daily_html
        except ImportError as e:
            st.error(
                f"Missing module: {e}. "
                "Make sure all .py files are in the same folder as app.py.",
                icon="❌"
            )
            return

        with st.status(f"Generating {mode} snapshot…", expanded=True) as status:

            # ── Step 1: Market data ──────────────────────────────────────────
            st.write("📡 Fetching market data from Yahoo Finance…")
            try:
                data = get_weekly_data() if mode == "weekly" else get_daily_data()
                n_ok = len([v for v in data.values() if v != "N/A"])
                st.write(f"✅ Market data ready — {n_ok} data points loaded")
            except Exception as e:
                st.error(f"Market data fetch failed: {e}")
                return

            # ── Step 2: AI commentary (no search — fast) ─────────────────────
            st.write("✍️ Generating per-section commentary (theme bar, pair narratives, INR insight)…")
            commentary = {}
            try:
                commentary = generate_snapshot_commentary(api_key, data)
                if commentary:
                    st.write(f"✅ Commentary ready — theme bar + {len(commentary)} sections")
                else:
                    st.write("⚠️ Commentary unavailable — snapshot will use numeric fallbacks")
            except Exception as e:
                st.write(f"⚠️ Commentary skipped ({e}) — numeric fallbacks will be used")

            # ── Step 3: Macro stories (with search) ──────────────────────────
            st.write("🔍 Fetching macro stories via Gemini + Google Search…")
            stories = []
            try:
                if mode == "weekly":
                    stories = get_weekly_stories(
                        api_key,
                        data.get("week_start", ""),
                        data.get("week_end", ""),
                        data.get("week_num", "")
                    )
                else:
                    stories = get_daily_stories(api_key, data.get("date", ""))
                st.write(f"✅ {len(stories)} macro stories generated")
            except Exception as e:
                st.warning(f"Macro stories failed ({e}) — using placeholder.", icon="⚠️")
                stories = []

            # ── Step 4: Week ahead (weekly only) ─────────────────────────────
            week_ahead = []
            if mode == "weekly":
                st.write("📆 Finding week-ahead events…")
                try:
                    week_ahead = get_week_ahead(api_key, data.get("week_end", ""))
                    st.write(f"✅ {len(week_ahead)} upcoming events identified")
                except Exception as e:
                    st.write(f"⚠️ Week-ahead skipped ({e})")

            # ── Step 5: Build HTML ────────────────────────────────────────────
            st.write("🏗 Building HTML snapshot…")
            try:
                if mode == "weekly":
                    html = generate_weekly_html(data, stories, week_ahead, commentary)
                else:
                    html = generate_daily_html(data, stories, commentary)
                st.write(f"✅ HTML ready · {len(html):,} chars")
            except Exception as e:
                st.error(f"HTML generation failed: {e}")
                return

            status.update(label="✅ Snapshot ready", state="complete", expanded=False)

        # ── Preview ──────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown(
            '<div style="font-size:9px;font-weight:700;color:#3a3a3a;'
            'letter-spacing:.12em;padding-bottom:6px;border-bottom:1px solid #181818;'
            'margin-bottom:10px;">PREVIEW</div>',
            unsafe_allow_html=True
        )
        st.caption(
            "Scroll within the preview · Download to open in browser or paste into Outlook/Gmail"
        )
        components.html(html, height=680, scrolling=True)

        # ── Download ──────────────────────────────────────────────────────────
        st.markdown("---")
        if mode == "weekly":
            fname = f"stanc_weekly_w{data.get('week_num','')}_{data.get('year','')}.html"
        else:
            fname = f"stanc_daily_{datetime.now().strftime('%Y%m%d')}.html"

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
            '⚑ How to distribute: Download → open in browser to verify → '
            'paste into Outlook (Insert HTML) or Gmail, or attach the .html file directly.'
            '</div>',
            unsafe_allow_html=True
        )
