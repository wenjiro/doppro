# -*- coding: utf-8 -*-
"""Проверка HTTPS.

К системным сертификатам добавляются корневой и выпускающие сертификаты
НУЦ Минцифры. Они нужны GigaChat: его сервер подписан этим центром,
а в Windows их часто нет. Проверка имени сервера и срока сертификата остаётся.
"""

from __future__ import annotations

import ssl

from core.paths import project_root


def app_ssl_context() -> ssl.SSLContext:
    """Контекст, который доверяет системным центрам и сертификатам Минцифры."""
    context = ssl.create_default_context()
    bundle = project_root() / "certs" / "russian_trusted_ca.pem"
    if bundle.is_file():
        context.load_verify_locations(cafile=str(bundle))
    return context
