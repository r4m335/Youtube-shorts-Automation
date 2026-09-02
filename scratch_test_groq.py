import os
from dotenv import load_dotenv
load_dotenv()
from src.llm.providers import generate_groq
import re, json

prompt = """Today's date is: August 17, 2026.
CRITICAL ANTI-DUPLICATION RULE: You MUST NOT generate any topic that covers the same event.
Generate 3 highly engaging, distinct, and currently trending REAL topics:
Category: Top Trending Global News
Return ONLY a valid JSON array of strings containing the 3 absolute latest trending topics. No markdown, no intro.
Example output format:
["Topic 1", "Topic 2", "Topic 3"]"""

try:
    print('Calling Groq...')
    res = generate_groq(prompt)
    print('Raw Result:', repr(res))
    match = re.search(r'\[.*\]', res, re.DOTALL)
    if match:
        extracted = match.group(0)
        print('Regex Match:', repr(extracted))
        parsed = json.loads(extracted)
        print('Parsed successfully:', parsed)
    else:
        print('No regex match found.')
except Exception as e:
    import traceback
    traceback.print_exc()
