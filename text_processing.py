import re
from datetime import datetime

# Common abbreviations and expansions
ABBREVIATIONS = {
    r'\bst\.': 'street',
    r'\bdr\.': 'doctor',
    r'\bprof\.': 'professor',
    r'\bmr\.': 'mister',
    r'\bms\.': 'miss',
    r'\bmrs\.': 'misses',
    r'\bet al\.': 'and others',
    r'\bvs\.': 'versus',
    r'\betc\.': 'and so on',
    r'\busd': 'US dollars',
    r'\busd': 'US dollars',
}

ACRONYMS = {
    'usa': 'United States',
    'us': 'United States',
    'uk': 'United Kingdom',
    'gps': 'GPS',
    'atm': 'ATM',
    'fbi': 'FBI',
    'nps': 'National Park Service',
    'epa': 'EPA',
    'covid': 'COVID',
    'nfl': 'NFL',
    'nba': 'NBA',
    'nhl': 'NHL',
    'mlb': 'MLB',
}

COMMON_STT_ERRORS = {
    r'\btwo\s+hundred\b': '200',
    r'\bone\s+thousand\b': '1000',
    r'\bwhat\'s': "what's",
    r'\bit\'s': "it's",
    r'\bi\'m': "i'm",
    r'\byou\'re': "you're",
    r'\bdon\'t': "don't",
    r'\bcan\'t': "can't",
    r'\bwon\'t': "won't",
}

CASUAL_FILLERS = [
    "you know,",
    "I mean,",
    "basically,",
    "like,",
    "so,",
    "honestly,",
    "right?",
    "yeah,",
]

ROBOTIC_PATTERNS = {
    r'(?i)\b(according to|based on|it is evident that)\b': 'so',
    r'(?i)\b(furthermore|additionally)\b': 'also',
    r'(?i)\b(nevertheless|however)\b': 'but',
    r'(?i)\b(accordingly)\b': 'so',
    r'(?i)\b(consequently)\b': 'that means',
}

def normalize_user_input(text: str) -> str:
    """Normalize STT output to make it LLM-friendly"""
    if not text:
        return text
    
    # Convert to lowercase for processing
    text = text.lower().strip()
    
    # Fix common STT errors
    for pattern, replacement in COMMON_STT_ERRORS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Expand abbreviations
    for pattern, replacement in ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Expand acronyms
    for acronym, expansion in ACRONYMS.items():
        text = re.sub(r'\b' + acronym + r'\b', expansion, text, flags=re.IGNORECASE)
    
    # Fix number formatting
    text = re.sub(r'(\d+)\s+and\s+(\d+)', r'\1.\2', text)  # "3 and 5" → "3.5"
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Capitalize first letter
    text = text[0].upper() + text[1:] if text else text
    
    return text

def humanize_response(text: str) -> str:
    """Make LLM output sound more human and casual"""
    if not text:
        return text
    
    # Replace robotic phrasing
    for pattern, replacement in ROBOTIC_PATTERNS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Add contractions
    text = re.sub(r'\bdo not\b', "don't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bcan not\b', "can't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bwill not\b', "won't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bis not\b', "isn't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bare not\b', "aren't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bwould not\b', "wouldn't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bcould not\b', "couldn't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bhave not\b', "haven't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bhas not\b', "hasn't", text, flags=re.IGNORECASE)
    text = re.sub(r'\bit is\b', "it's", text, flags=re.IGNORECASE)
    text = re.sub(r'\byou are\b', "you're", text, flags=re.IGNORECASE)
    text = re.sub(r'\bi am\b', "i'm", text, flags=re.IGNORECASE)
    
    # Break up long sentences
    sentences = text.split('. ')
    if len(sentences) > 1 and any(len(s) > 100 for s in sentences):
        processed_sentences = []
        for sentence in sentences:
            if len(sentence) > 100:
                # Split long sentences at commas
                parts = sentence.split(', ')
                if len(parts) > 1:
                    processed_sentences.extend([p + '.' for p in parts[:-1]])
                    processed_sentences.append(parts[-1] + '.')
                else:
                    processed_sentences.append(sentence + '.')
            else:
                processed_sentences.append(sentence + '.')
        text = ' '.join(processed_sentences).strip()
    
    # Add occasional casual filler words (but not too many)
    sentences = text.split('. ')
    if len(sentences) > 1 and len(sentences[0]) > 20:
        import random
        if random.random() < 0.3:  # 30% chance
            filler = random.choice(CASUAL_FILLERS)
            sentences[0] = filler + ' ' + sentences[0].lower()
        text = '. '.join(sentences)
    
    # Remove "I would say" type phrases
    text = re.sub(r'(?i)\bi would say\s+', '', text)
    text = re.sub(r'(?i)\bi would suggest\s+', '', text)
    text = re.sub(r'(?i)\bin my opinion\s+', '', text)
    
    # Add "really" or "quite" for emphasis on adjectives (subtle)
    text = re.sub(r'\b(beautiful|amazing|awesome|great|nice)\b', r'really \1', text, flags=re.IGNORECASE)
    
    # Remove redundant words
    text = re.sub(r'\b(very\s+very|really\s+really)\b', 'really', text, flags=re.IGNORECASE)
    
    # Fix capitalization for "I"
    text = re.sub(r'\bi\b', 'I', text)
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Ensure proper punctuation
    if text and text[-1] not in '.!?':
        text += '.'
    
    return text

def verbalize_entities(text: str) -> str:
    """Convert technical entities to human-readable format"""
    # Convert coordinates
    text = re.sub(
        r'(\d+\.?\d*)[°\s]*([NSns])\s*(\d+\.?\d*)[°\s]*([EWew])',
        lambda m: f"{m.group(1)}° {m.group(2).upper()}, {m.group(3)}° {m.group(4).upper()}",
        text
    )
    
    # Convert times
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', lambda m: format_time(m.group(1), m.group(2)), text)
    
    # Convert dates
    text = re.sub(
        r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
        lambda m: format_date(m.group(1), m.group(2), m.group(3)),
        text
    )
    
    return text

def format_time(hour: str, minute: str) -> str:
    """Convert 24-hour time to 12-hour format with AM/PM"""
    try:
        h = int(hour)
        m = int(minute)
        period = 'AM' if h < 12 else 'PM'
        if h > 12:
            h -= 12
        elif h == 0:
            h = 12
        return f"{h}:{m:02d} {period}"
    except:
        return f"{hour}:{minute}"

def format_date(day: str, month: str, year: str) -> str:
    """Convert date format to readable format"""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        m = int(month)
        if 1 <= m <= 12:
            return f"{months[m-1]} {day}, {year}"
    except:
        pass
    return f"{day}/{month}/{year}"

# Example usage for testing
if __name__ == "__main__":
    # Test normalization
    stt_output = "what's the weather in the usa?"
    normalized = normalize_user_input(stt_output)
    print(f"STT: {stt_output}")
    print(f"Normalized: {normalized}\n")
    
    # Test humanization
    robotic = "Based on the available information, it is evident that the weather conditions are quite favorable. Furthermore, you should bring adequate water supplies."
    humanized = humanize_response(robotic)
    print(f"Robotic: {robotic}")
    print(f"Humanized: {humanized}")
