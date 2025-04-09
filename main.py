import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, filters
import logging
import re
import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Показывать всё важное
)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('bot_activity.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

DOWNLOAD_PATH = 'downloads/'
user_links = {}
user_choices = {}

ADMIN_PANEL = False
active_users = set()
ADMIN_ID = 1770338622  # ID администратора
SECRET_PASSWORD = 'windows.ru'

# Функция для скачивания видео или аудио
def download_media(url: str, quality: str, is_audio: bool = False) -> str:
    ffmpeg_path = r'C:\ffmpeg-7.1.1-essentials_build\bin'  # Укажите путь к ffmpeg, если нужно

    # Проверка существования пути ffmpeg
    if not os.path.exists(ffmpeg_path):
        raise FileNotFoundError(f"Путь к ffmpeg не найден: {ffmpeg_path}")

    # Проверка существования папки для скачивания
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)
        logger.info(f"Папка для скачивания была создана: {DOWNLOAD_PATH}")

    if is_audio:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_PATH, '%(title)s.mp3'),  # Сохраняем как .mp3
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': ffmpeg_path  # Указываем путь к ffmpeg
        }
    else:
        ydl_opts = {
            'format': quality,
            'outtmpl': os.path.join(DOWNLOAD_PATH, '%(title)s.%(ext)s'),
            'ffmpeg_location': ffmpeg_path  # Указываем путь к ffmpeg
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict)
        
        # Печатаем путь для диагностики
        logger.info(f"Скачиваем файл: {filename}")
        
        # Удаляем исходный .webm файл (если есть) после конвертации
        if is_audio and filename.endswith(".webm"):
            os.remove(filename)
            logger.info(f"Удалён исходный файл: {filename}")

        # Создаём директорию, если её нет
        directory = os.path.dirname(filename)
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Создана директория: {directory}")
        
        return filename

# /report команда
async def report(update: Update, context: CallbackContext):
    user = update.effective_user
    bug_report = update.message.text[7:].strip()  # Отсекаем "/report "
    
    if bug_report:
        # Отправляем баг-репорт тебе на id
        try:
            # Получаем последние строки из лога
            with open('bot_activity.log', 'r') as log_file:
                logs = log_file.readlines()[-10:]  # Последние 10 строк лога

            # Формируем сообщение
            message = f"Баг-репорт от пользователя {user.full_name} (@{user.username}, ID: {user.id}):\n\n{bug_report}\n\nПоследние 10 строк из лога:\n```{''.join(logs)}```"
            await context.bot.send_message(chat_id=ADMIN_ID, text=message)
            await update.message.reply_text("✅ Ваш баг-репорт был отправлен!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке репорта: {e}")
    else:
        await update.message.reply_text("⚡️ Пожалуйста, напишите описание ошибки после команды /report.")

SECRET_PASSWORD = 'windows.ru'

# Секретная команда
async def secret_command(update: Update, context: CallbackContext):
    global ADMIN_PANEL
    user = update.effective_user
    secret_input = update.message.text[7:].strip()

    if secret_input == SECRET_PASSWORD and user.id == ADMIN_ID:
        await update.message.reply_text("✅ Доступ открыт. Теперь отправь текст, который будет рассылается всем пользователям!")
        ADMIN_PANEL = True  # Включаем админ-панель
        await update.message.reply_text("Введите текст, который будет отправлен всем пользователям:")
    else:
        await update.message.reply_text("❌ Неверный пароль или у вас нет прав на доступ к админ-панели!")

# Обработка текста от админа (рассылка всем пользователям)
async def admin_message(update: Update, context: CallbackContext):
    global ADMIN_PANEL
    user = update.effective_user
    if ADMIN_PANEL and user.id == ADMIN_ID:  # Проверка, что админ - это именно тот пользователь
        text_to_send = update.message.text
        for user_id in active_users:  # Активные пользователи
            try:
                await context.bot.send_message(user_id, text_to_send)
            except Exception as e:
                logger.error(f"Ошибка при рассылке: {e}")
        await update.message.reply_text("✅ Текст был отправлен всем пользователям!")
        ADMIN_PANEL = False  # Выключаем админ-панель после отправки сообщения
    elif user.id != ADMIN_ID:
        await update.message.reply_text("❌ Вы не имеете доступа к админ-панели!")

# /start команда
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id  # Получаем ID пользователя
    active_users.add(user_id)  # Добавляем ID в список активных пользователей

    keyboard = [
        [
            InlineKeyboardButton("🎬 Скачать видео", callback_data='video'),
            InlineKeyboardButton("🎵 Скачать аудио", callback_data='audio')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что ты хочешь скачать?", reply_markup=reply_markup)

# Обработка выбора после /start
async def start_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    choice = query.data
    user_choices[query.message.chat_id] = choice

    if choice == 'video':
        await query.edit_message_text("📎 Теперь отправь ссылку на видео!")
    elif choice == 'audio':
        await query.edit_message_text("📎 Теперь отправь ссылку на видео для конвертации в MP3!")

# Обработка ссылки
# Обработка ссылки
async def handle_message(update: Update, context: CallbackContext):
    global ADMIN_PANEL
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User: {user.username} | ID: {user.id} | Name: {user.full_name} | Message: {update.message.text}")

    # Если бот в админ-панели
    if ADMIN_PANEL:
        if user.id == ADMIN_ID:  # Жесткая проверка на ID администратора
            text_to_send = update.message.text
            for user_id in active_users:  # Рассылаем всем активным пользователям
                try:
                    await context.bot.send_message(user_id, text_to_send)
                except Exception as e:
                    logger.error(f"Ошибка при рассылке: {e}")
            await update.message.reply_text("✅ Текст был отправлен всем пользователям!")
            time.sleep(1)
            ADMIN_PANEL = False  # Возвращаемся в обычный режим
    else:
        url = update.message.text
        choice = user_choices.get(chat_id)

        if choice is None:
            # Если выбор ещё не сделан, ничего не проверяем на YouTube
            return

        if "youtube.com" in url or "youtu.be" in url:
            active_users.add(chat_id)  # Добавляем пользователя как активного
            user_links[chat_id] = url

            if choice == 'video':
                keyboard = [
                    [
                        InlineKeyboardButton("🎥 720p", callback_data='best[height<=720]'),
                        InlineKeyboardButton("🎥 480p", callback_data='best[height<=480]'),
                        InlineKeyboardButton("🎥 360p", callback_data='best[height<=360]')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text('Выбери качество видео:', reply_markup=reply_markup)

            elif choice == 'audio':
                await update.message.reply_text("🎵 Скачиваю и конвертирую в MP3...")
                try:
                    audio_path = download_media(url, quality='bestaudio', is_audio=True)
                    with open(audio_path, 'rb') as audio_file:
                        await update.message.reply_audio(audio_file)
                    os.remove(audio_path)
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка: {e}")
        else:
            if choice in ['audio', 'video']:
                await update.message.reply_text("🚫 Это не ссылка на YouTube!")
                
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User: {user.username} | ID: {user.id} | Name: {user.full_name} | Message: {update.message.text}")

    # Если бот в админ-панели
    if ADMIN_PANEL:
        if user.id == ADMIN_ID:  # Жесткая проверка на ID администратора
            text_to_send = update.message.text
            for user_id in active_users:  # Рассылаем всем активным пользователям
                try:
                    await context.bot.send_message(user_id, text_to_send)
                except Exception as e:
                    logger.error(f"Ошибка при рассылке: {e}")
            await update.message.reply_text("✅ Текст был отправлен всем пользователям!")
            time.sleep(1)
            ADMIN_PANEL = False  # Возвращаемся в обычный режим
    else:
        url = update.message.text
        choice = user_choices.get(chat_id)

        if "youtube.com" in url or "youtu.be" in url:
            active_users.add(chat_id)  # Добавляем пользователя как активного
            user_links[chat_id] = url

            if choice == 'video':
                keyboard = [
                    [
                        InlineKeyboardButton("🎥 720p", callback_data='best[height<=720]'),
                        InlineKeyboardButton("🎥 480p", callback_data='best[height<=480]'),
                        InlineKeyboardButton("🎥 360p", callback_data='best[height<=360]')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text('Выбери качество видео:', reply_markup=reply_markup)

            elif choice == 'audio':
                await update.message.reply_text("🎵 Скачиваю и конвертирую в MP3...")
                try:
                    audio_path = download_media(url, quality='bestaudio', is_audio=True)
                    with open(audio_path, 'rb') as audio_file:
                        await update.message.reply_audio(audio_file)
                    os.remove(audio_path)
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка: {e}")
            else:
                await update.message.reply_text("⚡️ Сначала выбери через /start, что скачать!")
        else:
            if not ADMIN_PANEL and choice == 'video' or 'audio':
                await update.message.reply_text("🚫 Это не ссылка на YouTube!")

# Обработка выбора качества видео
async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    quality = query.data
    chat_id = query.message.chat_id
    url = user_links.get(chat_id)

    if url:
        await query.edit_message_text(text="📥 Скачиваю видео...")
        try:
            video_path = download_media(url, quality)
            with open(video_path, 'rb') as video_file:
                await query.message.reply_video(video_file)
            os.remove(video_path)
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка: {e}")
    else:
        await query.message.reply_text("🚫 Ссылка не найдена. Отправь её снова.")

# Основная функция
def main():
    token = '7570835144:AAH3wgRRRu-24FdTpKi1QB2eHO0hhTm0Go4'
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("secret", secret_command))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start_choice, pattern='^(video|audio)$'))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & filters.COMMAND, admin_message))  # Добавляем обработку команды админа

    application.run_polling()

if __name__ == '__main__':
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)
        logger.info(f"Папка для скачивания была создана: {DOWNLOAD_PATH}")

    main()
