"""Mandatory join bypass rules."""

from app.core.config import get_settings


def test_admin_ids_configured():
    settings = get_settings()
    assert isinstance(settings.admin_id_list, list)


def test_force_join_default_off():
    from app.repositories.settings_repo import DEFAULT_SETTINGS

    assert DEFAULT_SETTINGS["force_join_enabled"] == "false"
