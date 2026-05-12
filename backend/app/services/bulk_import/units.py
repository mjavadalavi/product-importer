"""Persian unit-type title to Basalam unit_type id resolver."""
from __future__ import annotations

# Persian title → Basalam unit_type_id (matches VALID_UNIT_TYPE_IDS in payload.py)
UNIT_TYPE_TITLES: dict[str, int] = {
    "مترمربع": 6375,
    "میلی متر": 6374,
    "میلی‌متر": 6374,
    "جلد": 6373,
    "فوت": 6332,
    "اینچ": 6331,
    "سیر": 6330,
    "اصله": 6329,
    "کلاف": 6328,
    "قالب": 6327,
    "شاخه": 6326,
    "بوته": 6325,
    "دست": 6324,
    "بطری": 6323,
    "تخته": 6322,
    "کارتن": 6321,
    "توپ": 6320,
    "بسته": 6319,
    "جفت": 6318,
    "جین": 6317,
    "طاقه": 6316,
    "قواره": 6315,
    "انس": 6314,
    "سی سی": 6313,
    "سی‌سی": 6313,
    "میلی لیتر": 6312,
    "میلی‌لیتر": 6312,
    "لیتر": 6311,
    "تکه": 6310,
    "مثقال": 6309,
    "سانتی متر": 6308,
    "سانتی‌متر": 6308,
    "متر": 6307,
    "گرم": 6306,
    "گرمی": 6306,
    "کیلوگرم": 6305,
    "کیلو": 6305,
    "عددی": 6304,
    "عدد": 6304,
    "رول": 6392,
    "سوت": 6438,
    "قیراط": 6466,
}


def _normalize(value: str) -> str:
    return (
        str(value or "")
        .replace("‌", "")
        .replace("ي", "ی")
        .replace("ك", "ک")
        .strip()
        .lower()
    )


def resolve_unit_type_title(title: str | None) -> int | None:
    """Match a Persian unit title to a Basalam unit_type id, or None."""
    if not title:
        return None
    nt = _normalize(title)
    if not nt:
        return None
    for k, v in UNIT_TYPE_TITLES.items():
        if _normalize(k) == nt:
            return v
    return None
