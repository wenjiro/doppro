# -*- coding: utf-8 -*-
"""Готовит png, ico и каркас docx до запуска или перед сборкой exe."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from core.paths import assets_dir, icon_path, is_frozen, logo_path, project_root, template_path
from core.template_factory import create_template


def prepare() -> None:
    """Обновляет логотип, иконку и шаблон документа в папке проекта."""
    if is_frozen():
        return
    assets_dir().mkdir(parents=True, exist_ok=True)
    source = _find_logo_source()
    _write_logo_and_icon(source, logo_path(), icon_path())
    template_path().parent.mkdir(parents=True, exist_ok=True)
    create_template(str(template_path()))


def ensure() -> None:
    """Создаёт недостающие файлы при запуске из исходников."""
    if is_frozen():
        return
    if not logo_path().exists() or not icon_path().exists():
        assets_dir().mkdir(parents=True, exist_ok=True)
        _write_logo_and_icon(_find_logo_source(), logo_path(), icon_path())
    if not template_path().exists():
        template_path().parent.mkdir(parents=True, exist_ok=True)
        create_template(str(template_path()))


def _find_logo_source() -> Path:
    root = project_root()
    candidates = [
        logo_path(),
        root / "scKoV.jpg",
        root / "logo.png",
        root / "logo.jpg",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        found = sorted(root.glob(pattern))
        if found:
            return found[0]
    raise FileNotFoundError(
        "Не найден логотип. Положите файл знака в папку проекта (например scKoV.jpg) или в assets/logo.png."
    )


def _write_logo_and_icon(source: Path, png_target: Path, ico_target: Path) -> None:
    image = Image.open(source).convert("RGBA")
    image.load()
    png = image.copy()
    png.thumbnail((512, 512), Image.Resampling.LANCZOS)
    png_target.parent.mkdir(parents=True, exist_ok=True)
    png.save(png_target, "PNG")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    icons: list[Image.Image] = []
    for size in sizes:
        frame = png.copy()
        frame.thumbnail((size, size), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(frame, ((size - frame.width) // 2, (size - frame.height) // 2), frame)
        icons.append(canvas)
    icons[0].save(
        ico_target,
        format="ICO",
        sizes=[(size, size) for size in sizes],
        append_images=icons[1:],
    )
