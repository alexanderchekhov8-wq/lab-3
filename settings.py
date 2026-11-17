"""Чтение и проверка параметров эксперимента."""

import argparse
import json
import math
from pathlib import Path


DEFAULTS = {
    "arrival_rate": 20.0,
    "service_mean": 2.0,
    "hours": 8.0,
    "cashiers": [1, 2, 3],
    "runs": 200,
    "threshold": 5.0,
    "seed": 42,
    "output": str(Path(__file__).resolve().parent / "results"),
}

LABELS = {
    "arrival_rate": "Поток покупателей, человек/час",
    "service_mean": "Среднее обслуживание, минут",
    "hours": "Продолжительность рабочего дня, часов",
    "cashiers": "Варианты числа касс (через пробел, например 1 2 3)",
    "runs": "Число моделируемых дней",
    "threshold": "Порог ожидания, минут",
    "seed": "Начальное значение генератора",
    "output": "Папка результатов",
}


def validate_value(key, value):
    if key == "cashiers":
        if (not isinstance(value, list) or not value
                or any(type(c) is not int or c < 1 for c in value)):
            raise ValueError("cashiers: нужен непустой список положительных целых чисел")
        return sorted(set(value))
    if key in ("runs", "seed"):
        minimum = 2 if key == "runs" else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"{key}: нужно целое число не меньше {minimum}")
        return value
    if key == "output":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("output: нужен непустой путь к папке")
        return value
    if (type(value) not in (int, float)
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{key}: нужно конечное положительное число")
    return float(value)


def load_config(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("В файле настроек должен быть JSON-объект")
    unknown = set(data) - DEFAULTS.keys()
    if unknown:
        raise ValueError("Неизвестные параметры: " + ", ".join(sorted(unknown)))
    result = {key: validate_value(key, value) for key, value in data.items()}
    if "output" in result:
        output = Path(result["output"]).expanduser()
        result["output"] = str(output if output.is_absolute() else path.resolve().parent / output)
    return result


def prompt_settings(values):
    print("Введите параметры. Enter сохраняет значение в скобках.")
    for key, label in LABELS.items():
        while True:
            raw = input(f"{label} [{values[key]}]: ").strip()
            if not raw:
                break
            try:
                if key == "cashiers":
                    value = [int(part) for part in raw.replace(",", " ").split()]
                elif key in ("runs", "seed"):
                    value = int(raw)
                elif key == "output":
                    value = raw
                else:
                    value = float(raw.replace(",", "."))
                values[key] = validate_value(key, value)
                break
            except ValueError as error:
                print(f"Некорректное значение: {error}. Повторите ввод.")
    return values


def parse_settings(argv=None):
    parser = argparse.ArgumentParser(
        description="Моделирование отдельных очередей к кассам магазина",
        argument_default=argparse.SUPPRESS,
    )
    parser.add_argument("--config", type=Path, help="Файл параметров JSON")
    parser.add_argument("--interactive", action="store_true", help="Пошаговый ввод параметров")
    for key in DEFAULTS:
        options = {"help": f"{LABELS[key]}; по умолчанию: {DEFAULTS[key]}"}
        if key == "cashiers":
            options.update(type=int, nargs="+")
        elif key in ("runs", "seed"):
            options["type"] = int
        elif key != "output":
            options["type"] = float
        parser.add_argument("--" + key.replace("_", "-"), **options)
    cli = vars(parser.parse_args(argv))
    config_path = cli.pop("config", None)
    interactive = cli.pop("interactive", False)
    values = DEFAULTS.copy()
    try:
        if config_path is not None:
            values.update(load_config(config_path))
        values.update({key: validate_value(key, value) for key, value in cli.items()})
        if interactive:
            values = prompt_settings(values)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\nВвод параметров прерван.\n")
    values["output"] = Path(values["output"]).expanduser().resolve()
    return argparse.Namespace(**values)
