# Архитектура Career Copilot

## 1. Обзор

Career Copilot — клиент-серверное веб-приложение, объединяющее NLP, семантический поиск (RAG) и генеративный AI для построения персонализированных планов карьерного развития.

Единый сервис: Python-бэкенд обслуживает REST API и раздаёт статические файлы React-фронтенда. Такой монолитный подход исключает необходимость в отдельном веб-сервере, настройке CORS между доменами или CDN.

---

## 2. Архитектурная схема

```
┌────────────────────────────────────────────────────────────────────────┐
│                         КЛИЕНТ (Браузер)                               │
│                                                                        │
│   React 19 · TypeScript 5.9 · Tailwind CSS 4 · Vite 7                │
│                                                                        │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│   │ Welcome  │→ │ GoalSetup│→ │  Skills  │→ │ Confirm  │→ │ Result │ │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│        ↑                                                        ↑     │
│        └────────── History API (browser back / forward) ────────┘     │
│                    sessionStorage (state persistence)                   │
│                                                                        │
│   UI-компоненты:                                                       │
│   SearchableSelect · SkillCard · ScenarioCard · Alert · Toast         │
│   Stepper · Skeleton · Spinner · ErrorBoundary · FeedbackRating       │
│   Layout · NavBar · MiniProgress · SoftOnboardingHint                 │
│                                                                        │
│   API-клиент: fetch + AbortController (отмена при размонтировании)    │
│                                                                        │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
                             │ HTTP (JSON / multipart/form-data)
                             │
┌────────────────────────────▼───────────────────────────────────────────┐
│                      FastAPI (api.py)                                   │
│                                                                        │
│   REST-эндпоинты:                   SPA Fallback:                      │
│   GET  /api/professions             /{path} → frontend/dist/index.html │
│   GET  /api/skills-for-role                                            │
│   GET  /api/suggest-skills                                             │
│   POST /api/analyze-resume                                             │
│   POST /api/plan                                                       │
│   GET  /health                                                         │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                       БИЗНЕС-ЛОГИКА                                    │
│                                                                        │
│  ┌───────────────────┐   ┌──────────────┐   ┌───────────────────────┐ │
│  │ scenario_handler  │   │ gap_analyzer │   │ output_formatter      │ │
│  │                   │   │              │   │                       │ │
│  │ Маршрутизация:    │──▶│ Сопоставление│──▶│ Markdown-отчёт       │ │
│  │ - next_grade      │   │ текущих      │   │ (диагностика +       │ │
│  │ - change_prof     │   │ навыков с    │   │  план 70/20/10)      │ │
│  │ - explore         │   │ требованиями │   │                       │ │
│  └───────┬───────────┘   └──────────────┘   └────────────┬──────────┘ │
│          │                                                │           │
│  ┌───────▼──────────────────────┐    ┌────────────────────▼─────────┐ │
│  │ Детализация сценариев:       │    │ plan_generator              │ │
│  │                              │    │                              │ │
│  │ next_grade_service           │    │ GPT-4o:                      │ │
│  │ → ожидания по грейду,       │    │ - промпт с ролью консультанта│ │
│  │   связи навык↔параметр      │    │ - сжатая диагностика         │ │
│  │                              │    │ - RAG-контекст               │ │
│  │ switch_profession_service    │    │ - retry с backoff            │ │
│  │ → baseline, пересечения,    │    │ - fallback при недоступности │ │
│  │   кластеризация треков      │    │                              │ │
│  │                              │    │ Выход: план в формате        │ │
│  │ explore_recommendations      │    │ 70% практика                 │ │
│  │ → closest / adjacent / far  │    │ 20% менторство               │ │
│  │   категоризация ролей       │    │ 10% обучение                 │ │
│  └──────────────────────────────┘    └──────────────────────────────┘ │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                       ДАННЫЕ И NLP                                     │
│                                                                        │
│  ┌───────────────┐   ┌──────────────────┐   ┌───────────────────────┐ │
│  │ data_loader   │   │ skill_normalizer │   │ rag_service           │ │
│  │               │   │                  │   │                       │ │
│  │ JSON →        │   │ 1. lower + trim  │   │ Sentence-Transformers │ │
│  │ skills_map    │   │ 2. опечатки      │   │ paraphrase-           │ │
│  │ atlas_map     │   │ 3. pymorphy3 (RU)│   │ multilingual-MiniLM   │ │
│  │ role_map      │   │    Snowball (EN) │   │ (384-dim embeddings)  │ │
│  │               │   │ 4. синонимы      │   │                       │ │
│  │ Методы:       │   │    (JSON-словарь)│   │ Qdrant REST API:      │ │
│  │ get_role_reqs │   │                  │   │ - suggest_skills      │ │
│  │ get_all_roles │   │ Цепочка          │   │ - map_to_canonical    │ │
│  │ get_skills_   │   │ ответственности  │   │ - rank_opportunities  │ │
│  │   for_role    │   │                  │   │ - get_rag_context     │ │
│  └───────────────┘   └──────────────────┘   └───────────────────────┘ │
│                                                                        │
│  ┌───────────────┐                                                    │
│  │ resume_parser │                                                    │
│  │               │                                                    │
│  │ 1. pypdf →    │                                                    │
│  │    текст      │                                                    │
│  │ 2. GPT-4o →   │                                                    │
│  │    навыки     │                                                    │
│  │    (JSON mode)│                                                    │
│  │ 3. pymorphy3 →│                                                    │
│  │    нормал-ция │                                                    │
│  └───────────────┘                                                    │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                       ХРАНЕНИЕ                                         │
│                                                                        │
│  Файловая система:                   Внешние сервисы:                  │
│  data/clean_skills.json (~6 900)     OpenAI GPT-4o (обязательно)       │
│  data/atlas_params_clean.json (~10)  Qdrant Cloud  (опционально)       │
│  data/skill_synonyms.json                                              │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Поток данных

### 3.1. Построение плана (основной сценарий)

```
Пользователь
    │
    ├── Выбирает профессию, сценарий, грейд  (GoalSetup)
    ├── Добавляет навыки                      (Skills)
    │   ├── Из PDF: resume_parser → GPT-4o → нормализация → [{name, level}]
    │   ├── Вручную: ввод + debounce → suggest_skills (синонимы + RAG)
    │   └── Из подсказок: fetchSkillsForRole → чипы быстрого добавления
    │
    ├── Подтверждает данные                    (Confirmation)
    │
    └── POST /api/plan
         │
         ├── 1. Нормализация навыков
         │   └── _skills_table_to_user_skills: float→int уровни + resolve_to_canonical
         │
         ├── 2. Маршрутизация сценария (scenario_handler)
         │   ├── «Следующий грейд»:    get_role_requirements(role, next_grade)
         │   ├── «Смена профессии»:    build_switch_comparison(skills, target, grade)
         │   └── «Исследование»:       explore_opportunities → rank_opportunities
         │
         ├── 3. Gap-анализ (gap_analyzer)
         │   └── Дельта по навыкам и атлас-параметрам, приоритеты, % соответствия
         │
         ├── 4. Форматирование (output_formatter)
         │   ├── Markdown-диагностика (шаг 1)
         │   └── Вызов plan_generator с RAG-контекстом (шаг 2)
         │
         └── 5. Ответ: {markdown, role_titles?}
```

### 3.2. Нормализация навыков (цепочка ответственности)

```
Пользовательский ввод
    │
    ├─ 1. Точное совпадение (lowercase) в словаре синонимов
    │     → найдено? → каноническое имя
    │
    ├─ 2. Нормализация текста:
    │     - lowercase, trim, collapse spaces
    │     - замена опечаток (питон → python, дата саенс → data science)
    │     - лемматизация слов:
    │       - русский → pymorphy3 (разработка→разработка, разработчик→разработка)
    │       - английский → Snowball stemmer (developing→develop)
    │     → нормализованная форма в словаре синонимов? → каноническое имя
    │
    ├─ 3. Перебор ключей словаря: normalize(key) == normalize(input)?
    │     → найдено? → каноническое имя
    │
    └─ 4. Не найдено → None (навык используется as-is)
```

### 3.3. RAG pipeline

```
build_rag_index.py (офлайн):
    clean_skills.json + atlas_params_clean.json
        │
        ├── Формирование текстовых описаний для каждого навыка/параметра
        ├── Sentence-Transformers → 384-dim embeddings
        └── Загрузка в Qdrant с metadata (тип, название, профессия)

Runtime (при запросах):
    Вход: текстовый запрос (навык / описание)
        │
        ├── Sentence-Transformers → embedding запроса
        ├── Qdrant: cosine similarity search (top_k, score_threshold)
        └── Результат: релевантные навыки / контекст для плана
```

---

## 4. Frontend-архитектура

### 4.1. Состояние и навигация

```
                     ┌─────────────────────┐
                     │     App.tsx          │
                     │                     │
                     │ state: AppState     │◄── sessionStorage (persist)
                     │ screen: Screen      │◄── History API (browser back)
                     │ plan: PlanResponse  │◄── sessionStorage (persist)
                     │                     │
                     │ update(patch)       │
                     │ reset()             │
                     │ setScreen(s)        │──▶ pushState / replaceState
                     └──────────┬──────────┘
                                │ props
          ┌─────────┬───────────┼───────────┬──────────┐
          ▼         ▼           ▼           ▼          ▼
     Welcome   GoalSetup    Skills    Confirmation  Result
```

**Persistence:** весь `AppState` сериализуется в `sessionStorage` при каждом изменении. При загрузке страницы восстанавливается из хранилища. F5 / случайный refresh не теряет прогресс.

**Навигация:** каждый переход записывает хэш (`#goal`, `#skills`, ...) через `history.pushState`. Событие `popstate` обрабатывает кнопку «Назад» браузера.

### 4.2. Компонентная иерархия

```
ErrorBoundary                    ← перехват непредвиденных ошибок
  └── ThemeProvider              ← dark/light тема (localStorage)
       └── App                   ← состояние + навигация
            ├── Welcome
            ├── GoalSetup
            │    ├── Layout (header + stepper + footer)
            │    ├── SearchableSelect (комбобокс профессий)
            │    ├── ScenarioCard × 3
            │    └── SkeletonForm (загрузка)
            ├── Skills
            │    ├── Layout
            │    ├── Dropzone (react-dropzone)
            │    ├── Combobox (input + suggestions dropdown)
            │    ├── SkillCard × N (с уровнем + удалением)
            │    └── SkillQualityBar (прогресс 0→7+)
            ├── Confirmation
            │    ├── Layout
            │    ├── Summary (dl/dt/dd)
            │    └── Expandable skills chips
            └── Result
                 ├── Layout (wide)
                 ├── ReactMarkdown + remarkGfm
                 ├── Desktop TOC (sticky sidebar)
                 ├── Mobile TOC (bottom sheet)
                 └── FeedbackRating
       └── ToastContainer          ← глобальные toast-уведомления
```

### 4.3. API-клиент

Все запросы проходят через централизованный `api/client.ts`:

- Generic `request<T>(url, init, signal)` с типизированными ответами
- `ApiError` класс с HTTP-статусом для дифференцированной обработки
- Каждая функция принимает опциональный `AbortSignal`
- Компоненты создают `AbortController` в `useEffect` и отменяют при unmount

### 4.4. Дизайн-система

**Темы:** CSS-переменные переключаются классом `.dark` на `<html>`. 12 токенов (surface, border, text, accent). Тема сохраняется в `localStorage`, при первой загрузке определяется из `prefers-color-scheme`.

**Компонентные классы (Tailwind `@layer components`):**
- `.btn-primary`, `.btn-secondary` — кнопки
- `.card` — карточки с тенью
- `.input-field` — поля ввода
- `.label`, `.helper` — подписи к полям

**Анимации:**
- `.fade-in` — плавное появление (opacity)
- `.slide-up` — появление снизу (translateY + opacity)
- `.skill-card-enter` — появление слева (translateX + scale)

---

## 5. Ключевые архитектурные решения

| Решение | Обоснование |
|---------|-------------|
| **Монолитный деплой** | Один сервис = один контейнер. Нет CORS, нет отдельного CDN. Подходит для MVP |
| **RAG вместо fine-tuning** | При обновлении данных достаточно переиндексировать Qdrant. Без затрат на переобучение модели |
| **pymorphy3 вместо NLTK Snowball** | Лемматизация точнее стемминга для русского языка. «разработка» и «разработчик» → одна лемма |
| **Ленивая загрузка ML** | Sentence-Transformers и PyTorch грузятся только при первом RAG-запросе. Ускоряет старт |
| **Qdrant через REST** | Без gRPC/protobuf — меньше зависимостей, меньший Docker-образ |
| **sessionStorage** | Состояние wizard-а переживает F5, но не переживает закрытие вкладки (приватность) |
| **History API** | Browser back/forward работает интуитивно. Нет тяжёлого React Router для линейного flow |
| **AbortController** | Отмена HTTP-запросов при быстрой навигации предотвращает race conditions |
| **Toast + undo** | Мгновенное удаление с возможностью отмены лучше модального подтверждения |

---

## 6. Ограничения и компромиссы

- Резюме обрезается до 14 000 символов перед отправкой в LLM
- Диагностика сжимается до ~1 000 символов перед передачей в plan_generator
- Ответ плана ограничен `max_tokens`; при ошибке API — retry с backoff, затем fallback
- Нет аутентификации и rate limiting (MVP)
- Нет i18n — интерфейс только на русском языке
