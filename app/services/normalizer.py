import re
from typing import Optional, List

def clean_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return s
    s = re.sub(r"\s+", " ", s).strip()
    return s

def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out
