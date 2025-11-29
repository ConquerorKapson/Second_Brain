"""
Helpers for metadata extraction and normalization.
For example: language detection, source attribution, timestamps.
"""
from typing import Dict

def normalize_metadata(meta: Dict) -> Dict:
    return meta or {}
