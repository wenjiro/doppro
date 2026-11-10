# -*- coding: utf-8 -*-
"""Проверка новой версии на GitHub.

Запрос без ключа и без данных программы: только номер последнего выпуска.
Если сети нет или выпуска ещё нет, программа просто продолжает работу.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from core.paths import GITHUB_REPO, GITHUB_RELEASES, VERSION
from core.tls import app_ssl_context


@dataclass
class UpdateReport:
    state: str
    local: str = VERSION
    remote: str = ""
    url: str = GITHUB_RELEASES

    @property
    def newer(self) -> bool:
        return self.state == "newer"


def look_for_update() -> UpdateReport:
    """Сравнивает установленную версию с последним выпуском на GitHub."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DopPro",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12, context=app_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return UpdateReport("missing")
        return UpdateReport("offline")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return UpdateReport("offline")
    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        return UpdateReport("missing")
    page = str(payload.get("html_url") or GITHUB_RELEASES)
    if is_newer(tag, VERSION):
        return UpdateReport("newer", remote=tag.lstrip("vV"), url=page)
    return UpdateReport("current", remote=tag.lstrip("vV"), url=page)


def is_newer(remote: str, local: str) -> bool:
    """True, если номер на GitHub больше установленного."""
    return _numbers(remote) > _numbers(local)


def _numbers(value: str) -> tuple[int, ...]:
    parts = [int(item) for item in re.findall(r"\d+", value)][:3]
    if not parts:
        return (0,)
    return tuple(parts + [0] * (3 - len(parts)))
