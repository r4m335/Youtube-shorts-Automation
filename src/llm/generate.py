import logging
from .providers import PROVIDERS
from .validator import validate_script
from .cache import get_cached_script, save_script_to_cache

PROMPT_TEMPLATE = """
Write a highly engaging YouTube Shorts script about: "{topic}"
Constraints:
- Between 5 to 8 lines of text
- Each line should be under 18 words
- Line 1 MUST be a strong hook. (Do not use "This is", "Here is", "Today we", "Did you know")
- Middle lines MUST deliver the news update clearly for target fans without over-explaining basic domain background.
- CRITICAL FACT-CHECK RULE: Stick 100% strictly to real, verified facts. DO NOT hallucinate fake manager appointments (e.g. NEVER call Xabi Alonso Chelsea coach), fake transfers, or unverified claims.
- Last line MUST be a curiosity loop or call to action.
- Total words must be between 50 to 150 words.
- NO metadata, NO asterisks, NO quotes, just the script lines.
"""

def generate_script_for_topic(topic):
    cached, topic_hash = get_cached_script(topic)
    if cached:
        logging.info(f"Using cached script for topic: {topic[:30]}...")
        return cached.split("\n"), topic_hash

    prompt = PROMPT_TEMPLATE.format(topic=topic)
    
    for provider_name, provider_func in PROVIDERS:
        logging.info(f"Attempting to generate script with {provider_name}...")
        
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
                
    logging.error(f"Failed to generate a valid script for topic: {topic} after all providers and retries.")
    return None, None


REFINE_PROMPT_TEMPLATE = """
You are a master YouTube Shorts script doctor and viral editor.

Topic: "{topic}"

Original Script:
\"\"\"
{script_text}
\"\"\"

The script editor rejected this script for the following reason:
"{feedback_reason}"

Please rewrite and refine the script to address the feedback completely while making it engaging and clear for target fans.

Constraints:
- Between 5 to 8 lines of text
- Each line should be under 18 words
- Line 1 MUST be a compelling hook
- Middle lines MUST deliver the main news clearly without spoonfeeding basic domain background info
- CRITICAL FACT-CHECK RULE: Stick 100% strictly to real, verified facts. DO NOT hallucinate fake manager appointments, fake transfers, or unverified claims.
- Last line MUST be a curiosity loop or call to action
- Maintain a cohesive narrative flow when spoken aloud
- CRITICAL: Output ONLY the script lines. Do NOT write "Here is the rewritten script" or any intro/outro commentary.
- NO metadata, NO asterisks, NO quotes, NO line labels (e.g. Line 1:)
"""


def refine_script_with_feedback(topic, lines, feedback_reason):
    """
    Attempts to rewrite/refine a rejected script using the LLM based on specific feedback.
    Returns parsed_lines if successful, or None if refinement fails.
    """
    script_text = "\n".join(lines)
    prompt = REFINE_PROMPT_TEMPLATE.format(
        topic=topic, script_text=script_text, feedback_reason=feedback_reason
    )

    for provider_name, provider_func in PROVIDERS:
        logging.info(f"Attempting script refinement with {provider_name}...")
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

    return None

