"""Tests for DB-backed text service."""

from app.locales import fa
from app.services.text_service import TextService


def test_text_keys_from_catalog():
    keys = TextService.text_keys()
    assert "welcome" in keys
    assert "btn_sponsor" in keys
    assert keys == sorted(fa.MESSAGES.keys())
