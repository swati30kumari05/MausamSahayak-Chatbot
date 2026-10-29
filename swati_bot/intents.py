"""Keyword and pattern intent detection for English, Hindi, and Hinglish (Swati's Bot).

Identifies farmer intent from conversational text queries and detects language.
"""
import re

KEYWORDS = {
    "unsubscribe": [
        "unsubscribe", "stop alerts", "stop alert", "अलर्ट बंद", "सूचना बंद", "alert band", "band karo"
    ],
    "subscribe": [
        "subscribe", "alert me", "notify me", "notify", "अलर्ट चालू", "सूचना चालू", "alert chalu", "alerts on"
    ],
    "forecast": [
        "forecast", "weather forecast", "kal ka mausam", "kal baarish", "kal barish", "tomorrow",
        "पूर्वानुमान", "मौसम पूर्वानुमान", "कल का मौसम", "कल बारिश होगी", "बारिश कब होगी",
        "barish kab hogi", "baarish kab hogi", "kab hogi barish", "kab hogi baarish",
        "agla mausam", "aage ka mausam", "two days weather"
    ],
    "sensors": [
        "sensor", "sensors", "khet ka haal", "khet ki sthiti", "field condition", "field data",
        "मेरे खेत का हाल", "खेत का हाल", "खेत की स्थिति", "सेंसर", "sensor readings",
        "khet ka haal batao", "mere khet", "soil moisture", "mitti ki nami"
    ],
    "flood": [
        "flood", "baadh", "badh", "bāṛh", "बाढ़", "बाढ", "river", "water level", "nadi",
        "नदी", "जलस्तर", "पानी बढ़", "evacuat", "relocat", "drowning", "jalstar"
    ],
    "heat": [
        "heat", "hot", "garmi", "loo", "गर्मी", "लू", "heatwave", "heat wave", "tapish", "dhoop"
    ],
    "crop": [
        "crop", "crops", "sow", "grow", "plant", "farming", "fasal", "fasl", "kheti", "kaunsi fasal",
        "फसल", "फ़सल", "खेती", "बुवाई", "बोना", "फसल सलाह", "crop advice", "crop recommendation"
    ],
    "weather": [
        "weather", "temperature", "temp", "humidity", "rain", "mausam", "barish", "baarish", "tapman",
        "मौसम", "तापमान", "बारिश", "बरसात", "नमी", "aaj ka mausam", "आज का मौसम", "live weather", "now"
    ],
    "location": [
        "location", "my location", "set location", "change location", "स्थान", "लोकेशन", "जगह", "share location"
    ],
    "language": [
        "language", "bhasha", "भाषा", "change language", "hindi", "english", "हिंदी", "अंग्रेजी"
    ],
    "menu": [
        "menu", "main menu", "मेनू", "मुख्य मेनू", "options", "soochi"
    ],
    "help": [
        "help", "मदद", "सहायता", "madad", "sahayata", "guide"
    ],
    "greeting": [
        "hi", "hello", "hey", "namaste", "namaskar", "नमस्ते", "नमस्कार", "pranam", "प्रणाम", "ram ram", "राम राम"
    ],
}

# Specific order of precedence to prevent broad intents from overshadowing specific ones
ORDER = [
    "unsubscribe",
    "subscribe",
    "forecast",
    "sensors",
    "flood",
    "heat",
    "crop",
    "weather",
    "location",
    "language",
    "menu",
    "help",
    "greeting"
]

DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")
HINGLISH_WORDS = {"kaisa", "kaisi", "kaise", "hogi", "hoga", "aaj", "kal", "batao", "mera", "meri", "kya", "khet", "haal", "pani", "garmi", "fasal", "baarish", "barish"}


def detect_intent(text: str) -> str | None:
    """Detect farmer's query intent from free text using phrases and token matching."""
    s = (text or "").lower().strip()
    if not s:
        return None

    words = set(re.findall(r"[\w\u0900-\u097F]+", s))

    for intent in ORDER:
        for kw in KEYWORDS[intent]:
            kw_clean = kw.lower().strip()
            # If the keyword contains multiple words, match as substring in cleaned text
            if " " in kw_clean:
                if kw_clean in s:
                    return intent
            # Single word: match in parsed tokens or substring if word length > 3
            elif kw_clean in words or (len(kw_clean) > 3 and kw_clean in s):
                return intent

    return None


def detect_language(text: str) -> str:
    """Detect whether query was typed in Hindi/Hinglish or English. Defaults to 'en'."""
    s = (text or "").lower().strip()
    if not s:
        return "en"

    # Contains Devanagari script -> Hindi
    if DEVANAGARI_REGEX.search(s):
        return "hi"

    # Contains common Hinglish conversational terms
    tokens = set(re.findall(r"[a-z]+", s))
    if tokens & HINGLISH_WORDS:
        return "hi"

    return "en"
