import logging
from .orchestrator import generate_category_topics
from .filter import filter_and_cache_topics

def get_topics():
    """Generates topics dynamically via LLM using random media categories, with robust retries."""
    logging.info("Starting V3 Category Ingestion process.")
    
    for attempt in range(5):
        category, generated_topics = generate_category_topics()
        
        if not generated_topics:
            logging.warning(f"Attempt {attempt+1}: No topics generated for '{category}'. Retrying...")
            continue
            
        valid_topics = filter_and_cache_topics(generated_topics, source=category)
        if valid_topics:
            logging.info(f"Ingestion complete. Found {len(valid_topics)} new valid topics in '{category}'.")
            return category, valid_topics
            
        logging.warning(f"Attempt {attempt+1}: All generated topics in '{category}' were duplicates or invalid. Pivoting...")
        
    logging.error("Failed to find any unique valid topics after 5 attempts across categories.")
    return "Unknown", []
