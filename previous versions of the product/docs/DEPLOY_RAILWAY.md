# Деплой AI Career Pathfinder на Railway

## Что будет работать после деплоя

Один сервис на Railway, один URL. FastAPI (`api.py`) отдаёт:

- `/api/*`, `/health` — REST API (бэкенд)
- всё остальное — React SPA (фронтенд из `frontend/dist`)

---

## Пошаговая инструкция

### 1. Убедитесь, что репозиторий содержит нужные файлы

В корне проекта должны быть:

```
Dockerfile          ← мульти-стейдж: Node собирает фронт, Python запускает API
api.py              ← FastAPI с SPA-фолбэком
frontend/           ← React-приложение (исходники)
requirements.txt    ← Python-зависимости
data/               ← JSON-файлы (навыки, атлас)
```

Файл `Dockerfile` уже есть в репозитории. Он делает:

1. Стейдж 1 (Node 20): `npm ci` + `npm run build` → собирает `frontend/dist`
2. Стейдж 2 (Python 3.12): `pip install` + копирует всё + `frontend/dist`
3. Запуск: `uvicorn api:app --host 0.0.0.0 --port $PORT`

### 2. Откройте Railway Dashboard

Идём в [railway.app](https://railway.app) → ваш проект.

### 3. Если сервис уже существует (подключён к репозиторию)

#### 3a. Переключите билдер на Dockerfile

1. Откройте сервис → **Settings**
2. В секции **Build** → **Builder** выберите **Dockerfile**
3. Поле **Dockerfile Path** оставьте пустым (или укажите `Dockerfile`)
4. Нажмите **Save** / подтвердите

#### 3b. Измените Start Command (если нужно)

Обычно Railway подхватывает `CMD` из Dockerfile автоматически.
Если нужно явно — в **Settings → Deploy → Start Command**:

```
uvicorn api:app --host 0.0.0.0 --port $PORT
```

#### 3c. Установите переменные окружения

Перейдите в **Variables** и добавьте:

| Переменная | Обязательность | Описание |
|---|---|---|
| `OPENAI_API_KEY` | Рекомендуется | Ключ OpenAI. Без него парсинг резюме вернёт 503, а генерация планов через LLM не будет работать |
| `QDRANT_URL` | Опционально | URL Qdrant-кластера для RAG-подсказок |
| `QDRANT_API_KEY` | Опционально | API-ключ Qdrant |

> `PORT` добавлять **не нужно** — Railway устанавливает его автоматически.

#### 3d. Задеплойте

Railway деплоит автоматически при пуше в подключённую ветку.

Если нужно задеплоить вручную:
- Кнопка **Deploy** в Dashboard
- Или: поменяйте ветку в **Settings → Source → Branch** на `cursor/mvp-de67`

### 4. Если создаёте новый сервис с нуля

1. **New Project** (или **+ New Service** в существующем проекте)
2. Выберите **Deploy from GitHub Repo**
3. Найдите репозиторий `career_buid_sysytem`
4. Railway определит `Dockerfile` и начнёт билд
5. Если не определил — зайдите в **Settings → Build → Builder → Dockerfile**
6. Добавьте переменные (см. п. 3c)
7. Дождитесь деплоя, откройте сгенерированный URL

### 5. Откройте приложение

После успешного деплоя:

1. Перейдите на вкладку **Settings → Networking → Public Networking**
2. Нажмите **Generate Domain** (если домена ещё нет)
3. Откройте сгенерированный URL — увидите Welcome-экран фронтенда

---

## Проверка работоспособности

```bash
# Замените <YOUR_DOMAIN> на ваш Railway-домен
curl https://<YOUR_DOMAIN>/health
# Ожидание: {"status":"ok"}

curl https://<YOUR_DOMAIN>/api/professions
# Ожидание: {"professions":["Product Manager","..."]}

# Откройте в браузере:
open https://<YOUR_DOMAIN>
# Ожидание: Welcome-экран "AI Career Pathfinder"
```

---

## Типичные проблемы

### Билд падает на `npm run build`

Проверьте, что в репозитории есть `frontend/package-lock.json`. Без него `npm ci` не работает.

### Билд падает на `pip install` (torch)

В `requirements.txt` первой строкой стоит `--extra-index-url https://download.pytorch.org/whl/cpu` — это нормально, CPU-версия torch ставится быстрее и весит меньше. Если всё равно не хватает памяти — увеличьте план Railway или временно уберите `torch` + `sentence-transformers` (RAG-фичи отключатся, остальное будет работать).

### Фронтенд не открывается (404 или JSON вместо HTML)

Убедитесь, что:
- `api.py` содержит блок `# Serve React frontend` в конце файла
- Dockerfile копирует `frontend/dist` командой `COPY --from=frontend-build`
- Ветка, из которой деплоите, содержит все изменения (push прошёл)

### Резюме-парсинг возвращает 503

Это ожидаемое поведение, если `OPENAI_API_KEY` не задан. Фронтенд покажет сообщение «Авторазбор резюме временно недоступен» и предложит добавить навыки вручную.

### Railway не видит Dockerfile

Зайдите в **Settings → Build → Builder** и вручную выберите **Dockerfile**.

---

## Локальная проверка перед деплоем

```bash
# Собрать и запустить через Docker локально:
docker build -t career-pathfinder .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... career-pathfinder

# Открыть http://localhost:8000
```

---

## Структура деплоя (итого)

```
Railway Service
├── Dockerfile (мульти-стейдж)
│   ├── Stage 1: node:20 → npm ci + npm run build
│   └── Stage 2: python:3.12 → pip install + uvicorn
├── Переменные: OPENAI_API_KEY, (QDRANT_URL, QDRANT_API_KEY)
└── Порт: $PORT (автоматически от Railway)
```

Один контейнер, один сервис, один URL — бэкенд + фронтенд вместе.
