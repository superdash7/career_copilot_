# Career Copilot — AI Career Pathfinder

<div align="center">

**Персональный навигатор карьерного роста на основе AI**

Анализ навыков · Gap-анализ · План развития 70/20/10

</div>

---

## Что это

Career Copilot — веб-приложение, которое помогает специалистам построить индивидуальный план карьерного развития. Система сопоставляет текущие навыки пользователя с требованиями целевой роли, определяет зоны роста и генерирует конкретные шаги по модели 70/20/10 (практика / менторство / обучение).

### Три сценария

| Сценарий | Что делает |
|----------|------------|
| **Следующий грейд** | Показывает, что нужно для перехода Junior → Middle → Senior → Lead → Expert в текущей роли |
| **Смена профессии** | Сравнивает навыки с требованиями новой роли, находит пересечения и пробелы |
| **Исследование возможностей** | Ранжирует все доступные роли по совпадению с профилем пользователя |

### Как это работает

```
┌─ Пользователь ──────────────────────────────────────────────┐
│                                                              │
│  1. Выбирает профессию и сценарий                           │
│  2. Добавляет навыки (из резюме PDF или вручную)            │
│  3. Получает персональный план развития                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Backend Pipeline ──────────────────────────────────────────┐
│                                                              │
│  Нормализация навыков (pymorphy3 + синонимы)                │
│       ↓                                                      │
│  Подбор требований роли из справочника                       │
│       ↓                                                      │
│  Gap-анализ: текущий уровень vs требуемый                   │
│       ↓                                                      │
│  Обогащение контекстом через RAG (Qdrant)                   │
│       ↓                                                      │
│  Генерация плана через GPT-4o (модель 70/20/10)             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Архитектура

```
┌────────────────────────────────────────────────────────────────────────┐
│                         КЛИЕНТ (Браузер)                               │
│                                                                        │
│   React 19 · TypeScript 5.9 · Tailwind CSS 4 · Vite 7 · Recharts      │
│                                                                        │
│   PublicLanding · Auth · Onboarding · Dashboard                        │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐   │
│   │ GoalSetup│→ │  Skills  │→ │ Confirm  │→ │ Result   │ (+ Growth/   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  Switch UI)   │
│        ↑              ↑             ↑              ↑            ↑     │
│        └──────── History API (browser back/forward) ────────────┘     │
│                  sessionStorage (persist on refresh)                    │
│                                                                        │
│   AuthContext (JWT) · ProtectedRoute · ShareCard                       │
│   Компоненты: SearchableSelect · SkillCard · ScenarioCard · Toast    │
│               Stepper · Skeleton · ErrorBoundary · FeedbackRating     │
│                                                                        │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
                             │  HTTP (JSON / multipart)
                             │  AbortController для отмены запросов
                             │
┌────────────────────────────▼───────────────────────────────────────────┐
│                      FastAPI (api.py)                                   │
│                                                                        │
│   REST API                         SPA Fallback                        │
│   ├─ GET  /api/professions         /{path} → frontend/dist/index.html │
│   ├─ GET  /api/skills-for-role     POST /api/auth/register · login     │
│   ├─ GET  /api/skills-by-category  POST /api/auth/refresh · logout    │
│   ├─ GET  /api/suggest-skills      GET  /api/auth/me                  │
│   ├─ POST /api/analyze-resume      PATCH /api/auth/onboarding         │
│   ├─ POST /api/plan                GET|POST /api/analyses · GET/{id}  │
│   ├─ POST /api/focused-plan        GET|PATCH /api/progress            │
│   ├─ GET  /api/share/{analysis_id}                                    │
│   └─ GET  /health                                                     │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                       БИЗНЕС-ЛОГИКА                                    │
│                                                                        │
│   ┌───────────────────┐     ┌──────────────┐     ┌──────────────────┐ │
│   │ scenario_handler  │     │ gap_analyzer │     │ output_formatter │ │
│   │                   │     │              │     │                  │ │
│   │ Маршрутизация     │     │ Сопоставление│     │ Markdown-отчёт   │ │
│   │ по сценарию       │────▶│ навыков с    │────▶│ + вызов LLM      │ │
│   │                   │     │ требованиями │     │ для плана        │ │
│   └───────┬───────────┘     └──────────────┘     └────────┬─────────┘ │
│           │                                               │           │
│   ┌───────▼───────────────────────────┐    ┌──────────────▼─────────┐ │
│   │ next_grade_service                │    │ plan_generator         │ │
│   │ switch_profession_service         │    │                        │ │
│   │ explore_recommendations           │    │ GPT-4o: план 70/20/10 │ │
│   │                                   │    │ retry + fallback       │ │
│   │ Детализация каждого сценария      │    │                        │ │
│   └───────────────────────────────────┘    └────────────────────────┘ │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                     ДАННЫЕ И NLP                                       │
│                                                                        │
│   ┌──────────────┐   ┌────────────────┐   ┌──────────────────────┐   │
│   │ data_loader  │   │ skill_         │   │ rag_service          │   │
│   │              │   │ normalizer     │   │                      │   │
│   │ JSON-спра-   │   │                │   │ Sentence-Transformers│   │
│   │ вочники      │   │ pymorphy3 (RU) │   │ + Qdrant             │   │
│   │ навыков и    │   │ Snowball  (EN) │   │                      │   │
│   │ атласа       │   │ + синонимы     │   │ Семантический поиск, │   │
│   │              │   │                │   │ подсказки, ранжиро-  │   │
│   └──────────────┘   └────────────────┘   │ вание ролей          │   │
│                                            └──────────────────────┘   │
│   ┌──────────────┐                                                    │
│   │ resume_      │                                                    │
│   │ parser       │   PDF → текст (pypdf) → GPT-4o → навыки          │
│   └──────────────┘                                                    │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                     ДАННЫЕ ПРИЛОЖЕНИЯ                                  │
│                                                                        │
│   JSON-справочники (data/)          SQLite (`DB_PATH`, см. env):      │
│   навыки · атлас · синонимы         пользователи, анализы, прогресс,   │
│                                     refresh-токены (bcrypt + JWT)      │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                     ВНЕШНИЕ СЕРВИСЫ                                     │
│                                                                        │
│   ┌──────────────────────┐       ┌──────────────────────────────┐     │
│   │  OpenAI API          │       │  Qdrant Cloud (опционально)  │     │
│   │  GPT-4o              │       │  Векторная БД для RAG        │     │
│   │  - парсинг резюме    │       │  - эмбеддинги навыков        │     │
│   │  - генерация плана   │       │  - семантический поиск       │     │
│   └──────────────────────┘       └──────────────────────────────┘     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Поток данных при построении плана

```
  Пользователь              Frontend                   Backend
  ──────────                ────────                   ───────
       │                        │                          │
       │  Выбирает профессию    │                          │
       │───────────────────────▶│  GET /api/professions    │
       │                        │─────────────────────────▶│
       │                        │◀─────────────────────────│
       │                        │                          │
       │  Загружает PDF         │                          │
       │───────────────────────▶│  POST /api/analyze-resume│
       │                        │─────────────────────────▶│  pypdf → текст
       │                        │                          │  GPT-4o → навыки
       │                        │                          │  pymorphy3 → нормализация
       │                        │◀─────────────────────────│  [{name, level}]
       │                        │                          │
       │  Нажимает «Построить»  │                          │
       │───────────────────────▶│  POST /api/plan          │
       │                        │─────────────────────────▶│  scenario_handler
       │                        │                          │  → gap_analyzer
       │                        │                          │  → rag_service (контекст)
       │                        │                          │  → output_formatter
       │                        │                          │  → plan_generator (GPT-4o)
       │                        │◀─────────────────────────│  {markdown, analysis?, role_titles?}
       │                        │                          │
       │  Видит план развития   │                          │
       │◀───────────────────────│  ReactMarkdown + TOC     │
```

---

## Технологии

### Backend

| Технология | Версия | Назначение |
|---|---|---|
| Python | 3.12 | Основной язык бэкенда |
| FastAPI | ≥ 0.100 | REST API с автогенерацией OpenAPI-документации |
| Uvicorn | ≥ 0.22 | ASGI-сервер |
| Pydantic | v2 | Валидация запросов/ответов |
| pymorphy3 | ≥ 2.0 | Лемматизация русского языка (замена NLTK-стемминга) |
| Sentence-Transformers | ≥ 2.2 | Мультиязычные эмбеддинги для RAG |
| PyTorch | CPU | Runtime для Sentence-Transformers |
| pypdf | ≥ 3.0 | Извлечение текста из PDF |
| scikit-learn | ≥ 1.0 | Кластеризация навыков (KMeans) |
| OpenAI SDK | ≥ 1.0 | Взаимодействие с GPT-4o |
| bcrypt, PyJWT | — | Хеширование паролей, access/refresh JWT |
| SQLite (stdlib + `db.py`) | — | Пользователи, анализы, прогресс, сессии refresh |

### Frontend

| Технология | Версия | Назначение |
|---|---|---|
| React | 19 | UI-фреймворк с функциональными компонентами и хуками |
| TypeScript | 5.9 | Строгая типизация всего приложения |
| Vite | 7 | Сборщик с мгновенным HMR |
| Tailwind CSS | 4 | Utility-first стилизация с CSS-переменными для тем |
| React Markdown | 10 | Рендеринг Markdown-планов с поддержкой GFM |
| Recharts | 3 | Радар и визуализация gap-анализа |
| Lucide React | — | SVG-иконки (tree-shakeable) |
| React Dropzone | 15 | Drag-and-drop загрузка PDF |

### Внешние сервисы

| Сервис | Назначение | Обязательность |
|---|---|---|
| OpenAI GPT-4o | Парсинг резюме, генерация планов | Да |
| Qdrant Cloud | Векторная БД для RAG | Нет (деградация: нет семантических подсказок) |

### Инфраструктура

| Технология | Назначение |
|---|---|
| Docker (multi-stage) | Stage 1: Node.js собирает фронтенд. Stage 2: Python запускает бэкенд |
| Railway | Облачный хостинг с автодеплоем из `main` |

---

## Структура проекта

```
career-copilot/
│
├── api.py                          # FastAPI REST API + SPA-раздача
├── main.py                         # Gradio UI (альтернативный интерфейс)
├── config.py                       # Конфигурация и env-переменные
│
├── data_loader.py                  # Загрузка JSON-справочников, требования ролей
├── skill_normalizer.py             # Лемматизация (pymorphy3) + словарь синонимов
├── resume_parser.py                # PDF → текст → GPT-4o → навыки
├── rag_service.py                  # RAG: Qdrant + Sentence-Transformers
│
├── scenario_handler.py             # Маршрутизация трёх сценариев
├── next_grade_service.py           # Логика «Следующий грейд»
├── switch_profession_service.py    # Логика «Смена профессии»
├── explore_recommendations.py      # Логика «Исследование возможностей»
│
├── gap_analyzer.py                 # Gap-анализ: навыки vs требования
├── output_formatter.py             # Markdown-отчёт + вызов plan_generator
├── plan_generator.py               # Генерация плана 70/20/10 через GPT-4o
│
├── build_rag_index.py              # Скрипт построения RAG-индекса в Qdrant
│
├── data/
│   ├── clean_skills.json           # ~6 900 навыков с привязкой к профессиям
│   ├── atlas_params_clean.json     # Параметры карьерного роста по грейдам
│   └── skill_synonyms.json         # Словарь синонимов навыков
│
├── tests/
│   ├── test_skill_normalizer.py
│   ├── test_next_grade_service.py
│   ├── test_switch_profession_service.py
│   └── test_explore_recommendations.py
│
├── frontend/                       # React SPA
│   ├── src/
│   │   ├── main.tsx                # Точка входа: React 19 + ThemeProvider + ErrorBoundary
│   │   ├── App.tsx                 # Корневой компонент: состояние, навигация, persistence
│   │   │
│   │   ├── screens/
│   │   │   ├── PublicLanding.tsx   # Публичный лендинг
│   │   │   ├── Auth.tsx            # Регистрация / вход
│   │   │   ├── OnboardingQuiz.tsx  # Квиз после регистрации
│   │   │   ├── Dashboard.tsx       # Личный кабинет
│   │   │   ├── GoalSetup.tsx       # Профессия + сценарий + грейд
│   │   │   ├── Skills.tsx          # Ввод навыков (PDF / вручную / подсказки)
│   │   │   ├── Confirmation.tsx    # Проверка данных перед генерацией
│   │   │   ├── Result.tsx          # План + TOC + сохранение анализа
│   │   │   ├── GrowthPage.tsx      # UI сценария «Следующий грейд»
│   │   │   └── SwitchPage.tsx      # UI сценария «Смена профессии»
│   │   │
│   │   ├── components/
│   │   │   ├── SearchableSelect.tsx # Комбобокс с поиском для профессий
│   │   │   ├── SkillCard.tsx        # Карточка навыка с уровнем
│   │   │   ├── ScenarioCard.tsx     # Карточка сценария
│   │   │   ├── ErrorBoundary.tsx    # Перехват неожиданных ошибок
│   │   │   ├── Toast.tsx            # Toast-уведомления (undo и др.)
│   │   │   ├── toastStore.ts        # Глобальный store для toast-ов
│   │   │   ├── Skeleton.tsx         # Skeleton-загрузочные экраны
│   │   │   ├── FeedbackRating.tsx   # Оценка полезности плана
│   │   │   ├── ShareCard.tsx        # Шаринг результата по ссылке
│   │   │   ├── ProtectedRoute.tsx   # Защита маршрутов с авторизацией
│   │   │   ├── Alert.tsx            # Алерты (error/warning/info/success)
│   │   │   ├── Layout.tsx           # Обёртка: header + stepper + footer
│   │   │   ├── NavBar.tsx           # Логотип + переключатель темы
│   │   │   ├── Stepper.tsx          # Прогресс-индикатор (5 шагов)
│   │   │   ├── Spinner.tsx          # Индикатор загрузки
│   │   │   ├── MiniProgress.tsx     # Метка «Шаг N из M»
│   │   │   └── SoftOnboardingHint.tsx # Всплывающие подсказки
│   │   │
│   │   ├── auth/
│   │   │   └── AuthContext.tsx     # JWT access/refresh, persist в sessionStorage
│   │   ├── api/
│   │   │   └── client.ts           # API-клиент с AbortController + Bearer
│   │   │
│   │   ├── types/
│   │   │   └── index.ts            # TypeScript-типы: Skill, AppState, PlanRequest и др.
│   │   │
│   │   ├── theme.tsx               # ThemeProvider (dark/light)
│   │   ├── themeContext.ts         # React Context для темы
│   │   ├── useTheme.ts            # Хук для доступа к теме
│   │   └── index.css              # Tailwind + CSS-переменные + анимации
│   │
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── eslint.config.js
│
├── requirements.txt
├── Dockerfile
├── Procfile
└── docs/
    ├── ARCHITECTURE.md
    ├── TECHNICAL_DESCRIPTION.md
    └── DEPLOY_RAILWAY.md
```

---

## Быстрый старт

### Предварительные требования

- Python 3.12+
- Node.js 20+ (для сборки фронтенда)
- API-ключ OpenAI

### Установка

```bash
git clone https://github.com/superdash777/career_buid_sysytem.git
cd career_buid_sysytem

# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install && npm run build && cd ..
```

### Настройка

Создайте файл `.env` в корне проекта:

```env
OPENAI_API_KEY=sk-...

# Опционально (для RAG):
QDRANT_URL=https://xxx.qdrant.io
QDRANT_API_KEY=...
```

### Запуск

```bash
# REST API + React SPA
python api.py
# → http://localhost:8000

# Альтернативно: Gradio UI
python main.py
# → http://localhost:7860
```

### Docker

```bash
docker build -t career-copilot .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... career-copilot
```

На **Railway** в Dockerfile нельзя использовать `VOLUME` — диск подключается через **Railway Volumes**. Том на **`/app/data`** допустим: в образе дубликат справочников лежит в **`_data_shipped`**, приложение само подставит его, если том перекрыл `clean_skills.json`. SQLite по умолчанию: **`data/app.db`** (на том же томе при mount `/app/data`). Локально в Docker: `-e DB_PATH=/data/app.db -v copilot_db:/data`.

Compose с постоянной БД:

```bash
docker compose up --build
```

(в `docker-compose.yml` заданы `DB_PATH=/data/app.db` и именованный volume.)

**Важно для авторизации:** если контейнер каждый раз стартует с **пустой** SQLite, старый JWT из браузера остаётся валидным, а записи пользователя в новой базе нет — API вернёт 401 с кодом `USER_NOT_FOUND`. Нужен постоянный диск для `DB_PATH` или одна реплика с общим хранилищем.

---

## REST API

Документация доступна по адресу `http://localhost:8000/docs` (Swagger UI).

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/professions` | Список профессий |
| GET | `/api/skills-for-role?profession=...` | Навыки для профессии |
| GET | `/api/suggest-skills?q=...` | Подсказки навыков (синонимы + RAG) |
| POST | `/api/analyze-resume` | Загрузка PDF → список навыков |
| POST | `/api/plan` | Построение плана развития |
| POST | `/api/focused-plan` | Фокусный план по выбранным навыкам (JSON) |
| POST | `/api/auth/register` | Регистрация (email, пароль) → JWT |
| POST | `/api/auth/login` | Вход → JWT |
| POST | `/api/auth/refresh` | Обновление access по refresh |
| POST | `/api/auth/logout` | Отзыв refresh |
| GET | `/api/auth/me` | Текущий пользователь (Bearer) |
| PATCH | `/api/auth/onboarding` | Сохранение онбординга (Bearer) |
| GET | `/api/analyses` | Список сохранённых анализов (Bearer) |
| POST | `/api/analyses` | Сохранить результат анализа (Bearer) |
| GET | `/api/analyses/{id}` | Детали анализа (Bearer) |
| GET | `/api/share/{analysis_id}` | Публичный просмотр сохранённого результата |
| GET | `/api/progress` | Прогресс по навыкам (Bearer) |
| PATCH | `/api/progress` | Обновить статус навыка todo / in_progress / done (Bearer) |
| GET | `/health` | Health check |

### Пример: построение плана

```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "profession": "Product Manager",
    "grade": "Специалист (Middle)",
    "skills": [{"name": "SQL", "level": 1.5}, {"name": "Коммуникация", "level": 2}],
    "scenario": "Следующий грейд"
  }'
```

Ответ:

```json
{
  "markdown": "# План развития: Product Manager → Senior\n\n...",
  "role_titles": null,
  "analysis": { "...": "структура для UI (radar, skill_gaps, сценарий и т.д.)" }
}
```

Поле `analysis` присутствует, когда бэкенд сформировал структурированные данные для экранов Growth / Switch / Explore.

---

## Переменные окружения

| Переменная | Обязательно | По умолчанию | Описание |
|---|---|---|---|
| `OPENAI_API_KEY` | Да | — | Ключ OpenAI API |
| `QDRANT_URL` | Нет | — | URL Qdrant для RAG |
| `QDRANT_API_KEY` | Нет | — | API-ключ Qdrant |
| `RESUME_PARSER_MODEL` | Нет | `gpt-4o` | Модель для парсинга резюме |
| `RESUME_TEXT_MAX_CHARS` | Нет | `14000` | Лимит текста резюме |
| `RAG_COLLECTION_NAME` | Нет | `career_pathfinder_rag` | Название legacy-коллекции Qdrant (MiniLM fallback) |
| `EMBED_MODEL_NAME` | Нет | `paraphrase-multilingual-MiniLM-L12-v2` | Модель эмбеддингов для legacy/fallback |
| `SKILLS_V2_COLLECTION_NAME` | Нет | `skills_v2` | Новая коллекция канонических навыков (E5) |
| `EMBED_MODEL_NAME_V2` | Нет | `intfloat/multilingual-e5-large-instruct` | Модель эмбеддингов v2 для нормализации навыков |
| `PORT` | Нет | `8000` | Порт сервера |
| `DB_PATH` | Нет | `<корень проекта>/data/app.db` | SQLite; при томе на `/app/data` файл окажется на постоянном диске. Иначе можно абсолютный путь, например `/data/app.db` |
| `JWT_SECRET` | Нет | `change-me-in-production` | Секрет подписи JWT; в продакшене задайте свой |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | Нет | `4320` | Срок жизни access-токена (по умолчанию 3 суток) |
| `JWT_REFRESH_TOKEN_TTL_MINUTES` | Нет | `43200` | Срок жизни refresh-токена (по умолчанию 30 суток) |
| `AUTH_RATE_LIMIT_WINDOW_SEC` | Нет | `60` | Окно rate limit для auth |
| `AUTH_LOGIN_RATE_LIMIT` / `AUTH_REGISTER_RATE_LIMIT` | Нет | `10` | Макс. попыток логина / регистраций в окне |
| `PLAN_CONTEXT_MAX_CHARS` | Нет | `12000` | Лимит символов контекста для генератора плана |

Без Qdrant приложение работает полностью — не будет семантических подсказок навыков и семантического ранжирования ролей, но gap-анализ и генерация планов доступны.

---

## Данные

### Навыки (`data/clean_skills.json`)

Текущая версия датасета в репозитории содержит 534 записи. Каждый навык привязан к профессии и содержит описания трёх уровней владения:

- **Basic** — применяет в типовых ситуациях
- **Proficiency** — применяет в нестандартных ситуациях
- **Advanced** — может обучать других

### Атлас параметров (`data/atlas_params_clean.json`)

~10 метакомпетенций (автономность, масштаб задач, сложность, коммуникация). Для каждого параметра определены ожидания по пяти грейдам (Junior → Expert). Применяются ко всем профессиям
### Синонимы (`data/skill_synonyms.json`)

Словарь `{вариант: каноническое_название}`. Используется для нормализации: «питон» → «Python», «эксель» → «Excel».

---

## Тесты

```bash
pytest tests/ -v
```

Покрытие: нормализация навыков, сценарии (next grade, switch profession, explore), gap-анализ.

---

## Eval pipeline

Оценка качества пайплайна выполняется через `eval.py` на размеченном датасете
`eval_dataset.json` (50 примеров).

```bash
python3 eval.py --version v2 --verbose
```

Результат сохраняется в:

```text
eval_results/<timestamp>_<version>.json
```

### Threshold analysis (precision/recall curve)

```bash
python3 scripts/threshold_analysis.py --dataset eval_dataset.json
```

Скрипт прогоняет нормализацию при порогах `0.50..0.85` и сохраняет:
- CSV с метриками;
- PNG с precision-recall кривой.

---

## Деплой

Приложение деплоится на Railway с автодеплоем из ветки `main`. Подробности: [docs/DEPLOY_RAILWAY.md](docs/DEPLOY_RAILWAY.md).

Multi-stage Docker-сборка:
1. **Stage 1 (Node.js 20)** — `npm ci && npm run build` → статические файлы
2. **Stage 2 (Python 3.12)** — `pip install` + исходный код + собранный фронтенд

---

## Лицензия

Проект для учебных целей.
