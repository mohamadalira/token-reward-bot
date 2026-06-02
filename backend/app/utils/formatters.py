from datetime import datetime
from typing import Union

import jdatetime

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ENGLISH_DIGITS = "0123456789"


def to_persian_number(value: Union[int, float, str], use_persian: bool = True) -> str:
    text = str(value)
    if not use_persian:
        return text
    return text.translate(str.maketrans(_ENGLISH_DIGITS, _PERSIAN_DIGITS))


def format_number(value: Union[int, float], use_persian: bool = True) -> str:
    formatted = f"{value:,}"
    if use_persian:
        formatted = formatted.translate(str.maketrans(_ENGLISH_DIGITS, _PERSIAN_DIGITS))
    return formatted


def format_date(dt: datetime, use_jalali: bool = True, use_persian: bool = True) -> str:
    if use_jalali:
        jdt = jdatetime.datetime.fromgregorian(datetime=dt)
        text = jdt.strftime("%Y/%m/%d")
    else:
        text = dt.strftime("%Y/%m/%d")
    if use_persian:
        text = text.translate(str.maketrans(_ENGLISH_DIGITS, _PERSIAN_DIGITS))
    return text


def generate_referral_code(user_id: int) -> str:
    import hashlib
    return hashlib.sha256(f"ref_{user_id}".encode()).hexdigest()[:10]
