# macro_generator.py  v2
# Two AI concerns are kept separate:
#   1. generate_snapshot_commentary()  — fast, NO search, uses market data + model knowledge
#   2. get_weekly_stories()            — WITH search grounding for real, sourced news
# Both degrade gracefully to fallbacks.

import json
import re
import google.generativeai as genai

# ── Search tool setup (handles both gemini-2.0 and 1.5 API shapes) ──────────

def _make_search_tool():
    """Return best available search tool, or None."""
    try:
        from google.generativeai import protos
        # gemini-2.0 style
        return protos.Tool(google_search=protos.GoogleSearch())
    except (AttributeError, Exception):
        pass
    try:
        from google.generativeai import protos
        # gemini-1.5 style
        return protos.Tool(google_search_retrieval=protos.GoogleSearchRetrieval())
    except Exception:
        return None


def _search_model(api_key, primary='gemini-2.0-flash', fallback='gemini-1.5-flash'):
    """Configure and return a Gemini model with search grounding."""
    genai.configure(api_key=api_key)
    tool = _make_search_tool()
    tools = [tool] if tool else []
    for name in [primary, fallback]:
        try:
            return genai.GenerativeModel(model_name=name, tools=tools)
        except Exception:
            continue
    return genai.GenerativeModel(model_name=fallback)


def _plain_model(api_key, name='gemini-2.0-flash'):
    """Configure and return a Gemini model WITHOUT search (faster, more reliable)."""
    genai.configure(api_key=api_key)
    for n in [name, 'gemini-1.5-flash']:
        try:
            return genai.GenerativeModel(model_name=n)
        except Exception:
            continue
    return None


# ── JSON extraction helper ────────────────────────────────────────────────────

def extract_json(text):
    """Robustly extract a JSON object or array from text."""
    if not text:
        return None
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try array
    s, e = text.find('['), text.rfind(']')
    if s != -1 and e != -1:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            pass
    # Try object
    s, e = text.find('{'), text.rfind('}')
    if s != -1 and e != -1:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            pass
    return None


# ── Fallback data ─────────────────────────────────────────────────────────────

def fallback_stories(n=3):
    return [{
        "tag": "Data Unavailable",
        "headline": "Macro stories could not be fetched — add manually",
        "body": "The AI call did not return usable results. "
                "Please add the week's key macro events manually before distributing.",
        "inr_relevance": "📌 INR: Update this section with relevant macro context.",
        "links": [],
        "color": "blue"
    }] * n


def fallback_commentary():
    """Return an empty commentary dict — HTML will use programmatic fallbacks."""
    return {}


# ── CORE: Snapshot commentary (no search — fast, reliable) ───────────────────

def generate_snapshot_commentary(api_key, data):
    """
    Generate per-section commentary for the snapshot using market data + model knowledge.
    Does NOT use Google Search — fast and reliable.
    Returns a dict with keys: theme, mood_tag, *_sub fields, inr_insight,
    chart_callout, chart_events.
    """
    mode = data.get('mode', 'weekly')

    # Build a compact numerical context string
    def _v(k, default='N/A'):
        return data.get(k, default)

    if mode == 'weekly':
        ctx = f"""
Week: {_v('week_start')} to {_v('week_end')} (Week {_v('week_num')})

USD/INR close: {_v('usdinr_close')}  WoW: {_v('usdinr_wow_val',0):+.2f}%
  Week range: {_v('usdinr_wk_low')} – {_v('usdinr_wk_high')}  Mon open: {_v('usdinr_open')}
DXY: {_v('dxy_close')}  WoW: {_v('dxy_wow_val',0):+.2f}%
EUR/INR: {_v('eurinr_close')}  WoW: {_v('eurinr_wow_val',0):+.2f}%
GBP/INR: {_v('gbpinr_close')}  WoW: {_v('gbpinr_wow_val',0):+.2f}%
JPY/INR (per 100): {_v('jpyinr_close')}  WoW: {_v('jpyinr_wow_val',0):+.2f}%
CNH/INR: {_v('cnhinr_close')}  WoW: {_v('cnhinr_wow_val',0):+.2f}%
US 10Y: {_v('us10y_close')}%  WoW: {_v('us10y_wow_val',0):+.1f} bps
India 10Y: {_v('in10y_close')}%  WoW: {_v('in10y_wow_val',0):+.1f} bps
Brent: ${_v('brent_close')}  WoW: {_v('brent_wow_val',0):+.2f}%
Gold INR: {_v('gold_inr')}  WoW: {_v('gold_wow_val',0):+.2f}%
Fed Funds: {_v('fed_rate')}
RBI Repo: {_v('rbi_rate')}
India-US yield spread: {_v('yield_spread')}
"""
        prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.

Below is factual market data for the week. Use your knowledge of global macro events during this exact week to write concise, professional, client-facing commentary. Be specific — name actual events (central bank decisions, data prints, geopolitical developments) that drove these price moves. Do NOT fabricate numbers. Use the numbers I give you.

{ctx}

Return ONLY a valid JSON object with exactly these keys:

{{
  "theme": "Week in one line — 1–2 sentences covering the 2–3 biggest market-moving events with actual numbers. End with a one-phrase INR takeaway.",
  "mood_tag": "2–4 keywords ALL CAPS separated by · summarising the dominant market tone. E.g. FOMC HOLD · OIL RALLY · INR PRESSURE",
  "usdinr_sub": "1–2 short lines: key intraweek levels and the event that drove the high/low",
  "dxy_sub": "1–2 short lines: what drove DXY direction and relevance for INR",
  "eurinr_sub": "1 line: EUR/INR driver — is it a EUR story or INR story?",
  "gbpinr_sub": "1 line: GBP/INR driver",
  "jpyinr_sub": "1 line: JPY/INR driver",
  "cnhinr_sub": "1 line: CNH/INR driver",
  "us10y_sub": "1–2 lines: what drove US 10Y yields this week",
  "in10y_sub": "1–2 lines: India yield drivers and any fiscal or demand context",
  "fed_sub": "1 line: any Fed communication or meeting this week",
  "rbi_sub": "1 line: any RBI action or guidance this week",
  "brent_sub": "1–2 lines: oil price driver and India CAD/INR impact",
  "gold_sub": "1 line: gold driver",
  "inr_insight": "2–3 sentences: the key INR read. Is weakness USD-driven or broad-based vs G3? What India-specific factors are at play? What to watch next week.",
  "chart_callout": "6–9 words: single most important INR chart observation for the week (shown in chart annotation box)",
  "chart_events": [
    {{"label": "SHORT NAME", "x_idx": 1}},
    {{"label": "SHORT NAME", "x_idx": 2}}
  ]
}}

chart_events: max 2 significant events for vertical annotation on the Mon–Fri INR chart.
x_idx: 0=Mon 1=Tue 2=Wed 3=Thu 4=Fri. Use empty array [] if no single-day event stands out.

Return ONLY the JSON. No markdown fences, no preamble."""

    else:  # daily
        ctx = f"""
Date: {_v('date')}
USD/INR: {_v('usdinr_close')}  24h chg: {_v('usdinr_chg_val',0):+.2f}%
DXY: {_v('dxy_close')}  24h chg: {_v('dxy_chg_val',0):+.2f}%
EUR/INR: {_v('eurinr_close')}  GBP/INR: {_v('gbpinr_close')}
JPY/INR: {_v('jpyinr_close')}  CNH/INR: {_v('cnhinr_close')}
US 10Y: {_v('us10y_close')}%  India 10Y: {_v('in10y_close')}%
Brent: ${_v('brent_close')}  Gold: {_v('gold_inr')}
"""
        prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.

Based on this daily market data, write concise commentary for an internal FX snapshot. Name any actual macro events or data releases from today that drove moves.

{ctx}

Return ONLY a valid JSON object:
{{
  "theme": "Today in one line — 1 sentence covering the dominant driver with a key number.",
  "mood_tag": "2–3 keywords ALL CAPS separated by · summarising today's tone",
  "usdinr_sub": "1 line: key level and driver",
  "dxy_sub": "1 line: DXY direction and why",
  "inr_insight": "2 sentences: INR read — broad USD move or INR-specific? What to watch next session.",
  "chart_callout": "5–7 words: single key observation"
}}

Return ONLY the JSON. No markdown."""

    try:
        model = _plain_model(api_key)
        if not model:
            return fallback_commentary()
        response = model.generate_content(prompt)
        result = extract_json(response.text)
        if result and isinstance(result, dict):
            return result
    except Exception as e:
        print(f"[commentary] Error: {e}")

    return fallback_commentary()


# ── Weekly stories (WITH search grounding) ────────────────────────────────────

def get_weekly_stories(api_key, week_start, week_end, week_num):
    """
    Use Gemini with Google Search grounding to find the 3 most important
    macro events of the past week relevant to India FX markets.
    """
    prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.

Use Google Search to identify the 3 most important macro events from the week of {week_start} to {week_end} (Week {week_num}) that affected global FX markets, with particular relevance to USD/INR and INR vs G3 currencies (EUR, GBP, JPY, CNH).

Prioritise: central bank decisions (Fed, RBI, BoE, BoJ, ECB), major economic data surprises (GDP, CPI, PCE, jobs), geopolitical events affecting oil prices, and significant risk-on/risk-off events.

For each story provide:
1. tag: Short category and date (e.g. "Central Bank · {week_start[:6]}", "US Macro · Apr 30")
2. headline: Max 15 words, include key numbers
3. body: 2–3 concise sentences. Wrap key numbers in <strong> tags.
4. inr_relevance: 1–2 sentences starting with "📌 INR:"
5. links: Array of 1–2 objects with "text" (e.g. "→ Reuters") and "url" (real, working URL)
6. color: "red" for central bank/hawkish, "amber" for geopolitics/oil/commodities, "blue" for macro data

Return ONLY a valid JSON array. No markdown, no preamble.

[
  {{
    "tag": "Category · Date",
    "headline": "Headline with numbers",
    "body": "2–3 sentences with <strong>key numbers</strong>.",
    "inr_relevance": "📌 INR: direct impact on USD/INR.",
    "links": [{{"text": "→ Source", "url": "https://real-url.com"}}],
    "color": "red"
  }}
]"""

    for attempt in range(2):
        try:
            model = _search_model(api_key)
            response = model.generate_content(prompt)
            stories = extract_json(response.text)
            if stories and isinstance(stories, list) and len(stories) > 0:
                return stories[:3]
        except Exception as e:
            print(f"[stories] attempt {attempt+1} failed: {e}")

    # Last resort: try without search
    try:
        model = _plain_model(api_key)
        if model:
            response = model.generate_content(prompt)
            stories = extract_json(response.text)
            if stories and isinstance(stories, list):
                return stories[:3]
    except Exception:
        pass

    return fallback_stories(3)


# ── Week ahead (WITH search grounding) ───────────────────────────────────────

def get_week_ahead(api_key, current_week_end):
    """
    Use Gemini to identify key data releases and events for the coming week.
    """
    prompt = f"""You are an FX analyst at Standard Chartered's India FM Sales desk.

The current week just ended on {current_week_end}. Use Google Search to identify the 4–5 most important macro events, data releases, and central bank decisions for the COMING week relevant to India FX (USD/INR, INR vs G3).

Focus on: central bank meetings (Fed, RBI, BoE, BoJ, ECB), major US/India/European data (GDP, CPI, jobs, PMI), geopolitical deadlines.

Return ONLY a valid JSON array:
[
  {{
    "date": "Mon 5",
    "impact": "HIGH",
    "event": "Short description and what to watch for",
    "url": "https://real-working-url.com"
  }}
]

impact must be exactly "HIGH" or "MED". Date format: "Day DD" e.g. "Tue 6". No markdown."""

    try:
        model = _search_model(api_key, primary='gemini-2.0-flash', fallback='gemini-1.5-flash')
        response = model.generate_content(prompt)
        events = extract_json(response.text)
        if events and isinstance(events, list):
            return events[:6]
    except Exception as e:
        print(f"[week_ahead] Error: {e}")

    # Fallback without search
    try:
        model = _plain_model(api_key)
        if model:
            response = model.generate_content(prompt)
            events = extract_json(response.text)
            if events and isinstance(events, list):
                return events[:6]
    except Exception:
        pass

    return []


# ── Daily stories (WITH search grounding) ────────────────────────────────────

def get_daily_stories(api_key, date_str):
    """
    Use Gemini to find 2 key macro events from the last 24 hours.
    """
    prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.

Use Google Search to identify the 2 most important macro events from the last 24 hours (around {date_str}) relevant to India FX (USD/INR and INR vs G3 currencies).

Focus on: central bank statements, major economic data releases, geopolitical events affecting oil, significant FX moves.

Return ONLY a valid JSON array:
[
  {{
    "tag": "Category · {date_str}",
    "headline": "Headline max 15 words with key numbers",
    "body": "2–3 sentences. Key numbers in <strong> tags.",
    "inr_relevance": "📌 INR: direct impact.",
    "links": [{{"text": "→ Source", "url": "https://real-url.com"}}],
    "color": "red | amber | blue"
  }}
]"""

    for attempt in range(2):
        try:
            model = _search_model(api_key, primary='gemini-2.0-flash', fallback='gemini-1.5-flash')
            response = model.generate_content(prompt)
            stories = extract_json(response.text)
            if stories and isinstance(stories, list):
                return stories[:2]
        except Exception as e:
            print(f"[daily_stories] attempt {attempt+1} failed: {e}")

    try:
        model = _plain_model(api_key)
        if model:
            response = model.generate_content(prompt)
            stories = extract_json(response.text)
            if stories and isinstance(stories, list):
                return stories[:2]
    except Exception:
        pass

    return fallback_stories(2)
