import os
import subprocess
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TELEGRAM_ADMIN_BOT_TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
# Загружаем список админов
ADMIN_CHAT_IDS_RAW = os.getenv("TELEGRAM_ADMIN_CHAT_IDS", "")
ADMIN_CHAT_IDS = [int(x.strip()) for x in ADMIN_CHAT_IDS_RAW.split(",") if x.strip().isdigit()]

async def check_auth(update: Update):
    user_id = update.effective_message.chat_id
    if user_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("❌ Access denied.")
        return False
    return True

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        result = subprocess.run(['systemctl', 'is-active', 'botbuff'], capture_output=True, text=True, check=True)
        status = result.stdout.strip()
        await update.message.reply_text(f"Status BotBuff VK Bot: {status}")
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"Error getting status: {e}")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'botbuff'], check=True)
        await update.message.reply_text("✅ Restarting BotBuff VK Bot...")
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"Error restarting: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        subprocess.run(['sudo', 'systemctl', 'stop', 'botbuff'], check=True)
        await update.message.reply_text("✅ Stopping BotBuff VK Bot...")
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"Error stopping: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        subprocess.run(['sudo', 'systemctl', 'start', 'botbuff'], check=True)
        await update.message.reply_text("✅ Starting BotBuff VK Bot...")
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"Error starting: {e}")

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        result = subprocess.run(['journalctl', '-u', 'botbuff', '-n', '20', '--no-pager'], capture_output=True, text=True, check=True)
        logs_text = result.stdout
        await update.message.reply_text(f"```\n{logs_text}\n```", parse_mode='Markdown')
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"Error getting logs: {e}")

async def update_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        result = subprocess.run(['git', '-C', '/home/FOK/Vkbot', 'pull'], capture_output=True, text=True, check=True)
        await update.message.reply_text(f"✅ Git pull successful:\n```\n{result.stdout}\n```", parse_mode='Markdown')
        # Перезапускаем бота после обновления
        subprocess.run(['sudo', 'systemctl', 'restart', 'botbuff'], check=True)
        await update.message.reply_text("✅ Code updated and bot restarted.")
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"Error updating code: {e.stderr}")

def main():
    if not TELEGRAM_ADMIN_BOT_TOKEN:
        logging.error("TELEGRAM_ADMIN_BOT_TOKEN not set!")
        return
    app = Application.builder().token(TELEGRAM_ADMIN_BOT_TOKEN).build()

    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("update", update_code))

    logging.info("Telegram Admin Bot for BotBuff started.")
    app.run_polling()

if __name__ == '__main__':
    main()
