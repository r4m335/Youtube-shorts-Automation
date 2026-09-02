import logging
from .providers import PROVIDERS
from .validator import validate_script
from .cache import get_cached_script, save_script_to_cache

PROMPT_TEMPLATE = """
Write a highly engaging YouTube Shorts script about: "{topic}"

Background Context (Use strictly to prevent hallucinations):
"{context}"

Constraints:
- Between 4 to 12 lines of text. It is completely OK if the script is shorter than 12 lines. DO NOT make up information just to fill space.
- Write entirely in conversational, spoken language. Sound like an energetic YouTuber talking directly to the camera.
- Use natural speech patterns: contractions (I'm, they've, we'll), shorter sentences, and punchy delivery. Avoid formal, written-only English.
- Each line should be under 18 words
- Line 1 MUST be a strong hook. (Do not use "This is", "Here is", "Today we", "Did you know")
- Middle lines MUST deliver the news update clearly for target fans without over-explaining basic domain background.
- EXTREME FACT-CHECK RULE: You MUST rely ONLY on the facts explicitly mentioned in the Background Context. DO NOT use your pre-trained knowledge to guess what team a player plays for, who won a match, or who scored. If the context doesn't explicitly name a player or their team, DO NOT name them. Do not hallucinate outdated rosters, fake transfers, or unverified claims.
- Last line MUST be a curiosity loop or call to action.
- Total words must be between 40 to 250 words.
- NO metadata, NO asterisks, NO quotes, just the script lines.
"""

def generate_script_for_topic(topic, context=""):
    cached, topic_hash = get_cached_script(topic)
    if cached:
        logging.info(f"Using cached script for topic: {topic[:30]}...")
        return cached.split("\n"), topic_hash

    prompt = PROMPT_TEMPLATE.format(topic=topic, context=context)
    
    for provider_name, provider_func in PROVIDERS:
        logging.info(f"Attempting to generate script with {provider_name}...")
        
        encountered_api_error = False
        # 3 Retries per provider
        for attempt in range(3):
            try:
                raw_script = provider_func(prompt)
                is_valid, reason, parsed_lines = validate_script(raw_script)
                
                if is_valid:
                    logging.info(f"Successfully generated valid script with {provider_name}.")
                    save_script_to_cache(topic_hash, parsed_lines)
                    return parsed_lines, topic_hash
                else:
                    logging.warning(f"{provider_name} attempt {attempt+1} failed validation: {reason}")
            except Exception as e:
                logging.error(f"{provider_name} attempt {attempt+1} failed with error: {e}")
                encountered_api_error = True
                import time
                time.sleep(15)
                
        if not encountered_api_error:
            logging.error(f"Topic rejected because {provider_name} failed validation 3 times. Skipping fallback models.")
            return None, None
                
    logging.error(f"Failed to generate a valid script for topic: {topic} after all providers and retries.")
    return None, None


REFINE_PROMPT_TEMPLATE = """
You are a master YouTube Shorts script doctor and viral editor.

Topic: "{topic}"

Background Context (Strict Fact-Check Source):
"{context}"

Original Script:
\"\"\"
{script_text}
\"\"\"

The script editor rejected this script for the following reason:
"{feedback_reason}"

Please rewrite and refine the script to address the feedback completely while making it engaging and clear for target fans.

Constraints:
- Between 4 to 12 lines of text. Do NOT make up information just to fill space.
- Write entirely in conversational, spoken language. Sound like an energetic YouTuber talking directly to the camera.
- Use natural speech patterns: contractions (I'm, they've, we'll), shorter sentences, and punchy delivery. Avoid formal, written-only English.
- Each line should be under 18 words
- Line 1 MUST be a compelling hook
- Middle lines MUST deliver the main news clearly
- EXTREME FACT-CHECK RULE: You MUST rely ONLY on the facts explicitly mentioned in the Background Context. DO NOT use your pre-trained knowledge to guess what team a player plays for, who won a match, or who scored. If the context doesn't explicitly name a player or their team, DO NOT name them. Do not hallucinate outdated rosters, fake transfers, or unverified claims.
- Last line MUST be a curiosity loop or call to action
- Maintain a cohesive narrative flow when spoken aloud
- CRITICAL: Output ONLY the script lines. Do NOT write "Here is the rewritten script" or any intro/outro commentary.
- NO metadata, NO asterisks, NO quotes, NO line labels (e.g. Line 1:)
"""


def refine_script_with_feedback(topic, lines, feedback_reason, context=""):
    """
    Attempts to rewrite/refine a rejected script using the LLM based on specific feedback.
    Returns parsed_lines if successful, or None if refinement fails.
    """
    script_text = "\n".join(lines)
    prompt = REFINE_PROMPT_TEMPLATE.format(
        topic=topic, context=context, script_text=script_text, feedback_reason=feedback_reason
    )

    for provider_name, provider_func in PROVIDERS:
        logging.info(f"Attempting script refinement with {provider_name}...")
        
        encountered_api_error = False
        for attempt in range(2):
            try:
                raw_script = provider_func(prompt)
                is_valid, reason, parsed_lines = validate_script(raw_script)
                if is_valid:
                    logging.info(f"Successfully refined script with {provider_name}.")
                    return parsed_lines
                else:
                    logging.warning(f"{provider_name} refinement attempt {attempt+1} failed validation: {reason}")
            except Exception as e:
                logging.error(f"{provider_name} refinement attempt {attempt+1} failed with error: {e}")
                encountered_api_error = True
                import time
                time.sleep(15)
                
        if not encountered_api_error:
            logging.error(f"Refinement rejected because {provider_name} failed validation repeatedly. Skipping fallbacks.")
            return None

    return None

