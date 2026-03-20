import random

def generate_metadata(topic, hook_line):
    # Sanitize inputs
    safe_topic = topic.replace('"', '').replace('\n', '')[:30]
    safe_hook = hook_line.replace('"', '').replace('\n', '')[:60]
    
    title_templates = [
        f"{safe_hook} (in 40 seconds)",
        f"The Truth About {safe_topic}",
        f"Why {safe_topic} Will Shock You",
        f"{safe_topic} Explained Fast"
    ]
    
    description_templates = [
        f"Quick breakdown of {safe_topic}. #shorts #{safe_topic.split()[0].lower()} #facts",
        f"Everything you need to know about {safe_topic}. \n\n#shorts #trending #{safe_topic.split()[0].lower()}",
        f"A short explainer on {safe_topic}. Let me know your thoughts below! #shorts #viral",
    ]
    
    title = random.choice(title_templates)
    description = random.choice(description_templates)
    
    tags = ["shorts", "facts", safe_topic.split()[0].lower()]
    
    return title, description, tags
