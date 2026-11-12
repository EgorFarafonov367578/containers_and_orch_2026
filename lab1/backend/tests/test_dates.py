import datetime
from app.dates import build_prompt, describe_date, today


def test_today_uses_requested_timezone():
    # 2026-12-31 21:30 UTC — это уже 2027-01-01 в Москве.
    moment = datetime.datetime(2026, 12, 31, 21, 30,
                               tzinfo=datetime.timezone.utc)
    assert today("Europe/Moscow", moment) == datetime.date(2027, 1, 1)


def test_new_year():
    holiday, seasonal = describe_date(datetime.date(2027, 1, 1))
    assert holiday == "Новый год"
    assert seasonal  # непустая строка


def test_first_day_of_summer():
    holiday, _ = describe_date(datetime.date(2027, 6, 1))
    assert holiday == "первый день лета"


def test_no_holiday_gives_season():
    holiday, seasonal = describe_date(datetime.date(2027, 7, 15))
    assert holiday is None
    assert "лет" in seasonal


def test_all_holidays_named():
    for md, name in {(3, 8): "8 Марта", (12, 31): "канун Нового года",
                     (9, 1): "День знаний"}.items():
        assert describe_date(datetime.date(2027, *md))[0] == name


def test_prompt_mentions_date_and_occasion():
    p = build_prompt(datetime.date(2027, 1, 1))
    assert "2027-01-01" in p and "Новый год" in p


def test_greeting_phrase_holiday_forms():
    # форма «С ...» — творительный падеж, а не номинатив («С Новым годом!», не «С Новый год!»)
    from app.dates import greeting_phrase
    assert greeting_phrase(datetime.date(2027, 1, 1)) == \
        "С Новым годом! Пусть этот день принесёт только хорошее."
    assert greeting_phrase(datetime.date(2027, 6, 1)) == \
        "С первым днём лета! Пусть этот день принесёт только хорошее."
    assert greeting_phrase(datetime.date(2027, 5, 9)) == \
        "С Днём Победы! Пусть этот день принесёт только хорошее."
    assert greeting_phrase(datetime.date(2027, 12, 31)) == \
        "С наступающим Новым годом! Пусть этот день принесёт только хорошее."


def test_greeting_phrase_no_holiday_is_seasonal():
    from app.dates import greeting_phrase
    assert greeting_phrase(datetime.date(2027, 7, 15)) == "Хорошего летнего дня!"
