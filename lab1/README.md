# ЛР 1. Dockerfile

Приложение — «поздравлялка» на FastAPI: по запросу выдаёт поздравление с
сегодняшним днём (праздник или обычный день). Текст старается сгенерировать
локальная LLM (llama.cpp), если она недоступна — шаблонный fallback. История
поздравлений пишется в JSONL на volume. 

## Что где лежит

```
lab1/
  backend/
    app/                     # код FastAPI (main, config, dates, llm, ratelimit, history)
    tests/                   # 28 pytest-тестов
    requirements.txt         # зависимости с точными версиями
    Dockerfile.bad           # плохой Dockerfile (собирается и работает)
    Dockerfile               # хороший Dockerfile
    Dockerfile.dockerignore  # .dockerignore для хорошей сборки
    .env                     # фейковый токен — для демо утечки секрета (см. п. 9)
  run-stack.sh               # необязательное демо: бэкенд + llama.cpp с Qwen3-1.7B
  README.md                  # этот отчёт
```

## Как запустить

Хороший образ (с volume):

```bash
docker build -t greetings-backend lab1/backend
docker volume create greetings-data
docker run -d --name greetings-good -p 8000:8000 -v greetings-data:/data greetings-backend
curl http://localhost:8000/api/greeting
```

Плохой — так же, но `Dockerfile.bad`: `docker build -f lab1/backend/Dockerfile.bad -t greetings-bad lab1/backend`.
Он тоже поднимается и отвечает на `/api/greeting`

Демо с моделью (необязательно): `bash lab1/run-stack.sh`, поднимет llama.cpp
и бэкенд в общей docker-сети;

## Плохой Dockerfile: разбор практик

Исходник — [`Dockerfile.bad`](backend/Dockerfile.bad):

```dockerfile
FROM python:latest
ENV HF_TOKEN=hf_demo_FAKE_token_for_leak_demo
RUN apt-get update
RUN apt-get -y install vim nano curl
WORKDIR app
COPY . .
RUN pip install fastapi uvicorn httpx
EXPOSE 8000
ENTRYPOINT uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**1. Базовый образ `python:latest`**

Тег `latest` мутирующий: завтра он может указывать на другую версию Python,
и сборка перестанет воспроизводиться. Исправлено: `python:3.12-slim` —
конкретная версия, та же, что в venv разработчика.

**2. Всё работает под root**

Без инструкции `USER` процесс в контейнере выполняется от root. Если процесс
выберется из изоляции, на хосте это тоже root. Исправлено: отдельный
пользователь с UID 10001 и `USER 10001:10001`.

**3. `COPY . .` без `.dockerignore`**

В build context попадает всё подряд: внутри образа `.env`, `.venv` целиком,
`tests/`, `.pytest_cache`. Это лишний вес, риск утечки секретов (см. п. 9)
и лишние инвалидации кэша. Исправлено: `Dockerfile.dockerignore` рядом
с Dockerfile, в образ копируется только `app/`.

**4. Код скопирован до установки зависимостей**

`COPY . .` стоит раньше `pip install`: меняешь любой файл — сбрасывается кэш
всех следующих слоёв, и зависимости ставятся заново. Слои кэшируются по
содержимому инструкции, поэтому порядок должен идти от редко меняющегося
к часто меняющемуся. Исправлено: сначала `COPY requirements.txt` и установка,
и только потом `COPY app/`.

**5. Непиненные зависимости и кэш pip**

`pip install fastapi uvicorn httpx` без версий — при пересборке можно
неожиданно получить новые версии. Плюс нет `--no-cache-dir`, и скачанные
wheels остаются в слое. Исправлено: `requirements.txt` с точными версиями
и `pip install --no-cache-dir`.

**6. Shell-form `ENTRYPOINT`**

`ENTRYPOINT uvicorn ...` запускается как `/bin/sh -c "uvicorn ..."`, поэтому
PID 1 — shell, а не приложение. `docker stop` шлёт SIGTERM в PID 1, shell его
не пересылает, через 10 секунд прилетает SIGKILL без graceful shutdown.
Проверил: `time docker stop` на плохом контейнере — 10.3 с, на хорошем
(exec-форма `ENTRYPOINT ["uvicorn", ...]`) — 0.6 с.

**7. Debug-пакеты и грязный apt**

`vim`, `nano`, `curl` в образе — лишний вес и поверхность атаки. apt-слои
не склеены, без `--no-install-recommends` и пинов версий; `rm -rf
/var/lib/apt/lists/*` в отдельном слое ничего не удаляет — файлы остаются
в предыдущем слое. `WORKDIR app` к тому же относительный путь. Исправлено:
никаких debug-пакетов, runtime-слой минимальный.

**8. `--reload` и буферизованные логи**

`uvicorn --reload` — режим разработки: следит за файлами и перезапускается,
в «проду» ему не место. Плюс без `PYTHONUNBUFFERED=1` stdout буферизуется
и логи не видны в `docker logs` в реальном времени. Исправлено: обычный
`uvicorn` в exec-форме и `ENV PYTHONUNBUFFERED=1`.

**9. Секрет через `ENV`**

`ENV HF_TOKEN=...` навсегда остаётся в метаданных образа: `docker inspect`
и `docker history` показывают его любому, у кого есть образ. Токен в репозитории
фейковый (`backend/.env`), создан только для этого демо. Исправлено: секретов
в образе нет, передавать их нужно на рантайме (`-e`, в k8s — Secret).

hadolint по обоим файлам (10 замечаний у плохого, 0 у хорошего):

```
$ docker run --rm -i hadolint/hadolint < lab1/backend/Dockerfile.bad
DL3007 warning  Using latest is prone to errors...
DL3064 warning  Potentially sensitive data should not be used in the ARG or ENV
DL3009 info     Delete the apt lists after installing something
DL3059 info     Multiple consecutive RUN instructions...
DL3008 warning  Pin versions in apt get install
DL3015 info     Avoid additional packages by specifying --no-install-recommends
DL3000 error    Use absolute WORKDIR
DL3013 warning  Pin versions in pip
DL3042 warning  Avoid use of cache directory with pip
DL3025 warning  Use arguments JSON notation for CMD and ENTRYPOINT
$ docker run --rm -i hadolint/hadolint < lab1/backend/Dockerfile
(пусто)
```

## Хороший Dockerfile

[`Dockerfile`](backend/Dockerfile) — multi-stage:

- builder ставит pinned-зависимости в `--prefix=/install`, runtime забирает
  только результат через `COPY --from=builder`;
- non-root `USER 10001:10001`, `/data` создан заранее и отдан пользователю,
  чтобы volume наследовал владельца;
- порядок слоёв: `requirements.txt` → установка → код;
- exec-form `ENTRYPOINT`, `PYTHONUNBUFFERED=1`, секретов нет;
- `HEALTHCHECK` по `/healthz` средствами python (curl в образ не ставим);
- `.dockerignore` рядом с Dockerfile.

Итог: **204 MB против 1.86 GB** у плохого, graceful stop 0.6 с против 10.3 с,
hadolint — 0 замечаний, внутри образа только `app/`.

## Две плохие практики использования контейнера

**1. Хранить данные в writable-слое вместо volume.**

Контейнер эфемерен: пересоздали — и история пропала, а запись в слой
медленнее и раздувает образ. Приложение пишет историю в `/data`; без
`-v` файл `history.jsonl` умрёт вместе с контейнером:

```bash
docker run -d -p 8000:8000 greetings-backend                          # плохо
docker run -d -p 8000:8000 -v greetings-data:/data greetings-backend  # хорошо
```


**2. Запуск без лимитов CPU/памяти.**

Без `--memory`/`--cpus` один контейнер с утечкой съедает память хоста,
и OOM-killer начинает убивать чужие процессы. Для нашего бэкенда, который
дёргает LLM, актуально:

```bash
docker run -d -p 8000:8000 greetings-backend                                            # плохо
docker run -d -p 8000:8000 --memory=512m --cpus=1.0 --restart=on-failure:3 greetings-backend  # хорошо
```

## Проверка

| Проверка | Плохой образ | Хороший образ |
|---|---|---|
| Сборка и `/api/greeting` | ✅ 200 | ✅ 200 |
| hadolint | 10 замечаний | 0 |
| Размер | 1.86 GB | 204 MB |
| `time docker stop` | 10.3 с (SIGKILL) | 0.6 с (SIGTERM) |
| Внутри образа | `.env`, `.venv`, `tests/`, токен в ENV | только `app/` |
| Пользователь | root | uid=10001 |
| Volume | — | `history.jsonl` пережил рестарт |

Демо с моделью (Qwen3-1.7B, ~11 tok/s на CPU) и деградация:

```json
{"date": "2026-11-08", "holiday": null, "source": "llm",
 "greeting": "С доброй осенью! Тепло, уют и радость в каждом ветру. Удачи и счастья тебе!"}
```

После `docker stop greetings-model` бэкенд сразу отвечает `"source": "fallback"`.

Тесты: `pytest lab1/backend/tests` — 28 passed.
