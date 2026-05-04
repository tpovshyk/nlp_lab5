"""Telegram bot for Track A Research Agent.

Usage:
  python -m src.research_agent.bot

The bot will:
  1. Listen for messages on Telegram
  2. Run the research agent on each query
  3. Return results with paper metadata and citations
"""

import os
import logging
from typing import Optional
import json
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, Message
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


TELEGRAM_MAX_LEN = 4096


def _split_for_telegram(text: str, limit: int = 4000) -> list[str]:
    """Split a long message on line boundaries so Markdown pairs aren't cut.

    Greedy: pack as many full lines as fit per chunk; emit partial only if a
    single line is itself longer than the limit.
    """
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for line in text.split("\n"):
        added = len(line) + 1
        if buf_len + added > limit and buf:
            chunks.append("\n".join(buf))
            buf, buf_len = [], 0
        if added > limit:
            # one absurdly long line - hard-split it
            for i in range(0, len(line), limit):
                chunks.append(line[i : i + limit])
            continue
        buf.append(line)
        buf_len += added
    if buf:
        chunks.append("\n".join(buf))
    return chunks


async def _safe_reply(message: Message, text: str) -> None:
    """Reply with Markdown; on parse failure retry without parse_mode."""
    for chunk in _split_for_telegram(text):
        try:
            await message.reply_text(chunk, parse_mode="Markdown")
        except BadRequest as exc:
            if "parse" not in str(exc).lower():
                raise
            logger.warning("Markdown parse failed (%s); retrying as plain text", exc)
            await message.reply_text(chunk)

# Load environment variables
load_dotenv()

# Get API keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ResearchAgentBot:
    """Telegram bot for research agent queries."""

    def __init__(self):
        """Initialize the bot."""
        self.allowed_user_id = None
        if TELEGRAM_USER_ID:
            try:
                self.allowed_user_id = int(TELEGRAM_USER_ID)
                logger.info(f"Bot restricted to user ID: {self.allowed_user_id}")
            except ValueError:
                logger.warning("Invalid TELEGRAM_USER_ID in .env")

        # Build the LangGraph agent once at startup so each request reuses it.
        from research_agent.graph import build_graph
        self.agent = build_graph()
        logger.info("Research agent graph compiled and ready")

        # Initialize the application
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self.app.add_error_handler(self._on_error)

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Swallow benign Telegram errors so they don't dump full tracebacks."""
        err = context.error
        if isinstance(err, Forbidden):
            logger.warning("Skipped a chat that blocked the bot: %s", err)
            return
        if isinstance(err, BadRequest):
            logger.warning("Telegram BadRequest: %s", err)
            return
        logger.exception("Unhandled bot error", exc_info=err)

    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot."""
        if self.allowed_user_id is None:
            return True  # No restriction
        return user_id == self.allowed_user_id

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("❌ У вас нема доступу до цього бота.")
            return

        welcome_text = """
🔬 **Research Agent Bot** 🔬

Я допомагаю знаходити наукові статті за запитом.

**Приклади запитів:**
- "Find top 3 cited papers on transformers after 2020"
- "Find papers that support the claim about attention mechanisms"
- "Compare papers on BERT and RoBERTa"

**Команди:**
/help - Допомога
/status - Статус бота

Просто напишіть ваше питання і я пошукаю відповідні статті! 📚
"""
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("❌ У вас нема доступу до цього бота.")
            return

        help_text = """
📖 **Як користуватися:**

1️⃣ **Напишіть питання** про наукові статті
   Приклад: "Find papers on retrieval-augmented generation"

2️⃣ **Чекайте результат** - агент буде шукати статті
   - Пошук в arXiv
   - Проверка цитувань в Semantic Scholar
   - Дедублікація результатів

3️⃣ **Отримайте результат** з:
   - Назвами статей
   - Авторами
   - Роками публікації
   - arXiv ID або DOI
   - Кількістю цитувань

⏱️ **Час очікування:** ~30-60 секунд

❓ **Типи запитів:**
- "Find N most-cited papers on [topic]"
- "Find papers that [support/contradict] the claim"
- "Compare papers on X and Y"
- "Give literature review on [topic]"

📝 **Примітка:** Агент відповідає тільки на основі даних з arXiv і Semantic Scholar.
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("❌ У вас нема доступу до цього бота.")
            return

        status_text = """
✅ **Bot Status**

🟢 Telegram Bot: **Running**
🟢 Research Agent: **Ready**
🟢 MCP Server: **Ready**
🟢 API Cache: **Active**

📊 **Configuration:**
- Model: Claude 3.5 Sonnet
- Cache: SQLite
- Rate limit: Respected

Ready to process queries!
"""
        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages with research queries."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("❌ У вас нема доступу до цього бота.")
            return

        user_message = update.message.text
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        logger.info(f"Query from @{username} (ID: {user_id}): {user_message}")

        # Send "typing" indicator
        await update.message.chat.send_action("typing")

        try:
            # Send processing message
            processing_msg = await update.message.reply_text(
                "🔍 Шукаю статті...\n\n"
                "• Шукаю в arXiv\n"
                "• Перевіряю цитування\n"
                "• Дедубліцирую результати\n"
                "• Готую відповідь\n\n"
                "⏳ Це може зайняти 30-60 секунд..."
            )

            # Invoke the pre-built agent graph
            result = self.agent.invoke({"user_question": user_message})

            # Delete the "processing" message
            await processing_msg.delete()

            # Send the result
            response_text = result.get("final_answer", "❌ No response from agent")
            await _safe_reply(update.message, response_text)

            # Log successful query
            logger.info(f"✓ Query processed successfully for @{username}")

        except Exception as e:
            logger.error(f"❌ Error processing query: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ **Помилка:** {str(e)}\n\n"
                "Спробуйте пізніше або звʼяжіться з розробником.",
                parse_mode="Markdown",
            )


def check_env() -> bool:
    """Check if all required environment variables are set."""
    print("\n" + "=" * 60)
    print("🔍 Перевірка конфігурації")
    print("=" * 60)

    checks = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    }

    all_ok = True
    for key, value in checks.items():
        if value and len(value) > 5:
            status = "✅"
            display = value[:10] + "..." + value[-5:]
        else:
            status = "❌"
            display = "NOT SET"
            all_ok = False

        print(f"{status} {key}: {display}")

    print("=" * 60)

    if all_ok:
        print("✅ Вся конфігурація готова!\n")
    else:
        print("❌ Заповніть відсутні значення в .env файлі\n")

    return all_ok


def main():
    """Main entry point for the bot."""
    print("\n" + "=" * 60)
    print("🤖 Research Agent Telegram Bot")
    print("=" * 60)

    # Check configuration
    if not check_env():
        print("❌ Конфігурація неповна. Виходимо...")
        return

    # Initialize and start bot
    print("🚀 Запускаю бота...\n")
    bot = ResearchAgentBot()

    # Start the bot (run_polling is blocking)
    bot.app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✋ Бот зупинено користувачем")
