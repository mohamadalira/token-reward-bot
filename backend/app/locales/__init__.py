from typing import Any, Dict, Optional

from app.locales import fa


class I18n:
    def __init__(self, locale: str = "fa"):
        self.locale = locale
        self._catalogs: Dict[str, Dict[str, str]] = {"fa": fa.MESSAGES}

    def t(self, key: str, **kwargs: Any) -> str:
        catalog = self._catalogs.get(self.locale, fa.MESSAGES)
        template = catalog.get(key, key)
        if kwargs:
            return template.format(**kwargs)
        return template


_i18n: Optional[I18n] = None


def get_i18n(locale: str = "fa") -> I18n:
    global _i18n
    if _i18n is None or _i18n.locale != locale:
        _i18n = I18n(locale)
    return _i18n
