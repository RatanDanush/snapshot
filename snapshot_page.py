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

    # ── Mode selector ─────────────────────────────────────────────────────────
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

    # ── India 10Y manual input ─────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:9px;font-weight:700;color:#3a3a3a;'
        'letter-spacing:.12em;padding-bottom:6px;border-top:1px solid #181818;'
        'border-bottom:1px solid #181818;margin:10px 0 8px;">INDIA 10Y G-SEC (MANUAL)</div>',
        unsafe_allow_html=True
    )
    col_r1, col_r2 = st.columns([2, 5])
    with col_r1:
        india_10y_input = st.text_input(
            "India 10Y yield (%)",
            placeholder="e.g. 6.85",
            help="Yahoo Finance no longer provides this ticker reliably. "
                 "Paste today's 10Y G-Sec yield from CCIL / NDS-OM / RBI.",
            label_visibility="collapsed"
        )
    with col_r2:
        st.markdown(
            '<div style="font-size:10px;color:#5a6a80;padding:8px 0 0;">'
            '📌 Enter India 10Y G-Sec yield — Yahoo Finance no longer provides this ticker. '
            'Source: <a href="https://www.ccil.org.in" target="_blank" style="color:#1a5fa8;">CCIL</a> · '
            '<a href="https://www.rbi.org.in" target="_blank" style="color:#1a5fa8;">RBI</a>'
            '</div>', unsafe_allow_html=True
        )
    india_10y_manual = None
    if india_10y_input:
        try:
            india_10y_manual = float(india_10y_input.strip())
        except ValueError:
            st.warning("India 10Y value must be a number, e.g. 6.85", icon="⚠️")

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
        from data_fetcher import get_weekly_data, get_daily_data
        from macro_generator import (
            generate_snapshot_commentary,
            get_weekly_stories, get_week_ahead, get_daily_stories
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
            data = get_weekly_data(india_10y_manual=india_10y_manual) if mode == "weekly" else get_daily_data(india_10y_manual=india_10y_manual)
            n_ok = len([v for v in data.values() if v != "N/A"])
            st.write(f"✅ Market data ready — {n_ok} data points ({round(time.time()-t1, 1)}s)")
        except Exception as e:
            st.error(f"❌ Market data fetch failed: {e}")
            return

        # ── Step 2: Commentary ─────────────────────────────────────────────────
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
    st.caption("Scroll within the preview · Use the buttons below to download")

    # Inject html2canvas so users can save as JPEG directly from the preview
    jpeg_fname = (f"stanc_weekly_w{data.get('week_num','')}_{data.get('year','')}.jpg"
                  if mode == "weekly"
                  else f"stanc_daily_{datetime.now().strftime('%Y%m%d')}.jpg")
    preview_html = html + f"""
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"
  integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA=="
  crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<style>
#_jbtn{{position:fixed;bottom:14px;right:14px;z-index:99999;
  background:#002060;color:#c8a84b;border:2px solid #c8a84b;
  padding:7px 14px;font-family:Arial,sans-serif;font-size:11px;font-weight:700;
  cursor:pointer;border-radius:3px;letter-spacing:.08em;box-shadow:0 2px 8px rgba(0,0,0,.35);}}
#_jbtn:hover{{background:#c8a84b;color:#002060;}}
#_jsta{{position:fixed;bottom:52px;right:14px;z-index:99999;
  font-family:Arial,sans-serif;font-size:10px;color:#002060;display:none;
  background:#fff;padding:3px 8px;border-radius:2px;border:1px solid #c8a84b;}}
</style>
<button id="_jbtn" onclick="_dlJpeg()">⬇ JPEG</button>
<div id="_jsta">Rendering…</div>
<script>
function _dlJpeg(){{
  var btn=document.getElementById('_jbtn'),sta=document.getElementById('_jsta');
  btn.style.display='none'; sta.style.display='block';
  var el=document.querySelector('.wrap')||document.body;
  html2canvas(el,{{scale:2,backgroundColor:'#ffffff',useCORS:true,logging:false}})
  .then(function(c){{
    var a=document.createElement('a');
    a.download='{jpeg_fname}';
    a.href=c.toDataURL('image/jpeg',0.93);
    a.click();
    btn.style.display='block'; sta.style.display='none';
  }}).catch(function(){{
    btn.style.display='block'; sta.style.display='none';
    alert('JPEG render failed — use HTML download instead.');
  }});
}}
</script>"""
    components.html(preview_html, height=680, scrolling=True)

    # ── Download buttons ──────────────────────────────────────────────────────
    st.markdown("---")
    fname = (f"stanc_weekly_w{data.get('week_num','')}_{data.get('year','')}.html"
             if mode == "weekly"
             else f"stanc_daily_{datetime.now().strftime('%Y%m%d')}.html")

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            label="⬇️  Download HTML",
            data=html.encode("utf-8"),
            file_name=fname,
            mime="text/html",
            use_container_width=True,
            type="primary"
        )
    with dl_col2:
        st.markdown(
            '<div style="background:#f0f4fa;border:1px solid #c8a84b;border-radius:4px;'
            'padding:7px 14px;font-size:11px;color:#002060;font-weight:700;text-align:center;">'
            '📷 JPEG — click <b>⬇ JPEG</b> button inside the preview above'
            '</div>', unsafe_allow_html=True
        )

    st.markdown(
        '<div class="snap-warn">'
        '⚑ HTML: Download → open in browser → paste into Outlook (Insert HTML) or Gmail. &nbsp;'
        '⚑ JPEG: Click ⬇ JPEG in the preview → attach to email or save for sharing.'
        '</div>', unsafe_allow_html=True
    )
