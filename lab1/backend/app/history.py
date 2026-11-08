"""История поздравлений: JSONL в DATA_DIR (volume).

Запись — best-effort: недоступный volume не должен ломать API.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)


def append_record(data_dir: str, record: dict) -> None:
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "history.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("не удалось записать историю: %s", exc)
