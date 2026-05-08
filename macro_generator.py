# macro_generator.py  v3
# Two-step pipeline for stories:
#   Step A — search/summarise: returns prose (grounding citations are fine here)
#   Step B — structure: converts prose → clean JSON (no search, reliable output)
# Commentary stays as a single fast call (no search needed).
# All functions return (result, error_string_or_None) so callers can surface errors.

import json
import re
import time
import google.generativeai as genai


# ── Model helpers ─────────────────────────────────────────────────────────────

def _configure(api_key):
    genai.configure(api_key=api_key)


def _search_tool():
    """Return best available search tool for the installed SDK version."""
    try:
        from google.generativeai import protos
        return protos.Tool(google_search=protos.GoogleSearch())
    except AttributeError:
        pass
    try:
        from google.generativeai import protos
        return protos.Tool(google_search_retrieval=protos.GoogleSearchRetrieval())
    except Exception:
        return None


def _make_model(api_key, use_search=False):
    """
    Create a Gemini model. Tries gemini-1.5-flash first (most widely available).
    Returns (model, model_name, error_or_None).
    """
    _configure(api_key)
    tool = _search_tool() if use_search else None
    tools = [tool] if tool else []

    last_err = 'No candidates tried'
    for candidate in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']:
        try:
            m = genai.GenerativeModel(model_name=candidate, tools=tools)
            return m, candidate, None
        except Exception as e:
            last_err = str(e)

    return None, None, last_err


def _call(model, prompt):
    """
    Run generate_content with timing.
    Returns (text, elapsed_seconds, error_or_None).
    """
    if model is None:
        return None, 0, 'Model is None'
    t0 = time.time()
    try:
        response = model.generate_content(prompt)
        return response.text, round(time.time() - t0, 1), None
    except Exception as e:
        return None, round(time.time() - t0, 1), str(e)


# ── JSON extraction ───────────────────────────────────────────────────────────

def extract_json(text):
    if not text:
        return None
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for s_ch, e_ch in [('[', ']'), ('{', '}')]:
        s, e = text.find(s_ch), text.rfind(e_ch)
        if s != -1 and e != -1:
            try:
                return json.loads(text[s:e+1])
            except Exception:
                pass
    return None


# ── Fallback ──────────────────────────────────────────────────────────────────

def fallback_stories(n=3, reason=''):
    body = f'Gemini API error: {reason}' if reason else \
           'Macro stories unavailable — add manually before distributing.'
    return [{
        'tag': 'Data Unavailable',
        'headline': 'Macro stories could not be fetched — add manually',
        'body': body,
        'inr_relevance': '📌 INR: Update this section with relevant macro context.',
        'links': [],
        'color': 'blue'
    }] * n


# ── Two-step helpers ──────────────────────────────────────────────────────────

def _step_a_search(api_key, search_prompt, fallback_prompt):
    """
    Step A: search + summarise, returns raw prose text.
    If search model fails, falls back to plain model.
    Returns (prose_text, source_description, error_or_None).
    """
    # Try with search first
    model, name, err = _make_model(api_key, use_search=True)
    if not err:
        text, elapsed, call_err = _call(model, search_prompt)
        if not call_err and text:
            return text, f'{name} + search ({elapsed}s)', None
        err = call_err or 'empty response'

    search_fail_reason = err

    # Fallback: plain model with training knowledge
    model2, name2, err2 = _make_model(api_key, use_search=False)
    if err2:
        return None, '', f'Search: {search_fail_reason} | Plain model: {err2}'

    text2, elapsed2, call_err2 = _call(model2, fallback_prompt)
    if call_err2:
        return None, '', f'Search: {search_fail_reason} | Plain call: {call_err2}'

    if text2:
        return text2, f'{name2} no-search fallback ({elapsed2}s)', None

    return None, '', f'Search: {search_fail_reason} | Plain model returned empty'


def _step_b_structure(api_key, prose, structure_prompt_template):
    """
    Step B: convert prose → JSON using a plain model call.
    Returns (parsed_object, error_or_None).
    """
    model, name, err = _make_model(api_key, use_search=False)
    if err:
        return None, f'Structure model init: {err}'

    full_prompt = structure_prompt_template.replace('{{PROSE}}', prose or 'No content available.')
    text, elapsed, call_err = _call(model, full_prompt)

    if call_err:
        return None, f'Structure call ({elapsed}s): {call_err}'

    result = extract_json(text)
    if result is None:
        return None, f'JSON parse failed. First 300 chars of output:\n{(text or "")[:300]}'

    return result, None


# ── Commentary (single call, no search) ──────────────────────────────────────

def generate_snapshot_commentary(api_key, data):
    """
    Generate theme bar, mood tag, per-section narrative, INR insight, chart events.
    Uses market data + model training knowledge. No search.
    Returns (commentary_dict, error_or_None).
    """
    mode = data.get('mode', 'weekly')

    def v(k):
        val = data.get(k, 0)
        return val if isinstance(val, (int, float)) else 0

    if mode == 'weekly':
        ctx = f"""
Week: {data.get('week_start','')} to {data.get('week_end','')} (Week {data.get('week_num','')})

USD/INR close: {data.get('usdinr_close','N/A')}  WoW: {v('usdinr_wow_val'):+.2f}%
  Week range: {data.get('usdinr_wk_low','N/A')} – {data.get('usdinr_wk_high','N/A')}  Mon open: {data.get('usdinr_open','N/A')}
DXY: {data.get('dxy_close','N/A')}  WoW: {v('dxy_wow_val'):+.2f}%
EUR/INR: {data.get('eurinr_close','N/A')}  WoW: {v('eurinr_wow_val'):+.2f}%
GBP/INR: {data.get('gbpinr_close','N/A')}  WoW: {v('gbpinr_wow_val'):+.2f}%
JPY/INR (per 100): {data.get('jpyinr_close','N/A')}  WoW: {v('jpyinr_wow_val'):+.2f}%
CNH/INR: {data.get('cnhinr_close','N/A')}  WoW: {v('cnhinr_wow_val'):+.2f}%
US 10Y: {data.get('us10y_close','N/A')}%  WoW: {v('us10y_wow_val'):+.1f} bps
India 10Y: {data.get('in10y_close','N/A')}%  WoW: {v('in10y_wow_val'):+.1f} bps
Brent: ${data.get('brent_close','N/A')}  WoW: {v('brent_wow_val'):+.2f}%
Gold INR: {data.get('gold_inr','N/A')}  WoW: {v('gold_wow_val'):+.2f}%
Fed Funds: {data.get('fed_rate','N/A')}  RBI Repo: {data.get('rbi_rate','N/A')}
"""
        prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.

Actual market data for week {data.get('week_num','')} ({data.get('week_start','')}–{data.get('week_end','')}):
{ctx}

Using your knowledge of global macro events during this specific week, write professional 
client-facing commentary for each data point. Be specific — name actual events (central bank 
meetings, data releases, geopolitical developments) that explain these price moves.
Use only the numbers provided; do not fabricate prices.

Return ONLY a valid JSON object (no markdown fences):
{{
  "theme": "Week in one line — 1–2 sentences covering the 2–3 biggest market-moving events with key numbers. End with a one-phrase INR takeaway.",
  "mood_tag": "2–4 ALL CAPS keywords separated by · e.g. FOMC HOLD · OIL RALLY · INR PRESSURE",
  "usdinr_sub": "1–2 lines: intraweek peak/trough and the event that drove it",
  "dxy_sub": "1–2 lines: what drove DXY and why it matters for INR",
  "eurinr_sub": "1 line: EUR/INR — EUR story or INR story?",
  "gbpinr_sub": "1 line: GBP/INR driver",
  "jpyinr_sub": "1 line: JPY/INR driver",
  "cnhinr_sub": "1 line: CNH/INR driver",
  "us10y_sub": "1–2 lines: what drove US 10Y yields this week",
  "in10y_sub": "1–2 lines: India yield drivers and fiscal context",
  "fed_sub": "1 line: any Fed meeting, statement or signal this week",
  "rbi_sub": "1 line: any RBI action or guidance this week",
  "brent_sub": "1–2 lines: oil driver and India CAD/INR impact",
  "gold_sub": "1 line: gold driver",
  "inr_insight": "2–3 sentences: Is INR weakness USD-driven or broad G3? Any India-specific pressures? What to watch next week.",
  "chart_callout": "6–9 words: the single most important INR chart observation this week",
  "chart_events": [
    {{"label": "SHORT NAME", "x_idx": 1}},
    {{"label": "SHORT NAME", "x_idx": 2}}
  ]
}}

chart_events: max 2 events for vertical annotation on Mon–Fri chart.
x_idx: 0=Mon 1=Tue 2=Wed 3=Thu 4=Fri. Use [] if no single-day event stands out.
Return ONLY valid JSON. No markdown fences, no explanation."""

    else:
        ctx = f"""
Date: {data.get('date','')}
USD/INR: {data.get('usdinr_close','N/A')}  24h: {v('usdinr_chg_val'):+.2f}%
DXY: {data.get('dxy_close','N/A')}  24h: {v('dxy_chg_val'):+.2f}%
EUR/INR: {data.get('eurinr_close','N/A')}  GBP/INR: {data.get('gbpinr_close','N/A')}
JPY/INR (per 100): {data.get('jpyinr_close','N/A')}  CNH/INR: {data.get('cnhinr_close','N/A')}
US 10Y: {data.get('us10y_close','N/A')}%  India 10Y: {data.get('in10y_close','N/A')}%
Brent: ${data.get('brent_close','N/A')}  Gold: {data.get('gold_inr','N/A')}
"""
        prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.

Daily market data for {data.get('date','')}:
{ctx}

Write professional daily commentary referencing actual macro events or data from today.

Return ONLY valid JSON (no fences):
{{
  "theme": "Today in one line — 1 sentence, dominant driver + key number.",
  "mood_tag": "2–3 ALL CAPS keywords separated by ·",
  "usdinr_sub": "1 line: key level and driver",
  "dxy_sub": "1 line: DXY direction and INR relevance",
  "inr_insight": "2 sentences: broad USD move or INR-specific? What to watch.",
  "chart_callout": "5–7 words: key observation"
}}"""

    model, name, init_err = _make_model(api_key, use_search=False)
    if init_err:
        return {}, f'Commentary model init failed: {init_err}'

    text, elapsed, call_err = _call(model, prompt)
    if call_err:
        return {}, f'Commentary call failed ({elapsed}s): {call_err}'

    result = extract_json(text)
    if result and isinstance(result, dict):
        return result, None

    return {}, f'Commentary JSON parse failed ({elapsed}s). Output: {(text or "")[:200]}'


# ── Weekly stories ────────────────────────────────────────────────────────────

def get_weekly_stories(api_key, week_start, week_end, week_num):
    """
    Two-step: search+summarise → structure into 3 story cards.
    Returns (stories_list, error_or_None).
    """
    search_prompt = f"""Search Google News and financial sources for the 3 most important 
macro events from the week of {week_start} to {week_end} (Week {week_num}) that affected 
global FX markets, especially USD/INR and INR vs G3 currencies.

Focus on: central bank decisions (Fed, RBI, BoE, BoJ, ECB), major economic data surprises 
(GDP, CPI, PCE, jobs, PMI), geopolitical events affecting oil prices, and major risk events.

For each of the 3 events write a detailed paragraph covering:
- Exactly what happened (decision taken, number released, event occurred)
- The specific date it happened
- Key numbers (rate levels, beats/misses, percentage moves, bps changes)
- Immediate market reaction (what happened to FX, bonds, oil)
- Direct impact on USD/INR or INR vs G3

Be specific and factual. Include real numbers and source names."""

    fallback_prompt = f"""Using your training knowledge, write 3 detailed paragraphs about the 
most significant global macro events from the week of {week_start} to {week_end} (Week {week_num}) 
that affected India FX markets. Be specific about central bank actions, data releases, 
and geopolitical events. Include actual numbers, dates, and market reactions."""

    prose, source, prose_err = _step_a_search(api_key, search_prompt, fallback_prompt)

    if not prose:
        return fallback_stories(3, reason=prose_err or 'No content from Step A'), prose_err

    structure_template = f"""You are a senior FX analyst at Standard Chartered.

Here is a summary of macro events from the week of {week_start}–{week_end}:

{{{{PROSE}}}}

Convert this into exactly 3 structured story cards as a JSON array.
Each card must be detailed with specific numbers, dates, and central bank names.

Return ONLY a valid JSON array (no markdown fences, no explanation):
[
  {{
    "tag": "Category · Date  e.g. Central Bank · {week_start[:6]}",
    "headline": "Max 15 words including key numbers",
    "body": "2–3 sentences. Wrap key numbers in <strong> tags. Be specific and factual.",
    "inr_relevance": "📌 INR: 1–2 sentences on the specific impact on USD/INR or INR vs G3. Include price levels.",
    "links": [{{"text": "→ Source name e.g. → Reuters", "url": "https://real-url.com"}}],
    "color": "red for central bank/hawkish | amber for geopolitics/oil/commodities | blue for macro data"
  }}
]

Ensure all 3 cards are distinct events. Use real source URLs where possible."""

    result, struct_err = _step_b_structure(api_key, prose, structure_template)

    if struct_err:
        return fallback_stories(3, reason=struct_err), struct_err

    if isinstance(result, list) and len(result) > 0:
        return result[:3], None

    return fallback_stories(3, reason='Structure returned empty'), 'Structure step returned empty'


# ── Week ahead ────────────────────────────────────────────────────────────────

def get_week_ahead(api_key, current_week_end):
    """
    Two-step: search for upcoming events → structure into calendar JSON.
    Returns (events_list, error_or_None).
    """
    search_prompt = f"""Search for the 4–6 most important macro events and data releases 
for the week AFTER {current_week_end} relevant to India FX markets (USD/INR, G3/INR).

Include: central bank meetings (with rate expectations), major data releases (GDP, CPI, 
jobs, PMI), geopolitical deadlines, or RBI operations.

For each event list: exact date, event name, consensus expectation, and why it matters for INR."""

    fallback_prompt = f"""List 4–6 important macro events for the week after {current_week_end} 
that are relevant to India FX. Include central bank meetings, data releases, and key dates."""

    prose, source, prose_err = _step_a_search(api_key, search_prompt, fallback_prompt)

    if not prose:
        return [], prose_err

    structure_template = """Convert this into a calendar JSON array.

{{PROSE}}

Return ONLY a valid JSON array (no markdown fences):
[
  {
    "date": "Day DD e.g. Mon 5 or Tue 6",
    "impact": "HIGH or MED",
    "event": "Event name and what to watch — be specific about expectations",
    "url": "https://credible-source.com"
  }
]

impact=HIGH for central bank meetings and major data surprises. impact=MED for routine releases."""

    result, err = _step_b_structure(api_key, prose, structure_template)

    if isinstance(result, list):
        return result[:6], err

    return [], err


# ── Daily stories ─────────────────────────────────────────────────────────────

def get_daily_stories(api_key, date_str):
    """
    Two-step: search today's events → structure into 2 story cards.
    Returns (stories_list, error_or_None).
    """
    search_prompt = f"""Search for the 2 most important macro events or data releases 
from the last 24 hours (around {date_str}) that affected global FX markets and India-related assets.

Include specific numbers, times (IST or UTC), market reactions, and source names.
Write 2 detailed paragraphs."""

    fallback_prompt = f"""Describe the 2 most significant macro events on {date_str} 
for India FX markets. Include specific numbers and market reactions."""

    prose, source, prose_err = _step_a_search(api_key, search_prompt, fallback_prompt)

    if not prose:
        return fallback_stories(2, reason=prose_err or 'No content'), prose_err

    structure_template = f"""Convert this into 2 structured daily story cards.

{{{{PROSE}}}}

Return ONLY a valid JSON array (no markdown fences):
[
  {{
    "tag": "Category · {date_str}",
    "headline": "Max 15 words with key numbers",
    "body": "2–3 sentences. Key numbers in <strong> tags.",
    "inr_relevance": "📌 INR: specific impact on USD/INR with price level.",
    "links": [{{"text": "→ Source name", "url": "https://real-url.com"}}],
    "color": "red | amber | blue"
  }}
]"""

    result, err = _step_b_structure(api_key, prose, structure_template)

    if isinstance(result, list) and len(result) > 0:
        return result[:2], err

    return fallback_stories(2, reason=err or 'No result'), err
