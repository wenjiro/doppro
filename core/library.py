# -*- coding: utf-8 -*-
"""Список программ педагога на этом компьютере.

Ключ нейросети сюда не пишется: в файле только поля программы.
Черновик по-прежнему один и обновляется сам. В список программа попадает по кнопке.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.data_model import ProgramData
from core.paths import user_data_dir

_SECRET_KEYS = {"gemini_api_key", "gigachat_api_key", "deepseek_api_key", "provider"}


class LibraryError(Exception):
    """Понятная причина, почему программу не удалось прочитать или записать."""


@dataclass
class ProgramEntry:
    id: str
    title: str
    direction: str
    updated: str

    @property
    def updated_text(self) -> str:
        try:
            moment = datetime.fromisoformat(self.updated)
        except ValueError:
            return self.updated
        return moment.strftime("%d.%m.%Y %H:%M")


def programs_dir() -> Path:
    folder = user_data_dir() / "programs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_programs(folder: Path | None = None) -> list[ProgramEntry]:
    root = folder or programs_dir()
    entries: list[ProgramEntry] = []
    if not root.is_dir():
        return entries
    for path in root.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            program = payload.get("program", payload)
            if not isinstance(program, dict):
                continue
            entries.append(
                ProgramEntry(
                    id=path.stem,
                    title=(str(program.get("title") or "").strip() or "Без названия"),
                    direction=str(program.get("direction") or "").strip(),
                    updated=str(payload.get("updated") or ""),
                )
            )
        except (OSError, json.JSONDecodeError):
            continue
    entries.sort(key=lambda item: item.updated, reverse=True)
    return entries


def save_program(program: ProgramData, folder: Path | None = None) -> str:
    """Записывает программу. Если она уже из списка, обновляет ту же запись."""
    root = folder or programs_dir()
    root.mkdir(parents=True, exist_ok=True)
    program_id = program.library_id.strip() or uuid.uuid4().hex
    _write(root / f"{program_id}.json", program)
    program.library_id = program_id
    return program_id


def load_program(program_id: str, folder: Path | None = None) -> ProgramData:
    path = (folder or programs_dir()) / f"{program_id}.json"
    if not path.is_file():
        raise LibraryError("Этой программы уже нет в списке.")
    program = _read(path)
    program.library_id = program_id
    return program


def delete_program(program_id: str, folder: Path | None = None) -> None:
    path = (folder or programs_dir()) / f"{program_id}.json"
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise LibraryError("Не удалось удалить программу из списка.") from exc


def duplicate_program(program_id: str, folder: Path | None = None) -> str:
    source = load_program(program_id, folder)
    source.library_id = ""
    title = source.title.strip() or "Без названия"
    source.title = f"{title} — копия"
    return save_program(source, folder)


def export_program(program: ProgramData, path: Path) -> None:
    payload = {"version": 1, "program": program.to_dict()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_program(path: Path, folder: Path | None = None) -> ProgramData:
    if path.stat().st_size > 2_000_000:
        raise LibraryError("Файл слишком большой для программы ДопПро.")
    program = _read(path)
    program.library_id = ""
    save_program(program, folder)
    return program


def _write(path: Path, program: ProgramData) -> None:
    payload = {
        "version": 1,
        "updated": datetime.now().isoformat(timespec="minutes"),
        "program": program.to_dict(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _read(path: Path) -> ProgramData:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LibraryError("Файл программы не читается.") from exc
    if not isinstance(payload, dict):
        raise LibraryError("В файле нет программы ДопПро.")
    if any(key in payload for key in _SECRET_KEYS) and "program" not in payload:
        raise LibraryError("Это файл настроек, а не программа. Ключ импортировать нельзя.")
    raw = payload.get("program", payload)
    if not isinstance(raw, dict) or "title" not in raw and "modules" not in raw:
        raise LibraryError("В файле нет программы ДопПро.")
    return ProgramData.from_dict(raw)
