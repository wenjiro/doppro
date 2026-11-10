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

    frames = _sharp_icon_frames(image)
    # Первый кадр обязан быть самым крупным: иначе Pillow выбрасывает остальные размеры.
    frames[-1].save(
        ico_target,
        format="ICO",
        sizes=[(frame.width, frame.height) for frame in frames],
        append_images=frames[:-1],
    )


_NAVY = (0, 48, 112, 255)
_TEAL = (0, 148, 160, 255)
_ICON_BG = (244, 248, 252, 255)


def _sharp_icon_frames(image: Image.Image) -> list[Image.Image]:
    """Знак без бледного круга и без серой каймы JPEG. На 16–32 px края остаются резкими."""
    mark = _mark_from_logo(image)
    frames: list[Image.Image] = []
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        pad = max(1, round(size * 0.06))
        inner = max(1, size - pad * 2)
        scale = min(inner / mark.width, inner / mark.height)
        width = max(1, round(mark.width * scale))
        height = max(1, round(mark.height * scale))
        resized = mark.resize((width, height), Image.Resampling.LANCZOS)
        # На мелких размерах серая кайма выглядит мыльной. Крупные оставляем сглаженными.
        if size <= 32:
            resized = _snap_mark(resized)
        canvas = Image.new("RGBA", (size, size), _ICON_BG)
        canvas.paste(resized, ((size - width) // 2, (size - height) // 2), resized)
        frames.append(canvas)
    return frames


def _mark_from_logo(image: Image.Image) -> Image.Image:
    source = image.convert("RGB")
    width, height = source.size
    pixels = source.load()
    mark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    output = mark.load()
    min_x, min_y, max_x, max_y = width, height, 0, 0
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            if red < 90 and green > 100 and blue > 110:
                color = _TEAL
            elif red < 70 and blue > 70 and green < 110:
                color = _NAVY
            else:
                continue
            output[x, y] = color
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x <= min_x or max_y <= min_y:
        return image.convert("RGBA")
    return mark.crop((min_x, min_y, max_x + 1, max_y + 1))


def _snap_mark(image: Image.Image) -> Image.Image:
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 128:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            if green > 90 and blue > 90:
                pixels[x, y] = _TEAL
            else:
                pixels[x, y] = _NAVY
    return image
