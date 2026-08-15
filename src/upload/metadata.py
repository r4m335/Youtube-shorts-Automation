import logging

def generate_metadata(topic, hook_line, script_lines=None, source_info=None):
    """
    Generates YouTube video metadata using LLM for viral titles,
    trending hashtags, and SEO-optimized descriptions.
    
    Args:
        topic: The topic string.
        hook_line: The first line of the script (used as fallback title).
        script_lines: Full script lines list (for context-aware title generation).
        source_info: Optional dict with 'author' and 'url' for source attribution.
    """
    title = _generate_llm_title(topic, hook_line)
    description = _generate_llm_description(topic, script_lines or [hook_line])
    tags = _generate_llm_tags(topic)
    
    # Add source attribution if available
    if source_info:
        author = source_info.get("author", "")
        url = source_info.get("url", "")
        if author:
            attribution = f"\n\nSource: @{author} on X"
            if url:
                attribution += f"\n{url}"
            description += attribution
    
    return title, description, tags


def _generate_llm_title(topic, hook_line):
    """Use LLM to generate a viral, click-worthy title. Falls back to hook line."""
    from src.llm.providers import PROVIDERS
    
    prompt = f"""Generate ONE viral YouTube Shorts title for this topic:
Topic: "{topic}"
Hook line: "{hook_line}"

Rules:
- Maximum 70 characters (STRICT — YouTube truncates longer titles)
- Must create curiosity or urgency (use words like: just, officially, finally, breaking, insane, shocking)
- Do NOT use generic templates like "The Truth About..." or "Why X Will Shock You"
- Do NOT add hashtags in the title
- Do NOT use quotes around the title
- Make it specific to THIS news story — not generic
- Output ONLY the title text, nothing else

Examples of GOOD titles:
- Messi Just Signed the BIGGEST Contract in Football History
- Nintendo Finally Revealed the Switch 2 Price
- This Country Just Banned All Social Media

Output ONLY the title:"""

    for provider_name, provider_func in PROVIDERS:
        try:
            raw = provider_func(prompt).strip()
            # Clean up any quotes, newlines, or markdown
            raw = raw.strip('"\'`').split('\n')[0].strip()
            # Remove any hashtags that slipped in
            raw = ' '.join(w for w in raw.split() if not w.startswith('#'))
            
            if 10 <= len(raw) <= 100:
                logging.info(f"LLM title generated ({provider_name}): {raw}")
                return raw[:100]
        except Exception as e:
            logging.warning(f"LLM title generation failed ({provider_name}): {e}")
    
    # Fallback: use hook line
    fallback = hook_line.replace('"', '').replace('\n', '')[:70].strip()
    logging.warning(f"Using fallback title: {fallback}")
    return fallback


def _generate_llm_description(topic, script_lines):
    """Generate an SEO-optimized description with trending hashtags."""
    from src.llm.providers import PROVIDERS
    
    script_text = "\n".join(script_lines) if isinstance(script_lines, list) else script_lines
    
    prompt = f"""Write a YouTube Shorts description for this video:
Topic: "{topic}"
Script summary: "{script_text[:200]}"

Rules:
- 2-3 sentences summarizing the key news/update (SEO-friendly, include topic keywords naturally)
- Add a CTA line: "Follow for daily breaking updates! 🔔"
- End with 5-8 trending hashtags relevant to THIS specific topic (e.g. #PremierLeague #TransferNews not just #shorts #facts)
- Always include #shorts as one of the hashtags
- Total description under 500 characters
- Output ONLY the description text

Output:"""

    for provider_name, provider_func in PROVIDERS:
        try:
            raw = provider_func(prompt).strip()
            raw = raw.strip('"\'`')
            if 30 <= len(raw) <= 800:
                logging.info(f"LLM description generated ({provider_name})")
                return raw[:800]
        except Exception as e:
            logging.warning(f"LLM description generation failed ({provider_name}): {e}")
    
    # Fallback
    safe_topic = topic.replace('"', '')[:50]
    return f"Quick breakdown of {safe_topic}.\n\nFollow for daily breaking updates! 🔔\n\n#shorts #trending #news"


def _generate_llm_tags(topic):
    """Extract relevant tags for the YouTube API tags field."""
    # Basic keyword extraction for API tags (separate from hashtags in description)
    words = topic.split()
    tags = ["shorts"]
    for w in words:
        clean = "".join(c for c in w if c.isalnum())
        if clean and len(clean) > 2 and clean.lower() not in {"the", "and", "for", "with", "about"}:
            tags.append(clean.lower())
    
    # Add common discovery tags
    tags.extend(["trending", "news", "viral", "breaking"])
    return list(dict.fromkeys(tags))[:15]  # Deduplicate, max 15 tags
