"""Tests for channel input parsing."""

import pytest

from app.bot.navigation.ui import validate_card_number
from app.utils.channel_resolver import normalize_channel_input, _TME_RE


def test_normalize_at_username():
    assert normalize_channel_input("@mychannel") == "@mychannel"


def test_tme_public_link():
    m = _TME_RE.match("https://t.me/mychannel")
    assert m and m.group(2) == "mychannel"


def test_tme_invite_link():
    m = _TME_RE.match("https://t.me/+AbCdEfGh")
    assert m and m.group(1) == "+AbCdEfGh"


def test_validate_card_16_digits():
    ok, digits = validate_card_number("6037-9977-1234-5678")
    assert ok is True
    assert digits == "6037997712345678"


def test_validate_card_wrong_length():
    ok, msg = validate_card_number("1234")
    assert ok is False
    assert "۱۶" in msg
