# 🤖 Telegram Bot для Research Agent

Telegram bot, що дозволяє користувачам інтерактивно запитувати про наукові статті.

## Швидкий старт

### 1. Установка залежностей

```bash
pip install -e ".[bot,agent,mcp]"
```

### 2. Налаштування .env файлу

```bash
cp .env.example .env
```

Заповніть обов'язкові значення:

```env
# Обов'язково!
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh

# Опціонально (для безпеки)
TELEGRAM_USER_ID=987654321
```

### 3. Запуск бота

```bash
python -m src.research_agent.bot
```

Очікуваний вивід:
```
============================================================
🤖 Research Agent Telegram Bot
============================================================

🔍 Перевірка конфігурації
============================================================
✅ ANTHROPIC_API_KEY: sk-ant-...xxxxx
✅ TELEGRAM_BOT_TOKEN: 123456789:ABC...fgh
============================================================

🚀 Запускаю бота...

Bot is running. Press Ctrl+C to exit.
```

---

## Як отримати APIKeys

### Anthropic API Key

1. Перейти на https://console.anthropic.com/
2. Sign in або створити account
3. Перейти в **API keys** → **Create Key**
4. Скопіювати ключ та вставити в `.env`:
   ```env
   ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
   ```

### Telegram Bot Token

1. Знайти **@BotFather** на Telegram
2. Написати `/newbot`
3. Дати ім'я боту (напр. "ResearchAgentBot")
4. Дати username (має бути унікальний, напр. "research_agent_bot")
5. BotFather надасть token, напр:
   ```
   Use this token to access the HTTP API: 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh
   ```
6. Вставити в `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh
   ```

### Telegram User ID (опціонально)

Щоб обмежити доступ тільки вам:

1. Напишіть **@userinfobot** на Telegram
2. Bot поверне ваш User ID
3. Вставити в `.env`:
   ```env
   TELEGRAM_USER_ID=987654321
   ```

---

## Інтеграція з Research Agent

### Поточний стан

- ✅ Telegram bot структура
- ✅ Обробка повідомлень
- ⏳ Підключення до LangGraph агента

### Що потрібно зробити

У файлі `src/research_agent/bot.py` функція `handle_message()` на даний момент повертає placeholder.

Щоб підключити справжній агент:

```python
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... existing code ...
    
    try:
        from src.research_agent.graph import build_graph
        from mcp_literature_server.research_server import ResearchAgentServer
        
        # Initialize MCP server
        mcp_server = ResearchAgentServer()
        
        # Build agent
        agent = build_graph(checkpointer=None)
        
        # Run agent
        result = await agent.ainvoke({
            "user_question": user_message,
        })
        
        # Format and send result
        response_text = result.get("final_answer", "❌ No response")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        response_text = f"❌ Error: {e}"
```

---

## Команди

### /start
Вітання та інструкції

### /help
Детальна довідка про використання

### /status
Статус бота та всіх компонентів

### Звичайні повідомлення
Запити про статті:
- "Find top 3 cited papers on transformers after 2020"
- "Find papers that support the claim about attention"
- "Compare BERT and RoBERTa papers"

---

## Приклад використання

### Користувач пише:
```
Find the 3 most-cited papers on retrieval-augmented generation published after 2020
```

### Бот відповідає:
```
🔍 Шукаю статті...
• Шукаю в arXiv
• Перевіряю цитування
• Дедубліцирую результати
• Готую відповідь

⏳ Це може зайняти 30-60 секунд...
```

### Результат:
```
🔬 **Research Results**

**Top 3 Most-Cited Papers on RAG (after 2020):**

1️⃣ **"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"**
   - Authors: Patrick Lewis, Ethan Perez, Aleksandra Piktus, ...
   - Year: 2020
   - Citations: 4,532
   - arXiv: 2005.11401
   - Abstract: We explore adding non-parametric memory to language models...

2️⃣ **"Dense Passage Retrieval for Open-Domain Question Answering"**
   - Authors: Vladimir Karpukhin, Barlas Oğuz, Sewon Min, ...
   - Year: 2020
   - Citations: 2,145
   - arXiv: 2004.04906
   - Abstract: Open-domain question answering relies on efficient passage retrieval...

3️⃣ **"Realm: Retrieval-Augmented Language Model Pre-Training"**
   - Authors: Kelvin Guu, Kenton Lee, Zora Tun, Panupong Pasupat, Ming-Wei Chang
   - Year: 2020
   - Citations: 1,876
   - arXiv: 2002.08909
   - Abstract: Language model pre-training has been shown to be effective...

✅ All results grounded in arXiv + Semantic Scholar
```

---

##架構

```
User (Telegram)
    ↓
[Telegram Bot]
    ↓
[Research Agent LangGraph]
    ├─→ classify_task (LLM: Claude)
    ├─→ plan_search (LLM: Claude)
    ├─→ search_papers (MCP: ArXiv + Semantic Scholar)
    ├─→ validate_evidence
    └─→ write_answer (LLM: Claude)
    ↓
[Telegram Bot] ← sends response
    ↓
User sees results
```

---

## Налаштування для Telegram Desktop / Web

Якщо ви тестуєте на Telegram Desktop, вам може знадобитися:

1. Встановіть Telegram Desktop з https://desktop.telegram.org/
2. Знайдіть вашого бота за username (напр. @research_agent_bot)
3. Напишіть йому `/start`

---

## Troubleshooting

### ❌ "ModuleNotFoundError: No module named 'telegram'"
```bash
pip install -e ".[bot]"
```

### ❌ "TELEGRAM_BOT_TOKEN not found"
```bash
# Перевірте .env файл
cat .env | grep TELEGRAM_BOT_TOKEN

# Напевно значення пусто - заповніть його
```

### ❌ "Connection refused"
Переконайтеся що bot правильно має доступ до Telegram API (інтернет-з'єднання).

### ⏳ "Bot doesn't respond"
1. Перевірте логи (має бути в stdout)
2. Переконайтеся що `build_graph()` повертає агент
3. Перевірте MCP Server працює

---

## Testing

### Без Telegram (тестувати логіку)

```bash
python -c "from src.research_agent.bot import check_env; check_env()"
```

### З Telegram

1. Запустіть бота: `python -m src.research_agent.bot`
2. Знайдіть бота на Telegram
3. Напишіть `/start`
4. Напишіть тестовий запит

---

## Наступні кроки

1. ✅ Bot структура готова
2. ⏳ Підключити LangGraph агента
3. ⏳ Підключити MCP Server
4. ⏳ Тестувати проти реальних запитів
5. ⏳ Оптимізувати траєкторії та метрики

Дивіться [INTEGRATION.md](mcp_literature_server/INTEGRATION.md) для деталей підключення.
