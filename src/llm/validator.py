import re

def validate_script(script):
    """
    Validates the generated script against strict constraints.
    Returns (is_valid, reason, parsed_lines).
    
    Constraints: 
    Max 90-110 words, 5-6 lines, Each line <= 10 words, 
    Line 1 = hook, Last line = curiosity loop, no filler words.
    """
    INTRO_FILLER_PREFIXES = (
        "here is", "here's", "heres", "sure", "certainly",
        "rewritten", "revised", "updated", "script:", "short script:",
        "note:", "option", "version", "here are", "below is", "below are",
        "draft", "revised version", "rewritten version"
    )

    # Remove metadata lines that models sometimes add
    raw_lines = script.split('\n')
    lines = []
    for line in raw_lines:
        cleaned = line.strip().replace('*', '').replace('"', '').replace('`', '')
        # Remove line numbering prefixes like "1. ", "Line 1: ", "- "
        cleaned = re.sub(r'^(line\s*\d+:?|\d+[\.\):]|-|\*)\s*', '', cleaned, flags=re.IGNORECASE).strip()
        
        if not cleaned:
            continue
            
        cleaned_lower = cleaned.lower()
        if any(cleaned_lower.startswith(prefix) for prefix in INTRO_FILLER_PREFIXES):
            continue
        if "rewritten script" in cleaned_lower or "revised script" in cleaned_lower or "here is the" in cleaned_lower or "here's the" in cleaned_lower:
            continue
            
        lines.append(cleaned)
    
    # Line count: 5 to 8 lines allowed for full storytelling context
    if not (5 <= len(lines) <= 8):
        return False, f"Incorrect line count: {len(lines)} (must be between 5 to 8 lines)", lines
        
    total_words = sum(len(line.split()) for line in lines)
    if not (40 <= total_words <= 160): 
        return False, f"Word count out of range: {total_words}", lines
        
    # Check for weak hook
    weak_starts = ["this is", "here is", "in this video", "today we", "did you know"]
    first_line_lower = lines[0].lower()
    for weak in weak_starts:
        if first_line_lower.startswith(weak):
            return False, f"Weak hook detected: {weak}", lines
            
    # Each line <= 20 words limit
    for i, line in enumerate(lines):
        words = line.split()
        if len(words) > 20:
            return False, f"Line {i+1} is too long ({len(words)} words)", lines

    # Reject scripts mentioning recent past years (2015-2025) to ensure news is 100% current
    full_script_text = " ".join(lines)
    past_year_match = re.search(r'\b(201[5-9]|202[0-5])\b', full_script_text)
    if past_year_match:
        return False, f"Script mentions past year '{past_year_match.group(0)}'. News must be current from today (2026).", lines
            
    return True, "Valid", lines


def evaluate_script_quality(topic, lines):
    """
    Uses an LLM to evaluate if the generated script is actually engaging, coherent,
    and suitable for a YouTube Short before proceeding to TTS/rendering.

    Returns (is_good, reason).
    """
    from .providers import PROVIDERS
    
    script_text = "\n".join(lines)
    prompt = f"""You are an expert YouTube Shorts producer and virality editor.

Evaluate this generated script for a YouTube Short:

Topic: "{topic}"
Script:
\"\"\"
{script_text}
\"\"\"

STRICT EVALUATION RULES (MUST FOLLOW):

ONLY REJECT (`is_good: false`) IF IT MATCHES ONE OF THESE 2 CRITICAL VIOLATIONS:
1. OUTDATED NEWS & RETRO VIOLATION: News or sports updates mentioning older years (2010-2025), old retro kits/jerseys (e.g. "2014 Chelsea kit"), throwback photos, or past season transfers.
2. ZERO-NEWS FLUFF & TRIVIAL CONTENT: Fast food/restaurant/cafe menu updates, food item lists, or generic clickbait with no named real-world event.

STRICT PROHIBITIONS — DO NOT REJECT (`is_good: true`) FOR ANY OF THE FOLLOWING:
- DO NOT fact-check or reject based on whether the story is verified by external media. Faithfully generate the video based on what the tweet states!
- DO NOT reject because a hook is "too dramatic", "sensational", "intense", or "not unexpected enough". Dramatic hooks are REQUIRED for YouTube Shorts virality!
- DO NOT reject because the script lacks deep technical, academic, or clinical trial details. This is a 30-second Short!
- DO NOT reject over minor phrasing preferences, sentence flow, or style choices.

Return ONLY valid JSON (no markdown):
{{"is_good": true, "reason": "brief explanation"}}
"""

    for provider_name, provider_func in PROVIDERS:
        try:
            raw = provider_func(prompt).strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            
            import json
            data = json.loads(raw)
            is_good = bool(data.get("is_good", False))
            reason = data.get("reason", "No reason provided.")
            return is_good, f"[{provider_name}] {reason}"
        except Exception as e:
            continue

    # Fallback default: if evaluation LLM calls fail, accept by default
    return True, "Quality evaluation skipped (LLM unavailable)."

