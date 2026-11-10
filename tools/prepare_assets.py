# -*- coding: utf-8 -*-
"""Готовит иконку и каркас документа перед сборкой exe."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.assets_prep import prepare


if __name__ == "__main__":
    prepare()
    print("Готово: assets/logo.png, assets/icon.ico, templates/program_template.docx")
