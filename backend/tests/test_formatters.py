import pytest
from app.utils.formatters import format_number, generate_referral_code, to_persian_number


def test_persian_numbers():
    assert to_persian_number("123") == "۱۲۳"
    assert to_persian_number(456, use_persian=False) == "456"


def test_format_number():
    assert format_number(1250, use_persian=True) == "۱,۲۵۰"
    assert format_number(1250, use_persian=False) == "1,250"


def test_referral_code_unique():
    code1 = generate_referral_code(12345)
    code2 = generate_referral_code(67890)
    assert code1 != code2
    assert len(code1) == 10
