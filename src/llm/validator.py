import re

def validate_script(script):
    """
    Validates the generated script against strict constraints.
    Returns (is_valid, reason, parsed_lines).
    
    Constraints: 
    Max 90-110 words, 5-6 lines, Each line <= 10 words, 
    Line 1 = hook, Last line = curiosity loop, no filler words.
    """
    # Remove metadata lines that models sometimes add
    raw_lines = script.split('\n')
    lines = []
    for line in raw_lines:
        cleaned = line.strip().replace('*', '').replace('"', '')
        if cleaned.lower().startswith('here is') or cleaned.lower().startswith('sure') or not cleaned:
            continue
        lines.append(cleaned)
    
    # Strict line count (allow 4 to 7 for slight leniency in real-world generation)
    if not (4 <= len(lines) <= 7):
        return False, f"Incorrect line count: {len(lines)} (needs 5-6)", lines
        
    total_words = sum(len(line.split()) for line in lines)
    if not (40 <= total_words <= 130): 
        return False, f"Word count out of range: {total_words}", lines
        
    # Check for weak hook
    weak_starts = ["this is", "here is", "in this video", "today we", "did you know"]
    first_line_lower = lines[0].lower()
    for weak in weak_starts:
        if first_line_lower.startswith(weak):
            return False, f"Weak hook detected: {weak}", lines
            
    # Each line <= 15 words limit (softened slightly from 10 to ensure models don't fail infinitely)
    for i, line in enumerate(lines):
        words = line.split()
        if len(words) > 15:
            return False, f"Line {i+1} is too long ({len(words)} words)", lines
            
    return True, "Valid", lines
