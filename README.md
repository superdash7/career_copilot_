# CareerCopilot 

**Персональный навигатор карьерного роста на основе AI**

Анализ навыков → План карьерного развития → Отслеживание прогресса

***Ссылка на приложение:*** https://careerbuidsysytem-production.up.railway.app/#public

https://github.com/user-attachments/assets/87e988e8-8892-4c17-94b9-99c8b67e0032

---

## Что это

Career Copilot — веб-приложение, которое помогает специалистам построить индивидуальный план карьерного развития. Система сопоставляет текущие навыки пользователя с требованиями целевой роли, определяет зоны роста и генерирует конкретные шаги по модели 70/20/10 (практика / менторство / обучение).

После генерации плана пользователь может сохранить результат в **личный кабинет**, где доступны:
- **История анализов** — все ранее построенные планы с возможностью вернуться к любому
- **Kanban-доска** — задачи из плана развития с колонками «К выполнению → В работе → Выполнено»

Кроме того, в сервисе есть **лендинг-страница для HR-специалистов и руководителей команд**, через которую они могут запросить информацию о продукте, а сервсис получает контакты потенциальных лидов.

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
│  1. Регистрируется или входит в систему                     │
│  2. Выбирает профессию и сценарий                           │
│  3. Добавляет навыки (из резюме PDF или вручную)            │
│  4. Получает персональный план развития                      │
│  5. Сохраняет план в личный кабинет                          │
│  6. Отслеживает прогресс на kanban-доске                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Backend Pipeline ──────────────────────────────────────────┐
│                                                              │
│  Авторизация (JWT access/refresh + bcrypt)                  │
│       ↓                                                      │
│  Нормализация навыков (pymorphy3 + синонимы)                │
│       ↓                                                      │
│  Подбор требований роли из справочника                       │
│       ↓                                                      │
│  Gap-анализ: текущий уровень vs требуемый                   │
│       ↓                                                      │
│  Обогащение контекстом через RAG (Qdrant)                   │
│       ↓                                                      │
│  Генерация плана через GPT-4o (модель 70/20/10)             │
│       ↓                                                      │
│  Сохранение в SQLite (анализы, прогресс, история)           │
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
│   PublicLanding · Auth · Onboarding                                    │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│   │ GoalSetup│→ │  Skills  │→ │ Confirm  │→ │ Result   │  │Growth/ │ │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  │Switch  │ │
│        ↑              ↑             ↑              ↑       │   UI   │ │
│        └──────── History API (browser back/forward)─┘       └────────┘ │
│                  sessionStorage (persist on refresh)                    │
│                                                                        │
│   Dashboard (Личный кабинет):                                         │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│   │ История      │  │ Kanban-доска │  │ Radar-chart самооценки   │   │
│   │ анализов     │  │ задач плана  │  │ (Growth / Switch)        │   │
│   │              │  │              │  │                          │   │
│   │ GET /api/    │  │ todo →       │  │ Визуализация текущих     │   │
│   │ analyses     │  │ in_progress →│  │ vs целевых навыков       │   │
│   │              │  │ done         │  │                          │   │
│   └──────────────┘  └──────────────┘  └──────────────────────────┘   │
│                                                                        │
│   AuthContext (JWT) · ProtectedRoute · ShareCard                       │
│   Компоненты: SearchableSelect · SkillCard · ScenarioCard · Toast    │
│               KanbanBoard · Stepper · Skeleton · ErrorBoundary       │
│                                                                        │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
                             │  HTTP (JSON / multipart)
                             │  AbortController для отмены запросов
                             │
┌────────────────────────────▼───────────────────────────────────────────┐
│                      FastAPI (api.py) — 20 эндпоинтов                  │
│                                                                        │
│   REST API                         Авторизация & данные пользователя  │
│   ├─ GET  /api/professions         POST /api/auth/register · login     │
│   ├─ GET  /api/skills-for-role     POST /api/auth/refresh · logout    │
│   ├─ GET  /api/skills-by-category  GET  /api/auth/me                  │
│   ├─ GET  /api/suggest-skills      PATCH /api/auth/onboarding         │
│   ├─ POST /api/analyze-resume      GET|POST /api/analyses · GET/{id}  │
│   ├─ POST /api/plan                GET|PATCH /api/progress            │
│   ├─ POST /api/focused-plan        GET /api/share/{analysis_id}       │
│   └─ GET  /health                  /{path} → frontend/dist/index.html │
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
│   JSON-справочники (data/)          SQLite (db.py):                   │
│   534 навыка · 7 параметров ·       ┌─────────────────────────┐      │
│   358 синонимов                     │ users — пользователи    │      │
│                                     │ analyses — история      │      │
│                                     │ progress — kanban-статус│      │
│                                     │ refresh_tokens — сессии │      │
│                                     └─────────────────────────┘      │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                     ВНЕШНИЕ СЕРВИСЫ                                     │
│                                                                        │
│   ┌──────────────────────┐       ┌──────────────────────────────┐     │
│   │  OpenAI API          │       │  Qdrant Cloud                │     │
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
       │  Регистрация / вход    │                          │
       │───────────────────────▶│  POST /api/auth/register │
       │                        │─────────────────────────▶│  bcrypt → SQLite
       │                        │◀─────────────────────────│  JWT access + refresh
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
       │                        │◀─────────────────────────│  {markdown, analysis?}
       │                        │                          │
       │  Видит план развития   │                          │
       │◀───────────────────────│  ReactMarkdown + TOC     │
       │                        │                          │
       │  Сохраняет анализ      │                          │
       │───────────────────────▶│  POST /api/analyses      │
       │                        │─────────────────────────▶│  SQLite: сохранить
       │                        │◀─────────────────────────│  {id, scenario, result}
       │                        │                          │
       │  Открывает дашборд     │                          │
       │───────────────────────▶│  GET /api/analyses       │
       │                        │  GET /api/progress       │
       │                        │─────────────────────────▶│  SQLite: история + статусы
       │                        │◀─────────────────────────│
       │                        │                          │
       │  Двигает задачу        │                          │
       │  на kanban-доске       │                          │
       │───────────────────────▶│  PATCH /api/progress     │
       │                        │─────────────────────────▶│  todo → in_progress → done
       │                        │◀─────────────────────────│
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
| Recharts | 3 | Radar-chart и визуализация gap-анализа |
| Lucide React | — | SVG-иконки (tree-shakeable) |
| React Dropzone | 15 | Drag-and-drop загрузка PDF |

### Внешние сервисы

| Сервис | Назначение 
|---|---|
| OpenAI GPT-4o | Парсинг резюме, генерация планов | 
| Qdrant Cloud | Векторная БД для RAG | 

### Инфраструктура

| Технология | Назначение |
|---|---|
| Docker (multi-stage) | Stage 1: Node.js собирает фронтенд. Stage 2: Python запускает бэкенд |
| Railway | Облачный хостинг с автодеплоем |

---

## Структура проекта

```
career-copilot/
│
├── api.py                          # FastAPI REST API (20 эндпоинтов) + SPA-раздача
├── main.py                         # Gradio UI (альтернативный интерфейс)
├── config.py                       # Конфигурация и env-переменные
├── db.py                           # SQLite: users, analyses, progress, refresh_tokens
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
├── gap_analyzer.py                 # Gap-анализ: навыки vs требования роли
├── output_formatter.py             # Markdown-отчёт + вызов plan_generator
├── plan_generator.py               # Генерация плана 70/20/10 через GPT-4o
├── confidence_utils.py             # Индикаторы уверенности распознавания навыков
│
├── build_rag_index.py              # Скрипт построения RAG-индекса в Qdrant
├── eval.py                         # Оценка качества пайплайна (50 примеров)
│
├── data/
│   ├── clean_skills.json           # 534 навыка (1 600+ описаний по 3 уровням)
│   ├── atlas_params_clean.json     # 7 параметров карьерного роста по 5 грейдам
│   └── skill_synonyms.json         # 358 синонимов для нормализации навыков
│
├── tests/                          # 12 тестовых модулей (pytest)
│   ├── test_skill_normalizer.py
│   ├── test_next_grade_service.py
│   ├── test_switch_profession_service.py
│   ├── test_explore_recommendations.py
│   ├── test_plan_generator.py
│   ├── test_rag_hybrid.py
│   ├── test_resume_pipeline_v2.py
│   ├── test_weighted_gap_scoring.py
│   ├── test_eval_metrics.py
│   ├── test_rate_limiter.py
│   ├── test_auth_config.py
│   └── test_api_auth_user_not_found.py
│
├── frontend/                       # React SPA
│   ├── src/
│   │   ├── main.tsx                # Точка входа: React 19 + ThemeProvider + ErrorBoundary
│   │   ├── App.tsx                 # Корневой компонент: состояние, навигация, persistence
│   │   │
│   │   ├── screens/
│   │   │   ├── PublicLanding.tsx   # Публичный лендинг
│   │   │   ├── Auth.tsx            # Регистрация / вход (GDPR-согласие)
│   │   │   ├── OnboardingQuiz.tsx  # Квиз после регистрации
│   │   │   ├── Dashboard.tsx       # Личный кабинет (история + kanban + прогресс)
│   │   │   ├── GoalSetup.tsx       # Профессия + сценарий + грейд
│   │   │   ├── Skills.tsx          # Ввод навыков (PDF / вручную / подсказки)
│   │   │   ├── Confirmation.tsx    # Проверка данных перед генерацией
│   │   │   ├── Result.tsx          # План + TOC + сохранение анализа
│   │   │   ├── GrowthPage.tsx      # UI сценария «Следующий грейд» + radar-chart
│   │   │   ├── SwitchPage.tsx      # UI сценария «Смена профессии» + radar-chart
│   │   │   └── HRLanding.tsx       # Лендинг для HR / команд
│   │   │
│   │   ├── components/
│   │   │   ├── KanbanBoard.tsx      # Kanban-доска: drag & drop задач плана
│   │   │   ├── FocusedPlanSection.tsx # Фокусный план по выбранным навыкам
│   │   │   ├── SearchableSelect.tsx # Бокс с поиском для профессий
│   │   │   ├── SkillCard.tsx        # Карточка навыка с уровнем
│   │   │   ├── ScenarioCard.tsx     # Карточка сценария
│   │   │   ├── ShareCard.tsx        # Шаринг результата по ссылке
│   │   │   ├── ProtectedRoute.tsx   # Защита маршрутов с авторизацией
│   │   │   ├── LegalModal.tsx       # Модальные окна политики и согласия
│   │   │   ├── LoadingCarousel.tsx  # Карусель подсказок во время загрузки
│   │   │   ├── ErrorBoundary.tsx    # Перехват неожиданных ошибок
│   │   │   ├── Toast.tsx            # Toast-уведомления
│   │   │   ├── toastStore.ts        # Глобальный store для toast-ов
│   │   │   ├── Alert.tsx            # Алерты (error/warning/info/success)
│   │   │   ├── Layout.tsx           # Обёртка: header + stepper + footer
│   │   │   ├── NavBar.tsx           # Логотип + навигация + переключатель темы
│   │   │   ├── Stepper.tsx          # Прогресс-индикатор шагов
│   │   │   ├── Skeleton.tsx         # Загрузочные экраны
│   │   │   ├── MiniProgress.tsx     # Метка «Шаг N из M»
│   │   │   └── SoftOnboardingHint.tsx # Всплывающие подсказки
│   │   │
│   │   ├── auth/
│   │   │   └── AuthContext.tsx     # JWT access/refresh, persist в sessionStorage
│   │   ├── api/
│   │   │   └── client.ts           # API-клиент с AbortController + Bearer
│   │   ├── types/
│   │   │   └── index.ts            # TypeScript-типы: Skill, AppState, PlanRequest и др.
│   │   ├── legal/
│   │   │   └── legalFullTexts.ts   # Тексты политики конфиденциальности и согласия
│   │   ├── navigation/
│   │   │   └── goToDashboardContext.tsx # Контекст навигации в личный кабинет
│   │   ├── styles/
│   │   │   ├── tokens.css          # CSS-переменные дизайн-системы
│   │   │   └── typography.css      # Типографика
│   │   ├── utils/
│   │   │   ├── onboarding.ts       # Утилиты онбординга
│   │   │   └── profileAnalysisNotify.ts # Desktop-уведомления о готовности анализа
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
├── scripts/
│   ├── reindex_qdrant.py           # Переиндексация RAG-базы
│   └── threshold_analysis.py       # Precision/recall анализ порогов
│
├── requirements.txt                # Полный набор зависимостей
├── requirements-docker.txt         # Минимальный набор для Docker / Railway
├── Dockerfile
├── docker-compose.yml
├── railway.toml
├── Procfile
├── .github/
│   └── workflows/
│       └── docker-ghcr.yml        # CI: сборка Docker-образа → GHCR
│
└── docs/
    ├── ARCHITECTURE.md              # Архитектура системы
    ├── TECHNICAL_DESCRIPTION.md     # Техническое описание проекта
    ├── SYSTEM_DESCRIPTION_ISO24765.md # Описание системы по ISO/IEC/IEEE 24765
    ├── DIPLOMA_NLP_LLM_RAG_REPORT.md # Отчёт: NLP + LLM + RAG методология
    └── DEPLOY_RAILWAY.md            # Инструкция по деплою на Railway
```

---

## REST API
.

| Метод | Путь | Описание |
|---|---|---|
| **Данные** | | |
| GET | `/api/professions` | Список профессий |
| GET | `/api/skills-for-role?profession=...` | Навыки для профессии |
| GET | `/api/skills-by-category` | Навыки, сгруппированные по категориям |
| GET | `/api/suggest-skills?q=...` | Подсказки навыков (синонимы + RAG) |
| **Анализ** | | |
| POST | `/api/analyze-resume` | Загрузка PDF → список навыков |
| POST | `/api/plan` | Построение плана развития |
| POST | `/api/focused-plan` | Фокусный план по выбранным навыкам |
| **Авторизация** | | |
| POST | `/api/auth/register` | Регистрация (email, пароль) → JWT |
| POST | `/api/auth/login` | Вход → JWT |
| POST | `/api/auth/refresh` | Обновление access по refresh |
| POST | `/api/auth/logout` | Отзыв refresh-токена |
| GET | `/api/auth/me` | Текущий пользователь (Bearer) |
| PATCH | `/api/auth/onboarding` | Сохранение результатов онбординга (Bearer) |
| **Личный кабинет** | | |
| GET | `/api/analyses` | Список сохранённых анализов (Bearer) |
| POST | `/api/analyses` | Сохранить результат анализа (Bearer) |
| GET | `/api/analyses/{id}` | Детали анализа (Bearer) |
| GET | `/api/share/{analysis_id}` | Публичный просмотр результата |
| **Прогресс** | | |
| GET | `/api/progress` | Прогресс по навыкам (Bearer) |
| PATCH | `/api/progress` | Обновить статус: todo → in_progress → done (Bearer) |
| **Системные** | | |
| GET | `/health` | Health check |

---

## Данные

### Навыки (`data/clean_skills.json`)

1600 записей. Каждый навык содержит описания трёх уровней владения:

- **Basic** — применяет в типовых ситуациях
- **Proficiency** — применяет в нестандартных ситуациях
- **Advanced** — может обучать других

Итого **1 600+ описаний индикаторов компетенций** + примеры задач на развитие для каждого уровня.

### Атлас параметров (`data/atlas_params_clean.json`)

7 метакомпетенций (автономность, масштаб влияния, сложность задач, коммуникации, управление людьми, готовность расти, влияние на стратегию). Для каждого параметра определены ожидания по пяти грейдам (Junior → Expert).

---

## Деплой

Приложение деплоится на Railway с автодеплоем из ветки `main`. Подробности: [docs/DEPLOY_RAILWAY.md](docs/DEPLOY_RAILWAY.md). 

Multi-stage Docker-сборка:
1. **Stage 1 (Node.js 20)** — `npm ci && npm run build` → статические файлы
2. **Stage 2 (Python 3.12)** — `pip install` + исходный код + собранный фронтенд
