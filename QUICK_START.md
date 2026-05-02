# 🚀 Quick Start Guide

## Що ми щойно зробили?

### ✅ Завершено:

1. **MCP Server для пошуку статей** 
   - ArXiv Searcher (пошук на arXiv)
   - Semantic Scholar Client (цитування)
   - Paper Deduplicator (видалення дублів)
   - Request-based caching (SQLite)
   - 12 тестів - усі проходять ✓

2. **Telegram Bot**
   - Обробка повідомлень
   - Команди (/start, /help, /status)
   - Перевірка конфігурації
   - Інтеграція з дослідницьким агентом

3. **.env налаштування**
   - Шаблон з коментарями
   - Інструкції для отримання ключів
   - Перевірка конфігурації

---

## Крок за кроком: Запуск локально

### 1️⃣ Отримайте API ключі

#### Anthropic API Key:
- Перейти: https://console.anthropic.com/
- Sign in → API keys → Create Key
- Скопіювати

#### Telegram Bot Token:
- Знайти @BotFather на Telegram
- `/newbot` → дати ім'я → дати username
- Скопіювати token

### 2️⃣ Заповніть .env

```bash
# Відкрити .env
nano .env

# Заповніть:
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh

# Зберегти (Ctrl+X → y → Enter)
```

### 3️⃣ Запустіть бота

```bash
source .venv/bin/activate
python -m src.research_agent.bot
```

Очікуваний вивід:
```
============================================================
🤖 Research Agent Telegram Bot
============================================================

🔍 Перевірка конфігурації
============================================================
✅ ANTHROPIC_API_KEY: sk-ant-xxxxx
✅ TELEGRAM_BOT_TOKEN: 123456789:ABC...
============================================================
✅ Вся конфігурація готова!

🚀 Запускаю бота...

Bot is running. Press Ctrl+C to exit.
```

### 4️⃣ Тестуйте на Telegram

1. Знайти вашого бота за username (напр. @research_agent_bot)
2. Написати `/start`
3. Написати тестовий запит:
   ```
   Find papers on transformers
   ```

---

## Структура проекту

```
nlp_lab5/
├── .env                          # 🔑 Ваші API ключі (не комітити!)
├── .env.example                  # 📝 Шаблон .env
├── BOT_SETUP.md                  # 📖 Інструкція по боту
├── MCP_IMPLEMENTATION_SUMMARY.md # 📊 Резюме MCP сервера
├── verify_mcp.py                 # ✓ Перевірка MCP
│
├── mcp_literature_server/        # 🔬 Сервер для пошуку статей
│   ├── __init__.py
│   ├── __main__.py               # Запуск: python -m mcp_literature_server
│   ├── cache.py                  # SQLite кеш (request-based)
│   ├── literature_tools.py       # ArxivSearcher, SemanticScholarClient, Deduplicator
│   ├── research_server.py        # Сервер з 3 інструментами
│   ├── INTEGRATION.md            # Як підключити до агента
│   └── README.md                 # Документація
│
├── src/research_agent/           # 🤖 Дослідницький агент
│   ├── __init__.py
│   ├── bot.py                    # ⭐ НОВИЙ: Telegram бот
│   ├── state.py                  # ✓ Структурований стан
│   ├── graph.py                  # ✓ LangGraph топологія
│   ├── nodes.py                  # ✓ Вузли агента
│   ├── routing.py                # ✓ Логіка маршрутизації
│   ├── budgets.py                # ✓ Обмеження витрат
│   └── tool_contracts.py         # ✓ MCP контракти
│
├── docs/                         # 📚 Документація
│   ├── agent_spec.md             # ✓ Специфікація агента
│   ├── graph_design.md           # ✓ Дизайн графу
│   └── handoff.md                # ✓ Розподіл ролей
│
├── tests/                        # ✓ Тести
│   ├── test_literature_tools.py  # 12 тестів - усі проходять
│   └── test_routing.py
│
└── eval/                         # 📊 Оцінка (ще не заповнено)
    ├── tasks.example.json        # Приклад формату
    └── tasks.json                # ⏳ Потрібно 30+ завдань
```

---

## Архітектура

```
┌──────────────────────────────────────────────────┐
│          Telegram User                           │
└────────────────────┬─────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Telegram Bot        │ (bot.py)
        │  - /start, /help      │
        │  - обробка повідомлень│
        └────────────┬──────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Research Agent LangGraph       │
        ├────────────────────────────────┤
        │ 1. initialize_run              │
        │ 2. classify_task (LLM)         │
        │ 3. plan_search (LLM)           │
        │ 4. search_papers (MCP)         │
        │ 5. validate_evidence           │
        │ 6. write_answer (LLM)          │
        └────────────┬───────────────────┘
                     │
        ┌────────────▼──────────────────┐
        │   MCP Literature Server       │
        ├────────────────────────────────┤
        │ 1. search_arxiv()              │
        │ 2. get_semantic_scholar_paper()│
        │ 3. deduplicate_papers()        │
        └────────────┬───────────────────┘
                     │
        ┌────────────▼──────────────────┐
        │   External APIs + Cache       │
        ├────────────────────────────────┤
        │ • arXiv API                    │
        │ • Semantic Scholar API         │
        │ • SQLite Cache (.cache/)       │
        └────────────────────────────────┘
```

---

## Поточний стан

### ✅ Готово:
- [x] MCP Server (cache, literature tools, server)
- [x] Telegram Bot (структура, команди, обробка)
- [x] .env налаштування
- [x] 12 тестів MCP сервера (passing)
- [x] Документація (README, INTEGRATION, BOT_SETUP)

### ⏳ В процесі:
- [ ] Підключити LLM (Claude) в nodes.py
- [ ] Підключити MCP Server в search_papers()
- [ ] Тестувати проти живих API
- [ ] Evaluation set (30+ tasks)
- [ ] Ablation studies
- [ ] Final report

---

## Команди для роботи

### Запуск MCP Server (окремо для тестування):
```bash
python -m mcp_literature_server --cache-dir /tmp/cache
```

### Запуск Telegram Bot:
```bash
python -m src.research_agent.bot
```

### Тестування MCP:
```bash
python -m pytest tests/test_literature_tools.py -v
```

### Перевірка конфігурації:
```bash
python verify_mcp.py
```

---

## Наступні кроки

### Для вас (Participant 2 - MCP):
1. Отримайте Anthropic API Key
2. Заповніть .env файл
3. Запустіть бота (для демонстрації)
4. Протестуйте MCP проти живих API
5. Оптимізуйте кеш для evaluation

### Для Participant 3 (Evaluation):
1. Створіть 30+ tasks в eval/tasks.json
2. Реалізуйте дослідницький агент
3. Збирайте траєкторії
4. Запустіть абляції
5. Напишіть звіт

---

## Проблеми?

### ❌ "ModuleNotFoundError"
```bash
pip install -e ".[bot,agent,mcp,dev]"
```

### ❌ "ANTHROPIC_API_KEY not found"
1. Перевіріть .env файл існує
2. Заповніть справжніми ключами (не `YOUR_KEY_HERE`)
3. Перезапустіть бота

### ❌ "Telegram connection refused"
Переконайтеся:
- [ ] Інтернет-з'єднання активне
- [ ] Token скопійований правильно (без пробілів)
- [ ] Бот поки що працює локально

---

## Резюме

Ви тепер маєте:
- ✅ MCP Server для пошуку наукових статей
- ✅ Telegram Bot для інтерактивної демонстрації
- ✅ Кешування для швидкості
- ✅ 3 літературних інструменти (ArXiv, Semantic Scholar, Deduplication)
- ✅ Обробка помилок з розрізненням retriable/non-retriable

**Наступна фаза:** Підключити до LangGraph агента та LLM!

🚀 Готові продовжити?
