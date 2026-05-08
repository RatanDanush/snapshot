# macro_generator.py  v5
# Key fix: _call_best() tries models in preference order at call time,
# automatically skipping any that return 429 (quota=0) or 404 (not found).
# gemini-2.5-flash is now first in the list.
#
# Two-step story pipeline:
#   Step A — search+summarise (prose, grounding citations OK)
#   Step B — structure prose → clean JSON (no search, reliable)

import json, re, time
import google.generativeai as genai

# ── Model preference (newest first, most likely to have quota) ────────────────

MODEL_PREFERENCE = [
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-pro',
    'gemini-1.0-pro',
]

def _search_tool():
    """Return best available search grounding tool for the installed SDK."""
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


def _call_best(api_key, prompt, use_search=False):
    """
    Try each model in MODEL_PREFERENCE order.
    Skips models that return 429 (quota exceeded / limit=0) or 404 (not found).
    Stops on any other error (auth, invalid prompt, etc.).

    Returns (text, model_name_used, elapsed_seconds, error_or_None).
    """
    genai.configure(api_key=api_key)
    tool  = _search_tool() if use_search else None
    tools = [tool] if tool else []

    all_errors = []
    for candidate in MODEL_PREFERENCE:
        try:
            m = genai.GenerativeModel(model_name=candidate, tools=tools)
            t0 = time.time()
            r  = m.generate_content(prompt)
            return r.text, candidate, round(time.time()-t0, 1), None
        except Exception as e:
            err = str(e)
            all_errors.append(f'[{candidate}] {err[:120]}')
            # Only continue to next model for quota / availability errors
            if any(x in err for x in ['429', '404', 'quota', 'limit: 0',
                                       'not found', 'not supported', 'RESOURCE_EXHAUSTED']):
                continue
            # Auth errors, malformed prompt, etc. — stop immediately
            break

    return None, None, 0, '\n'.join(all_errors)


# ── JSON extraction ───────────────────────────────────────────────────────────

def extract_json(text):
    if not text: return None
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*',     '', text)
    text = text.strip()
    try: return json.loads(text)
    except Exception: pass
    for sc, ec in [('[', ']'), ('{', '}')]:
        s, e = text.find(sc), text.rfind(ec)
        if s != -1 and e != -1:
            try: return json.loads(text[s:e+1])
            except Exception: pass
    return None


# ── Fallback stories ──────────────────────────────────────────────────────────

def fallback_stories(n=3, reason=''):
    body = f'Gemini error: {reason}' if reason else \
           'Macro stories unavailable — add manually before distributing.'
    return [{'tag': 'Data Unavailable',
             'headline': 'Macro stories could not be fetched — add manually',
             'body': body,
             'inr_relevance': '📌 INR: Update this section with relevant macro context.',
             'links': [], 'color': 'blue'}] * n


# ── Two-step helpers ──────────────────────────────────────────────────────────

def _step_a(api_key, search_prompt, fallback_prompt):
    """
    Step A: search+summarise → raw prose.
    Tries with search first; if quota/tool fails, retries without search.
    Returns (prose, source_desc, error_or_None).
    """
    text, model, elapsed, err = _call_best(api_key, search_prompt, use_search=True)
    if not err and text:
        return text, f'{model}+search ({elapsed}s)', None

    search_err = err or 'empty response'

    # Fallback: same model list without search grounding
    text2, model2, elapsed2, err2 = _call_best(api_key, fallback_prompt, use_search=False)
    if not err2 and text2:
        return text2, f'{model2} no-search ({elapsed2}s)', f'Search failed: {search_err}'

    return None, '', f'Search: {search_err} | Plain: {err2}'


def _step_b(api_key, prose, template):
    """
    Step B: prose → structured JSON via plain model call.
    Returns (parsed_obj, error_or_None).
    """
    prompt = template.replace('{{PROSE}}', prose or 'No content available.')
    text, model, elapsed, err = _call_best(api_key, prompt, use_search=False)
    if err:
        return None, f'Step B ({elapsed}s): {err}'
    result = extract_json(text)
    if result is None:
        return None, f'Step B JSON parse failed. Output:\n{(text or "")[:400]}'
    return result, None


# ── Commentary (single call, no search) ──────────────────────────────────────

def generate_snapshot_commentary(api_key, data):
    """
    Theme bar, mood tag, per-section narrative, INR insight, chart events.
    No search — uses market data + model training knowledge.
    Returns (dict, error_or_None).
    """
    mode = data.get('mode', 'weekly')
    def v(k):
        val = data.get(k, 0)
        return val if isinstance(val, (int, float)) else 0

    if mode == 'weekly':
        ctx = (
            f"Week: {data.get('week_start','')} to {data.get('week_end','')} "
            f"(Week {data.get('week_num','')})\n\n"
            f"USD/INR: {data.get('usdinr_close','N/A')}  WoW: {v('usdinr_wow_val'):+.2f}%\n"
            f"  Range: {data.get('usdinr_wk_low','N/A')}–{data.get('usdinr_wk_high','N/A')}  "
            f"Mon open: {data.get('usdinr_open','N/A')}\n"
            f"DXY: {data.get('dxy_close','N/A')}  WoW: {v('dxy_wow_val'):+.2f}%\n"
            f"EUR/INR: {data.get('eurinr_close','N/A')}  WoW: {v('eurinr_wow_val'):+.2f}%\n"
            f"GBP/INR: {data.get('gbpinr_close','N/A')}  WoW: {v('gbpinr_wow_val'):+.2f}%\n"
            f"JPY/INR (per 100): {data.get('jpyinr_close','N/A')}  WoW: {v('jpyinr_wow_val'):+.2f}%\n"
            f"CNH/INR: {data.get('cnhinr_close','N/A')}  WoW: {v('cnhinr_wow_val'):+.2f}%\n"
            f"US 10Y: {data.get('us10y_close','N/A')}%  WoW: {v('us10y_wow_val'):+.1f} bps\n"
            f"India 10Y: {data.get('in10y_close','N/A')}%  WoW: {v('in10y_wow_val'):+.1f} bps\n"
            f"Brent: ${data.get('brent_close','N/A')}  WoW: {v('brent_wow_val'):+.2f}%\n"
            f"Gold INR: {data.get('gold_inr','N/A')}  WoW: {v('gold_wow_val'):+.2f}%\n"
            f"Fed: {data.get('fed_rate','N/A')}  RBI: {data.get('rbi_rate','N/A')}\n"
        )
        prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.

Actual market data for week {data.get('week_num','')} ({data.get('week_start','')}–{data.get('week_end','')}):
{ctx}

Using your knowledge of global macro events during this specific week, write professional
client-facing commentary. Name actual events (central bank meetings, data releases,
geopolitical developments) that explain these price moves. Use only the numbers provided.

Return ONLY a valid JSON object, no markdown fences, no explanation:
{{
  "theme": "Week in one line: 1–2 sentences on 2–3 biggest events with key numbers. End with INR takeaway.",
  "mood_tag": "EXACTLY 2–3 ALL CAPS keywords separated by · Max 3 terms. e.g. FOMC SPLIT · OIL SHOCK · INR PRESSURE",
  "usdinr_sub": "MAX 12 WORDS. Terse. Use · separators. e.g. 'Week hi: 95.28 Wed post-FOMC · Mon open: 94.52'",
  "dxy_sub": "MAX 12 WORDS. e.g. 'GDP miss + oil pullback drove Fri reversal · key vs INR'",
  "eurinr_sub": "MAX 10 WORDS. e.g. 'EUR recovered Fri on GDP miss · INR driver'",
  "gbpinr_sub": "MAX 10 WORDS. Terse. e.g. 'BoE hawkish hold · sterling outperformed all week'",
  "jpyinr_sub": "MAX 10 WORDS. e.g. 'BoJ held 0.75% · safe-haven JPY demand Fri'",
  "cnhinr_sub": "MAX 10 WORDS. e.g. 'CNH stable on PBOC guidance · INR weakness drove move'",
  "us10y_sub": "MAX 12 WORDS. Terse. e.g. 'FOMC hawkish dissents + PCE 4.3% drove surge · partial Fri pullback'",
  "in10y_sub": "MAX 12 WORDS. e.g. 'Oil shock → fiscal concern · FPI demand weak · mkt closed Thu'",
  "fed_sub": "MAX 10 WORDS starting with ■. e.g. '■ On hold · hawkish dissents · hike odds rose 0→9%'",
  "rbi_sub": "MAX 10 WORDS starting with ■. e.g. '■ On hold · neutral stance · next MPC June'",
  "brent_sub": "MAX 12 WORDS. e.g. 'Iran Hormuz at 4% flows (Goldman) · wk hi $126 intraday'",
  "gold_sub": "MAX 8 WORDS. e.g. 'Geopolitical safe-haven + USD weakness · near record'",
  "inr_insight": "2–3 sentences max. Must say whether weakness is USD-driven or broad G3. Name 1-2 India-specific factors. End with 'Watch: [specific trigger] next week.'",
  "chart_callout": "6–9 words: single most important INR chart observation",
  "chart_events": [{{"label":"SHORT NAME","x_idx":1}},{{"label":"SHORT NAME","x_idx":2}}]
}}

chart_events: max 2 events for Mon–Fri INR chart annotation.
x_idx: 0=Mon 1=Tue 2=Wed 3=Thu 4=Fri. Use [] if no single-day event stands out.
Return ONLY valid JSON."""

    else:
        ctx = (
            f"Date: {data.get('date','')}\n"
            f"USD/INR: {data.get('usdinr_close','N/A')}  24h: {v('usdinr_chg_val'):+.2f}%\n"
            f"DXY: {data.get('dxy_close','N/A')}  24h: {v('dxy_chg_val'):+.2f}%\n"
            f"EUR/INR: {data.get('eurinr_close','N/A')}  GBP/INR: {data.get('gbpinr_close','N/A')}\n"
            f"US 10Y: {data.get('us10y_close','N/A')}%  Brent: ${data.get('brent_close','N/A')}\n"
        )
        prompt = f"""You are a senior FX analyst at Standard Chartered's India FM Sales desk.
Daily market data for {data.get('date','')}:
{ctx}
Write commentary referencing actual macro events from today.
Return ONLY valid JSON, no fences:
{{"theme":"1 sentence dominant driver + key number.",
  "mood_tag":"2–3 ALL CAPS keywords separated by ·",
  "usdinr_sub":"1 line: key level and driver",
  "dxy_sub":"1 line: DXY direction and INR relevance",
  "inr_insight":"2 sentences: broad USD or INR-specific? What to watch.",
  "chart_callout":"5–7 words: key observation"}}"""

    text, model, elapsed, err = _call_best(api_key, prompt, use_search=False)
    if err:
        return {}, f'Commentary ({elapsed}s): {err}'
    result = extract_json(text)
    if result and isinstance(result, dict):
        return result, None
    return {}, f'Commentary JSON parse failed ({elapsed}s). Output: {(text or "")[:300]}'


# ── Weekly stories ────────────────────────────────────────────────────────────

def get_weekly_stories(api_key, week_start, week_end, week_num, data=None):
    """Two-step: search+summarise → structure into 3 story cards.
    Returns (list, error_or_None)."""

    search_p = f"""Search Google News and financial sources for the 3 most important macro
events from the week of {week_start} to {week_end} (Week {week_num}) that affected
global FX markets, especially USD/INR and INR vs G3 (EUR, GBP, JPY, CNH).

Focus on: central bank decisions (Fed, RBI, BoE, BoJ, ECB), major data surprises
(GDP, CPI, PCE, jobs, PMI), geopolitical events affecting oil, major risk events.

For EACH of the 3 events write a detailed paragraph covering:
- What exactly happened and the specific date
- Key numbers (rate levels, beats/misses, bps changes)
- Immediate market reaction (FX, bonds, oil)
- Direct impact on USD/INR or INR vs G3"""

    fallback_p = f"""Using your training knowledge, write 3 detailed paragraphs about the
most significant global macro events from the week of {week_start} to {week_end}
(Week {week_num}) that affected India FX markets. Include actual numbers, dates,
central bank actions, and market reactions for each event."""

    prose, source, err = _step_a(api_key, search_p, fallback_p)
    if not prose:
        return fallback_stories(3, reason=err or 'No prose from Step A'), err

    # Build verified data constraints so AI doesn't hallucinate price levels
    verified = ""
    if data:
        verified = f"""
VERIFIED MARKET DATA (do NOT use different price levels in any story):
- USD/INR: {data.get('usdinr_close','N/A')} (week range {data.get('usdinr_wk_low','N/A')}–{data.get('usdinr_wk_high','N/A')})
- DXY: {data.get('dxy_close','N/A')}
- EUR/INR: {data.get('eurinr_close','N/A')}  GBP/INR: {data.get('gbpinr_close','N/A')}
- US 10Y: {data.get('us10y_close','N/A')}%  India 10Y: {data.get('in10y_close','N/A')}%
- Brent: ${data.get('brent_close','N/A')}  Gold INR: {data.get('gold_inr','N/A')}
- Fed Funds: {data.get('fed_rate','N/A')}  RBI Repo: {data.get('rbi_rate','N/A')}
Any USD/INR values in stories must be in the range shown above, not from a different year."""

    struct = f"""You are a senior FX analyst at Standard Chartered.
{verified}
Summary of macro events from {week_start}–{week_end}:

{{{{PROSE}}}}

Convert into exactly 3 story cards as a JSON array. Be specific — include actual
numbers, dates, and central bank names.

Return ONLY a valid JSON array, no markdown fences:
[
  {{
    "tag": "Category · Date  e.g. Central Bank · {week_start[:6]}",
    "headline": "Max 15 words with key numbers",
    "body": "2–3 sentences. Wrap key numbers in <strong> tags.",
    "inr_relevance": "📌 INR: specific impact on USD/INR or INR vs G3 with price levels.",
    "links": [{{"text": "→ Source name", "url": "https://real-url.com"}}],
    "color": "red for central bank/hawkish | amber for geopolitics/oil | blue for macro data"
  }}
]
All 3 must be distinct events."""

    result, struct_err = _step_b(api_key, prose, struct)
    if struct_err:
        return fallback_stories(3, reason=struct_err), struct_err
    if isinstance(result, list) and result:
        # Sanitise placeholder URLs
        import urllib.parse
        for story in result:
            for link in story.get('links', []):
                url = link.get('url', '')
                if not url or 'source.com' in url or url == '#':
                    q = urllib.parse.quote(f"{story.get('headline', '')} {week_start}")
                    link['url'] = f"https://news.google.com/search?q={q}"
        return result[:3], None
    return fallback_stories(3, reason='Structure returned empty'), 'Structure returned empty'


# ── Week ahead ────────────────────────────────────────────────────────────────

def get_week_ahead(api_key, current_week_end):
    """Two-step: search upcoming events → calendar JSON.
    Returns (list, error_or_None)."""

    search_p = f"""Search for the 4–6 most important macro events for the week
AFTER {current_week_end} relevant to India FX markets.
Include: central bank meetings (with rate expectations), major data (GDP, CPI, jobs, PMI),
geopolitical deadlines. For each: exact date, event name, expectation, INR relevance."""

    fallback_p = f"""List 4–6 important macro events for the week after {current_week_end}
relevant to India FX. Include dates, event names, and what to watch for."""

    prose, source, err = _step_a(api_key, search_p, fallback_p)
    if not prose:
        return [], err

    struct = """Convert into a calendar JSON array.

{{PROSE}}

Return ONLY a valid JSON array, no markdown fences:
[{"date":"Day DD e.g. Mon 5","impact":"HIGH or MED",
  "event":"Event name and what to watch","url":"https://source.com"}]

impact=HIGH for central bank meetings and major surprises. impact=MED for routine releases."""

    result, err2 = _step_b(api_key, prose, struct)
    if isinstance(result, list):
        import urllib.parse
        for evt in result:
            url = evt.get('url', '')
            if not url or 'source.com' in url or url == '#':
                q = urllib.parse.quote(evt.get('event', 'macro event week ahead'))
                evt['url'] = f"https://news.google.com/search?q={q}"
        return result[:6], err2
    return [], err2


# ── Daily stories ─────────────────────────────────────────────────────────────

def get_daily_stories(api_key, date_str):
    """Two-step: search today → 2 story cards.
    Returns (list, error_or_None)."""

    search_p = f"""Search for the 2 most important macro events from the last 24 hours
(around {date_str}) that affected global FX and India assets.
Include numbers, market reactions, and source names. Write 2 detailed paragraphs."""

    fallback_p = f"""Describe the 2 most significant macro events on {date_str}
for India FX markets. Include specific numbers and market reactions."""

    prose, source, err = _step_a(api_key, search_p, fallback_p)
    if not prose:
        return fallback_stories(2, reason=err or 'No prose'), err

    struct = f"""Convert into 2 daily story cards.

{{{{PROSE}}}}

Return ONLY a valid JSON array, no markdown fences:
[{{"tag":"Category · {date_str}","headline":"Max 15 words with numbers",
   "body":"2–3 sentences. Key numbers in <strong> tags.",
   "inr_relevance":"📌 INR: specific impact with price level.",
   "links":[{{"text":"→ Source","url":"https://real-url.com"}}],
   "color":"red | amber | blue"}}]"""

    result, err2 = _step_b(api_key, prose, struct)
    if isinstance(result, list) and result:
        return result[:2], err2
    return fallback_stories(2, reason=err2 or 'No result'), err2
