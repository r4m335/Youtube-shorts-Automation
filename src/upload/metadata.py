import random

def generate_metadata(topic, hook_line, source_info=None):
    """
    Generates YouTube video metadata (title, description, tags).
    
    Args:
        topic: The topic string.
        hook_line: The first line of the script (used in title).
        source_info: Optional dict with 'author' and 'url' for source attribution.
    """
    # Sanitize inputs
    safe_topic = topic.replace('"', '').replace('\n', '')[:30].strip()
    safe_hook = hook_line.replace('"', '').replace('\n', '')[:60].strip()
    
    topic_words = safe_topic.split()
    first_word_raw = topic_words[0].lower() if topic_words else "news"
    
    title_templates = [
        f"{safe_hook} (in 40 seconds)",
        f"The Truth About {safe_topic}",
        f"Why {safe_topic} Will Shock You",
        f"{safe_topic} Explained Fast"
    ]
    
    description_templates = [
        f"Quick breakdown of {safe_topic}. #shorts #{first_word_raw} #facts",
        f"Everything you need to know about {safe_topic}. \n\n#shorts #trending #{first_word_raw}",
        f"A short explainer on {safe_topic}. Let me know your thoughts below! #shorts #viral",
    ]
    
    base_title = random.choice(title_templates)
    description = random.choice(description_templates)
    
    # Add source attribution if available
    if source_info:
        author = source_info.get("author", "")
        url = source_info.get("url", "")
        if author:
            attribution = f"\n\nSource: @{author} on X"
            if url:
                attribution += f"\n{url}"
            description += attribution
    
    # Extract appropriate alphanumeric hashtag from topic
    topic_tag = "".join(char for char in first_word_raw if char.isalnum())
    if not topic_tag:
        topic_tag = "news"
        
    tags = ["shorts", "facts", topic_tag]
    
    # Add appropriate hashtags to title and enforce 100 character limit
    title_hashtags = [f"#{topic_tag}", "#shorts", "#facts"]
    title = base_title.strip()
    for tag in title_hashtags:
        if len(title) + len(tag) + 1 <= 100:
            title += f" {tag}"
            
    # Absolute safeguard
    if len(title) > 100:
        title = title[:100].strip()
        
    return title, description, tags
