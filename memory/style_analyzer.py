"""
Style analyzer – extracts communication metrics from user messages
and incrementally updates the evolving personality profile.
"""

import re
import json
import math
import logging
from pathlib import Path
from typing import List, Dict, Any

from memory.database import get_style_profile, update_style_profile

logger = logging.getLogger(__name__)

PROFILE_JSON_PATH = Path(__file__).parent.parent / "memory" / "personality_profile.json"

# Words that signal direct / assertive communication
DIRECT_WORDS = {
    "must", "should", "need", "want", "will", "do", "don't",
    "now", "immediately", "clearly", "absolutely", "definitely",
}

# Words that signal formal register
FORMAL_WORDS = {
    "furthermore", "therefore", "however", "consequently",
    "regarding", "pursuant", "accordingly", "moreover",
    "henceforth", "notwithstanding",
}

# Words that signal emotional intensity
EMOTIONAL_WORDS = {
    "love", "hate", "amazing", "terrible", "wonderful", "awful",
    "excited", "frustrated", "thrilled", "devastated", "incredible",
    "furious", "ecstatic",
}


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _words(text: str) -> List[str]:
    return re.findall(r"\b[a-zA-Z']+\b", text.lower())


def analyze_text(text: str) -> Dict[str, float]:
    """
    Compute style metrics for a single text sample.

    Returns:
        avg_sentence_length  – mean words per sentence (normalised 0-1, cap at 40)
        directness_score     – 0 (hedged) … 1 (direct)
        formality_score      – 0 (casual) … 1 (formal)
        emotional_intensity  – 0 (neutral) … 1 (emotional)
        vocabulary_richness  – type-token ratio
    """
    sentences = _sentences(text)
    words     = _words(text)

    if not words:
        return _zero_metrics()

    # Average sentence length (normalised)
    if sentences:
        avg_len = sum(len(_words(s)) for s in sentences) / len(sentences)
    else:
        avg_len = len(words)
    norm_len = min(avg_len / 40.0, 1.0)

    word_set = set(words)

    directness  = len(word_set & DIRECT_WORDS)   / max(len(words), 1)
    formality   = len(word_set & FORMAL_WORDS)   / max(len(words), 1)
    emotional   = len(word_set & EMOTIONAL_WORDS) / max(len(words), 1)

    # Cap to realistic ranges
    directness = min(directness * 10, 1.0)
    formality  = min(formality  * 10, 1.0)
    emotional  = min(emotional  * 10, 1.0)

    # Type-token ratio (vocabulary richness)
    ttr = len(word_set) / len(words)

    return {
        "avg_sentence_length": round(norm_len, 4),
        "directness_score":    round(directness, 4),
        "formality_score":     round(formality, 4),
        "emotional_intensity": round(emotional, 4),
        "vocabulary_richness": round(ttr, 4),
    }


def _zero_metrics() -> Dict[str, float]:
    return {k: 0.0 for k in [
        "avg_sentence_length", "directness_score",
        "formality_score", "emotional_intensity", "vocabulary_richness",
    ]}


def _ema(old: float, new: float, alpha: float = 0.15) -> float:
    """Exponential moving average – gives old values more weight."""
    return round(alpha * new + (1 - alpha) * old, 4)


def update_profile_from_message(user_message: str):
    """
    Extract style metrics from a new user message and blend into
    the stored style profile using exponential moving average.
    """
    new_metrics = analyze_text(user_message)
    profile     = get_style_profile()

    merged = {
        "avg_sentence_length": _ema(
            profile.get("avg_sentence_length", 0.5),
            new_metrics["avg_sentence_length"],
        ),
        "directness_score": _ema(
            profile.get("directness_score", 0.5),
            new_metrics["directness_score"],
        ),
        "formality_score": _ema(
            profile.get("formality_score", 0.5),
            new_metrics["formality_score"],
        ),
        "emotional_intensity": _ema(
            profile.get("emotional_intensity", 0.5),
            new_metrics["emotional_intensity"],
        ),
        "vocabulary_richness": _ema(
            profile.get("vocabulary_richness", 0.5),
            new_metrics["vocabulary_richness"],
        ),
    }

    update_style_profile(merged)
    _export_profile_json()
    return merged


def _export_profile_json():
    """Write a human-readable personality profile to disk for inspection."""
    profile = get_style_profile()
    PROFILE_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "version": profile.get("version", 1),
        "last_updated": str(profile.get("last_updated", "")),
        "style_metrics": {
            "avg_sentence_length_normalised": profile.get("avg_sentence_length"),
            "directness_score": profile.get("directness_score"),
            "formality_score": profile.get("formality_score"),
            "emotional_intensity": profile.get("emotional_intensity"),
            "vocabulary_richness": profile.get("vocabulary_richness"),
        },
        "interpretations": {
            "communication_style": _interpret_directness(profile.get("directness_score", 0.5)),
            "register":            _interpret_formality(profile.get("formality_score", 0.5)),
            "emotional_tone":      _interpret_emotional(profile.get("emotional_intensity", 0.5)),
        },
        "preferred_topics":        profile.get("preferred_topics", []),
        "communication_patterns":  profile.get("communication_patterns", {}),
    }

    with open(PROFILE_JSON_PATH, "w") as f:
        json.dump(output, f, indent=2)


def _interpret_directness(score: float) -> str:
    if score > 0.6:  return "Direct and assertive"
    if score > 0.3:  return "Balanced"
    return "Thoughtful / hedged"


def _interpret_formality(score: float) -> str:
    if score > 0.6:  return "Formal"
    if score > 0.3:  return "Semi-formal"
    return "Casual / conversational"


def _interpret_emotional(score: float) -> str:
    if score > 0.6:  return "Emotionally expressive"
    if score > 0.3:  return "Moderately expressive"
    return "Reserved / analytical"


def get_personality_profile() -> dict:
    _export_profile_json()
    with open(PROFILE_JSON_PATH, "r") as f:
        return json.load(f)
