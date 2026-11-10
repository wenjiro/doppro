# -*- coding: utf-8 -*-
"""Формулировки и учебный план под конкретную программу.

В запрос не входят фамилия педагога, должность, руководитель и название организации.
Часы плана после ответа модели сводятся к объёму программы. Нормативные номера в текст не пропускаются.
"""

from __future__ import annotations

import json
import re
import uuid
import urllib.error
import urllib.parse
import urllib.request

from core.data_model import ModuleItem, ProgramData
from core.paths import settings_path
from core.planning import largest_remainder
from core.tls import app_ssl_context

# Ключ один на все версии. В запрос уходит та, которую выбрали в «Настройках».
GEMINI_MODELS = (
    ("gemini-3.8-flash", "Gemini 3.8 Flash"),
    ("gemini-3.6-flash", "Gemini 3.6 Flash"),
    ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite"),
)
_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
_FORBIDDEN = re.compile(
    r"(федеральн\w+\s+закон|приказ\s|санпин|сп\s*\d|распоряжен\w+\s+правительств|№\s*\d)",
    re.IGNORECASE,
)
_LAW_ONLY = re.compile(
    r"(федеральн\w+\s+закон|приказ\s|санпин|сп\s*\d|распоряжен\w+\s+правительств)",
    re.IGNORECASE,
)
_EXAMPLE_TOPIC = ("3d", "3д", "аддитив", "blender", "блендер", "prusa", "приса")


class GenerationError(Exception):
    """Понятная педагогу причина, почему формулировки не получены."""


_PROVIDERS = ("gemini", "gigachat", "deepseek")
_KEY_FIELDS = {
    "gemini": "gemini_api_key",
    "gigachat": "gigachat_api_key",
    "deepseek": "deepseek_api_key",
}


def load_settings() -> dict:
    """Ключи лежат только в настройках компьютера, не в черновике программы."""
    found = {field: "" for field in _KEY_FIELDS.values()}
    found["provider"] = "gemini"
    found["gemini_model"] = GEMINI_MODELS[0][0]
    path = settings_path()
    if not path.exists():
        return found
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return found
    if not isinstance(payload, dict):
        return found
    provider = str(payload.get("provider") or "gemini")
    found["provider"] = provider if provider in _PROVIDERS else "gemini"
    found["gemini_model"] = _known_gemini_model(payload.get("gemini_model"))
    for field in _KEY_FIELDS.values():
        found[field] = str(payload.get(field) or "").strip()
    return found


def save_settings(settings: dict) -> None:
    payload = {"provider": settings.get("provider") if settings.get("provider") in _PROVIDERS else "gemini"}
    payload["gemini_model"] = _known_gemini_model(settings.get("gemini_model"))
    for field in _KEY_FIELDS.values():
        payload[field] = str(settings.get(field) or "").strip()
    path = settings_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _known_gemini_model(value) -> str:
    chosen = str(value or "")
    allowed = {item[0] for item in GEMINI_MODELS}
    return chosen if chosen in allowed else GEMINI_MODELS[0][0]


def current_credentials() -> tuple[str, str]:
    settings = load_settings()
    provider = settings["provider"]
    return provider, settings[_KEY_FIELDS[provider]]


def anonymous_brief(program: ProgramData) -> dict:
    """Карточка для запроса. Персональных данных педагога здесь нет."""
    return {
        "title": program.title.strip(),
        "direction": program.direction,
        "level": program.level,
        "age_from": program.age_from,
        "age_to": program.age_to,
        "city": program.city.strip(),
        "region": program.region.strip(),
        "total_hours": program.total_hours,
        "hours_per_week": program.hours_per_week,
        "lesson_hours": program.lesson_hours,
        "years": program.years,
        "professional_trials": program.professional_trials,
        "regional_project": program.regional_project,
        "final_project": program.final_project,
        "software": program.software.strip(),
        "subjects": program.subjects.strip(),
        "professions": program.professions.strip(),
        "group_min": program.group_min,
        "group_max": program.group_max,
        "no_prior_training": program.no_prior_training,
        "differentiate": program.differentiate,
        "study_form": program.study_form.strip(),
        "modules": [
            {"name": item.name.strip(), "theory": item.theory, "practice": item.practice}
            for item in program.modules
        ],
    }


def generate_sections(program: ProgramData) -> dict:
    """Запрашивает тексты и возвращает словарь для ProgramData.generated."""
    brief = anonymous_brief(program)
    if not brief["title"] or not brief["modules"]:
        raise GenerationError("Сначала заполните название и разделы. Без них формулировать нечего.")
    payload = _complete(_prompt(brief))
    return parse_sections(payload, len(brief["modules"]))


def generate_plan(program: ProgramData) -> list[ModuleItem]:
    """Просит названия разделов по теме программы и сам выравнивает часы под общий объём."""
    if not program.title.strip():
        raise GenerationError("Сначала укажите название программы на шаге «Паспорт».")
    if program.total_hours < 8:
        raise GenerationError("Сначала укажите общий объём часов на шаге «Обучающиеся».")
    brief = plan_brief(program)
    payload = _complete(_plan_prompt(brief))
    return parse_plan(payload, program.total_hours)


def generate_equipment(program: ProgramData) -> dict[str, str]:
    """Просит оборудование, программы и роли проб по названию. Организацию и педагога не отправляет."""
    if not program.title.strip():
        raise GenerationError("Сначала укажите название программы на шаге «Паспорт».")
    payload = _complete(_equipment_prompt(equipment_brief(program)))
    return parse_equipment(payload, program.title)


def parse_sections(raw: str, module_count: int) -> dict:
    """Проверяет ответ модели и выкидывает выдуманные номера документов."""
    data = _load_json(raw)
    result = {
        "relevance": _paragraphs(data.get("relevance"), 2, 4),
        "novelty": _paragraphs(data.get("novelty"), 2, 4),
        "distinctive": _paragraphs(data.get("distinctive"), 3, 6),
        "expediency": _paragraphs(data.get("expediency"), 1, 3),
        "goal": _goal_text(data.get("goal") or data.get("goal_note")),
        "tasks": _paragraphs(data.get("tasks"), 3, 6),
        "method": _one(data.get("method")),
        "subject": _paragraphs(data.get("subject"), 3, 6),
        "addressee": _paragraphs(data.get("addressee"), 1, 3),
        "developing": _paragraphs(data.get("developing"), 2, 5),
        "educating": _paragraphs(data.get("educating"), 2, 5),
        "modules": _modules(data.get("modules"), module_count),
        "literature": _sources(data.get("literature")),
    }
    if not result["relevance"] or not result["novelty"]:
        raise GenerationError("Ответ сервиса пустой или не про эту программу. Повторите запрос.")
    if not result["goal"]:
        raise GenerationError("Сервис не сформулировал цель программы. Повторите запрос.")
    return result


def _prompt(brief: dict) -> str:
    return (
        "Ты составляешь фрагменты дополнительной общеобразовательной общеразвивающей программы на русском языке. "
        "Пиши просто, как методист, без канцелярита и без рекламных слов. "
        "Текст должен быть про ЭТУ программу: опирайся на название и на названия разделов. "
        "Не пиши общий очерк обо всей направленности, если из названия видна конкретная тема. "
        "Не упоминай фамилию педагога и название организации: их нет во входных данных. "
        "Не указывай номера законов, приказов, СанПиН, СП и распоряжений. "
        "Не меняй часы разделов и не придумывай даты. "
        "Верни только JSON без пояснений со схемой: "
        '{"relevance":["абзац","абзац"],"novelty":["абзац","абзац"],'
        '"distinctive":["пункт","пункт","пункт","пункт"],"expediency":["абзац"],'
        '"goal":"Цель программы — одно или два предложения о результате именно этой программы.",'
        '"addressee":["кому адресована эта программа по возрасту и условиям из данных"],'
        '"tasks":["предметная задача по названию","предметная задача"],'
        '"developing":["метапредметная задача","метапредметная задача"],'
        '"educating":["личностная задача","личностная задача"],'
        '"method":"как проходит занятие по этой теме",'
        '"subject":["наблюдаемый результат","результат","результат","результат"],'
        '"modules":[{"theory":"что объясняют","practice":"что делают","tasks":"обязательное задание и задание с усложнением"}],'
        '"literature":["библиографическая запись по ГОСТ Р 7.0.100-2018"]} '
        "Число объектов в modules равно числу разделов и идёт в том же порядке. "
        "Тема всех текстов — только title. direction задаёт область, но не подменяет название. "
        "Не пиши про 3D-моделирование, Blender, аддитивные технологии и любой другой чужой пример, если этих слов нет в title. "
        "Программу заполняют разные организации и разные направленности по всей России. "
        "goal — цель именно этой программы, одно или два предложения. "
        "Начни со слов «Цель программы». Назови видимый результат по названию и разделам. "
        "Не подменяй цель общим текстом направленности и не пиши «освоение обучающимися». "
        "addressee — кому адресована программа: возраст из данных, группа, нужна ли подготовка. Не называй организацию и педагога. "
        "tasks — 3–5 предметных задач именно по title. "
        "developing — 3–4 метапредметные задачи. educating — 3–4 личностные задачи. "
        "Не копируй одни и те же задачи для любой направленности. "
        "literature — 5–8 реальных источников по title для педагога и обучающихся. "
        "Каждую запись оформи по ГОСТ Р 7.0.100-2018 и расположи по алфавиту. "
        "Книга: Фамилия, И. О. Название : сведения / И. О. Фамилия. — Город : Издательство, год. — N с. "
        "Статья: Фамилия, И. О. Название // Издание. — Год. — № номер. — С. страницы. "
        "Электронный ресурс дополни строкой . — URL: адрес (дата обращения: ДД.ММ.ГГГГ). "
        "Не выдумывай ISBN, издательство и год. Если элемент неизвестен, пропусти его, но сохрани знаки ГОСТ у известных. "
        "Законы, приказы, СанПиН и СП в список литературы не включай. "
        "Для возраста младше 14 лет опора на образец, для 14 и старше — больше самостоятельности, если возраст программы это покрывает.\n\n"
        "Данные программы:\n"
        + json.dumps(brief, ensure_ascii=False, indent=2)
    )


def equipment_brief(program: ProgramData) -> dict:
    """Карточка оснащения. Текущие поля оборудования в запрос не входят: их как раз и составляют."""
    brief = plan_brief(program)
    for field in ("software", "subjects", "professions"):
        brief.pop(field, None)
    names = [
        name
        for item in program.modules
        if (name := _hint_for_title(program.title, item.name.strip()))
    ]
    if names:
        brief["modules"] = names
    return brief


def plan_brief(program: ProgramData) -> dict:
    """Карточка плана. Тема — название. Чужой пример про 3D в запрос не попадает."""
    brief = anonymous_brief(program)
    brief.pop("modules", None)
    for field in ("software", "subjects", "professions"):
        brief[field] = _hint_for_title(brief["title"], str(brief.get(field) or ""))
    return brief


def _title_is_example_topic(title: str) -> bool:
    folded = title.lower().replace("ё", "е")
    return any(marker in folded for marker in _EXAMPLE_TOPIC)


def _hint_for_title(title: str, text: str) -> str:
    cleaned = text.strip()
    if not cleaned or _title_is_example_topic(title):
        return cleaned
    folded = cleaned.lower().replace("ё", "е")
    if any(marker in folded for marker in _EXAMPLE_TOPIC):
        return ""
    return cleaned


def _plan_prompt(brief: dict) -> str:
    return (
        "Составь учебный план дополнительной общеобразовательной программы на русском языке. "
        "Единственная тема плана — поле title. Направленность direction только ограничивает область. "
        "Не составляй план про 3D-моделирование, Blender, аддитивные технологии, печать или сканирование, "
        "если этих слов нет в title. Это чужой пример, его нельзя подставлять другим программам. "
        "Педагоги по всей России ведут разные направления: план должен совпасть с названием, которое прислали. "
        "Разделы должны быть про конкретное название, а не общими словами направленности. "
        "Нужно от 5 до 7 разделов. Первый — введение и безопасность по этой теме. "
        "Последний — итоговая работа или аттестация по этой теме. "
        "Если professional_trials истинно, один раздел назови как профессиональную пробу по теме. "
        "Если regional_project истинно, один раздел свяжи с городом из данных. "
        "Часы theory и practice — целые, их сумма по всем разделам должна быть близка к total_hours. "
        "Практики больше, чем теории. Не указывай законы и номера документов. "
        "Не упоминай педагога и организацию. "
        "Для каждого раздела добавь lectures и practices. "
        "lectures — короткие заголовки лекций, примерно по одному на занятие теории "
        "(если теория есть, хотя бы один). "
        "practices — подзаголовки практических занятий, примерно по одному на занятие практики "
        "(если практика есть, хотя бы один). "
        "Это темы конкретных учебных дней по названию программы, а не общий пересказ раздела. "
        "Верни только JSON: {\"modules\":[{\"name\":\"название раздела\",\"theory\":2,\"practice\":8,"
        "\"lectures\":[\"тема лекции\"],\"practices\":[\"тема практики\",\"тема практики\"]}]}\n\n"
        "Данные программы:\n"
        + json.dumps(brief, ensure_ascii=False, indent=2)
    )


def _equipment_prompt(brief: dict) -> str:
    return (
        "Составь оснащение дополнительной общеобразовательной программы на русском языке. "
        "Единственная тема — поле title. Направленность direction только ограничивает область. "
        "Не пиши про 3D-моделирование, Blender, аддитивные технологии, 3D-печать и 3D-сканирование, "
        "если этих слов нет в title. Это чужой пример, его нельзя подставлять другим программам. "
        "Педагоги по всей России ведут разные направления и работают в разных организациях. "
        "Не называй организацию, педагога, завод и конкретную школу. "
        "Оборудование должно быть нужно именно для занятий по title и безопасно для возраста age_from–age_to. "
        "Не выдумывай дорогую технику, которой нет в названии. "
        "Если теме хватает кабинета, столов и простых материалов, перечисли их. "
        "Расходные материалы — то, что тратится на занятии: бумага, краска, ткань, глина и другое по title. "
        "Не повторяй ими мебель и оборудование. Не выдумывай пластик для печати и другие чужие материалы. "
        "Программное обеспечение — только то, без чего тему не провести. "
        "Если отдельная программа не нужна, одна фраза: занятие идёт без неё и без обязательного интернета. "
        "Не требуй платный пакет, если его название не следует из title. "
        "Профессии — роли для ознакомительной пробы по title, а не чужая специальность. "
        "Не указывай законы, приказы, СанПиН, СП и номера документов. "
        "Верни только JSON: "
        '{"equipment":["предмет","предмет"],'
        '"consumables":["расходный материал","расходный материал"],'
        '"software":["программа или одна фраза, что она не нужна"],'
        '"professions":["роль","роль","роль"]}\n\n'
        "Данные программы:\n"
        + json.dumps(brief, ensure_ascii=False, indent=2)
    )


def parse_equipment(raw: str, title: str) -> dict[str, str]:
    """Оставляет только строки по названию программы и отбрасывает чужой пример про 3D."""
    data = _load_json(raw)
    equipment = _item_lines(data.get("equipment"), title, 12, 180)
    consumables = _item_lines(data.get("consumables"), title, 8, 160)
    software = _item_lines(data.get("software"), title, 6, 240)
    roles = _item_lines(data.get("professions"), title, 6, 80)
    if len(equipment) < 3:
        raise GenerationError("Сервис не составил перечень оборудования. Повторите запрос.")
    if len(consumables) < 2:
        raise GenerationError("Сервис не составил перечень расходных материалов. Повторите запрос.")
    if not software:
        raise GenerationError("Сервис не описал программное обеспечение. Повторите запрос.")
    if len(roles) < 2:
        raise GenerationError("Сервис не назвал профессии для проб. Повторите запрос.")
    return {
        "equipment": "\n".join(equipment),
        "consumables": "\n".join(consumables),
        "software": "\n".join(software),
        "professions": "; ".join(roles),
    }


def _item_lines(value, title: str, limit: int, width: int) -> list[str]:
    if isinstance(value, str):
        chunks = value.replace(";", "\n").splitlines()
    elif isinstance(value, list):
        chunks = []
        for item in value:
            chunks.extend(str(item or "").replace(";", "\n").splitlines())
    else:
        return []
    items: list[str] = []
    for chunk in chunks:
        text = " ".join(chunk.split()).strip(" .;—-")
        if len(text) > width:
            text = text[:width].rstrip(" ,.;")
        if len(text) < 2 or _FORBIDDEN.search(text) or not _hint_for_title(title, text):
            continue
        if text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def parse_plan(raw: str, total_hours: int) -> list[ModuleItem]:
    """Оставляет названия модели и заново раскладывает часы, чтобы сумма совпала с программой."""
    data = _load_json(raw)
    rows = data.get("modules")
    if not isinstance(rows, list):
        raise GenerationError("В ответе нет списка разделов. Повторите запрос.")
    prepared: list[tuple[str, int, float]] = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        name = " ".join(str(row.get("name") or "").split())
        if len(name) < 3:
            continue
        theory = _nonneg(row.get("theory"))
        practice = _nonneg(row.get("practice"))
        weight = theory + practice or 1
        ratio = min(0.55, max(0.12, theory / weight))
        prepared.append((name[:140], weight, ratio, _topic_list(row.get("lectures")), _topic_list(row.get("practices"))))
    if len(prepared) < 4:
        raise GenerationError("Сервис предложил слишком мало разделов. Повторите запрос.")
    totals = largest_remainder(total_hours, [item[1] for item in prepared])
    if total_hours >= len(totals):
        while 0 in totals:
            empty = totals.index(0)
            donor = max(range(len(totals)), key=lambda index: totals[index])
            if totals[donor] <= 1:
                break
            totals[donor] -= 1
            totals[empty] = 1
    modules: list[ModuleItem] = []
    for (name, _weight, ratio, lectures, practices), hours in zip(prepared, totals):
        theory, practice = _split_module_hours(hours, ratio)
        modules.append(
            ModuleItem(name=name, theory=theory, practice=practice, lectures=lectures, practices=practices)
        )
    if sum(item.hours for item in modules) != total_hours:
        raise GenerationError("Не удалось свести часы разделов с объёмом программы.")
    return modules


def _split_module_hours(hours: int, theory_ratio: float) -> tuple[int, int]:
    if hours <= 1:
        return 0, hours
    theory = int(round(hours * theory_ratio))
    theory = min(max(theory, 1), hours - 1)
    return theory, hours - theory


def _topic_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    found: list[str] = []
    for item in value:
        text = " ".join(str(item or "").split())
        if len(text) < 3 or _FORBIDDEN.search(text):
            continue
        found.append(text[:180])
        if len(found) >= 24:
            break
    return found


def _nonneg(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _complete(prompt: str) -> str:
    provider, key = current_credentials()
    if len(key) < 10:
        raise GenerationError("Откройте «Настройки» и вставьте ключ выбранного сервиса.")
    if provider == "gigachat":
        return _gigachat(key, prompt)
    if provider == "deepseek":
        return _deepseek(key, prompt)
    return _gemini(key, prompt)


def _request(api_key: str, prompt: str) -> str:
    # Тот же вызов, что в документации AI Studio: interactions, а не старый generateContent.
    # thinking_level low — иначе модель долго «думает» и запрос обрывается по времени.
    body = {
        "model": _known_gemini_model(load_settings().get("gemini_model")),
        "input": prompt,
        "generation_config": {"thinking_level": "low"},
    }
    request = urllib.request.Request(
        _URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GenerationError(_http_message(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        if _is_timeout(exc.reason):
            raise GenerationError(_gemini_timeout()) from exc
        raise GenerationError(
            "Нет соединения с Google. Ключ из AI Studio при этом может быть верным: "
            "адрес сервиса с этой сети часто не открывается. В «Настройках» выберите GigaChat."
        ) from exc
    except TimeoutError as exc:
        raise GenerationError(_gemini_timeout()) from exc
    return _interaction_text(payload)


def _is_timeout(reason) -> bool:
    return isinstance(reason, TimeoutError) or "timed out" in str(reason).lower()


def _gemini_timeout() -> str:
    return (
        "Google не ответил за отведённое время. Ключ со страницы AI Studio может быть верным: "
        "с этой сети сервис часто недоступен. Откройте «Настройки», выберите GigaChat "
        "и вставьте ключ авторизации с developers.sber.ru."
    )


def _interaction_text(payload: dict) -> str:
    chunks: list[str] = []
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        chunks.append(direct.strip())
    for step in payload.get("steps") or []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        content = step.get("content")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    chunks.append(str(part["text"]))
    text = "\n".join(chunk for chunk in chunks if chunk.strip()).strip()
    if not text:
        status = str(payload.get("status") or "пустой ответ")
        raise GenerationError(f"Gemini не вернул текст ({status}). Повторите запрос.")
    return text


def _gemini(api_key: str, prompt: str) -> str:
    return _request(api_key, prompt)


def _deepseek(api_key: str, prompt: str) -> str:
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(
            {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
        method="POST",
    )
    payload = _read_json(request, "DeepSeek")
    return _chat_content(payload, "DeepSeek")


def _gigachat(api_key: str, prompt: str) -> str:
    secret = api_key.strip()
    if secret.lower().startswith("basic "):
        secret = secret[6:].strip()
    token_request = urllib.request.Request(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        data=urllib.parse.urlencode({"scope": "GIGACHAT_API_PERS"}).encode("utf-8"),
        headers={
            "Authorization": f"Basic {secret}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    token_payload = _read_json(token_request, "GigaChat")
    token = str(token_payload.get("access_token") or "")
    if not token:
        raise GenerationError("GigaChat не выдал доступ. Проверьте ключ авторизации в кабинете developers.sber.ru.")
    chat_request = urllib.request.Request(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        data=json.dumps(
            {
                "model": "GigaChat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    return _chat_content(_read_json(chat_request, "GigaChat"), "GigaChat")


def _read_json(request: urllib.request.Request, service: str) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=90, context=app_ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GenerationError(_service_http(service, exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "CERTIFICATE" in reason.upper() or "certificate" in reason.lower():
            raise GenerationError(
                f"{service} не открылся: сертификат сервера не подошёл. "
                "Сертификаты Минцифры уже встроены в ДопПро. Проверьте дату и время на компьютере и повторите."
            ) from exc
        raise GenerationError(f"Нет соединения с интернетом или {service} не ответил.") from exc
    except TimeoutError as exc:
        raise GenerationError(f"{service} не ответил за отведённое время. Повторите запрос.") from exc


def _chat_content(payload: dict, service: str) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise GenerationError(f"{service} вернул пустой ответ. Повторите запрос.")
    message = choices[0].get("message") or {}
    text = str(message.get("content") or "").strip()
    if not text:
        raise GenerationError(f"{service} вернул пустой текст. Повторите запрос.")
    return text


def _service_http(service: str, code: int, detail: str) -> str:
    if code in (400, 401, 403):
        return f"Ключ {service} не принят. Проверьте его в «Настройках»."
    if code == 402:
        return f"На счёте {service} нет средств. Для DeepSeek API нужен пополненный баланс, чат на сайте бесплатный."
    if code == 429:
        return f"Лимит запросов {service} на сегодня исчерпан. Повторите позже."
    short = _error_text(detail)
    if short:
        return f"{service} ответил ошибкой {code}: {short}"
    return f"{service} ответил ошибкой {code}."


def _response_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        message = ((payload.get("promptFeedback") or {}).get("blockReason")) or "пустой ответ"
        raise GenerationError(f"Сервис не вернул текст ({message}).")
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    chunks = [part.get("text", "") for part in parts if part.get("text") and not part.get("thought")]
    text = "\n".join(chunks).strip()
    if not text:
        raise GenerationError("Сервис вернул пустой текст. Повторите запрос.")
    return text


def _http_message(code: int, detail: str) -> str:
    if code in (400, 401, 403):
        return "Ключ Gemini не принят. Создайте ключ в Google AI Studio и вставьте его сюда."
    if code == 404:
        return "Эта версия Gemini недоступна. Откройте «Настройки» и выберите другую версию."
    if code == 503:
        return (
            "Эта версия Gemini сейчас перегружена. Откройте «Настройки» и выберите версию ниже, "
            "например Gemini 3.5 Flash-Lite."
        )
    if code == 429:
        return "Лимит бесплатных запросов на сегодня исчерпан. Повторите позже."
    short = _error_text(detail)
    if short:
        return f"Сервис Gemini ответил ошибкой {code}: {short}"
    return f"Сервис Gemini ответил ошибкой {code}."


def _error_text(detail: str) -> str:
    try:
        payload = json.loads(detail)
        message = str(((payload.get("error") or {}).get("message")) or "")
    except json.JSONDecodeError:
        message = detail
    message = re.sub(r"\s+", " ", message).strip()
    return message[:240]


def _load_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GenerationError("Сервис вернул текст не в виде карточки. Повторите запрос.") from exc
    if not isinstance(data, dict):
        raise GenerationError("Сервис вернул не тот формат. Повторите запрос.")
    return data


def _clean(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", " ".join(str(text).split()))
    kept = [part for part in parts if part and not _FORBIDDEN.search(part)]
    return " ".join(kept).strip()[:1500]


def _goal_text(value) -> str:
    text = _one(value)
    if len(text) < 40:
        return ""
    if not text.endswith("."):
        text += "."
    return text


def _sources(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = " ".join(str(item or "").split())
        if len(text) < 12 or _LAW_ONLY.search(text):
            continue
        items.append(text[:500])
        if len(items) >= 8:
            break
    items.sort(key=lambda line: line.casefold())
    return items


def _one(value) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return _clean(value or "")


def _paragraphs(value, minimum: int, maximum: int) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = _clean(item)
        if len(text) >= 40:
            items.append(text)
        if len(items) >= maximum:
            break
    if len(items) < minimum:
        return items
    return items


def _modules(value, count: int) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value[:count]:
        if not isinstance(item, dict):
            rows.append({"theory": "", "practice": "", "tasks": ""})
            continue
        rows.append(
            {
                "theory": _clean(item.get("theory", "")),
                "practice": _clean(item.get("practice", "")),
                "tasks": _clean(item.get("tasks", "")),
            }
        )
    return rows
