import logging
from .providers import PROVIDERS
from .validator import validate_script
from .cache import get_cached_script, save_script_to_cache

PROMPT_TEMPLATE = """
Write a highly engaging YouTube Shorts script about: "{topic}"
Constraints:
- Exactly 5 to 6 lines of text
- Each line cannot exceed 10 words
- First line MUST be a strong hook. (Do not use "This is", "Here is", "Today we", "Did you know")
- Last line MUST be a curiosity loop or call to action.
- Total words must be between 90 to 110 words.
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
