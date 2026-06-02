import pytest
from app.repositories.settings_repo import DEFAULT_SETTINGS


def test_default_settings_exist():
    required = [
        "bot_mode",
        "referral_reward",
        "token_price_usd",
        "min_campaign_tokens",
        "max_campaign_tokens",
        "min_reward_per_join",
        "max_reward_per_join",
    ]
    for key in required:
        assert key in DEFAULT_SETTINGS
