import json
import pathlib
from app.history import append_record


def test_creates_dir_and_roundtrip(tmp_path):
    data_dir = str(tmp_path / "не-существует")
    append_record(data_dir, {"greeting": "привет"})
    lines = pathlib.Path(data_dir, "history.jsonl").read_text().splitlines()
    assert json.loads(lines[0]) == {"greeting": "привет"}


def test_unwritable_dir_does_not_raise(tmp_path):
    blocker = tmp_path / "занят"
    blocker.write_text("это файл, не каталог")
    append_record(str(blocker), {"greeting": "привет"})  # не должно бросить
