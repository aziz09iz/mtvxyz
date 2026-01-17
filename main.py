import os
import logging
import asyncio
import random
import datetime
import json
import re
from datetime import timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from google import genai
from google.genai import types
import edge_tts 

# --- CONFIGURATION ---
load_dotenv()
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not GEMINI_KEY:
    logging.error("❌ Credentials Missing. Check .env variables.")
    exit(1)

try:
    client = genai.Client(api_key=GEMINI_KEY)
except Exception as e:
    logging.error(f"❌ Gemini Client Init Failed: {e}")
    exit(1)

AVAILABLE_MODELS = []

# --- UTILS ---
def get_wib_time():
    """Waktu WIB (UTC+7)."""
    utc_now = datetime.datetime.now(timezone.utc)
    return utc_now + timedelta(hours=7)

# --- SYSTEM: MODEL DISCOVERY ---
def refresh_available_models():
    global AVAILABLE_MODELS
    print("🔄 System Initialization: Scanning AI Models...")
    found_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "tts" in name or "audio" in name or "embedding" in name or "imagen" in name:
                continue
            found_models.append(name)
        
        flash_models = [m for m in found_models if "flash" in m and "vision" not in m]
        pro_models = [m for m in found_models if "pro" in m and "vision" not in m]
        other_models = [m for m in found_models if m not in flash_models and m not in pro_models]
        
        AVAILABLE_MODELS = flash_models + pro_models + other_models
        if not AVAILABLE_MODELS: AVAILABLE_MODELS = ["gemini-1.5-flash"]
        print(f"✅ AI Engine Ready. Primary: {AVAILABLE_MODELS[0]}")
    except:
        AVAILABLE_MODELS = ["gemini-1.5-flash"]

refresh_available_models()

# --- SERVICE: TEXT-TO-SPEECH ---
async def create_voice_note(text, filename="voice.mp3"):
    try:
        voice = "id-ID-GadisNeural" 
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)
        return filename
    except Exception as e:
        logging.error(f"TTS Error: {e}")
        return None

# --- SERVICE: INTELLIGENCE (GEMINI JSON) ---
async def get_gemini_content():
    """Generate konten JSON dengan Emoji."""
    
    themes = [
        "Growth Mindset", "Financial Freedom", "High Performance", 
        "Emotional Mastery", "Leadership", "Stoicism", "Focus & Flow"
    ]
    theme = random.choice(themes)
    
    prompt = (
        f"Role: Executive Mentor. Topik: {theme}.\n"
        "Output: **JSON Murni** (3 keys: insight, action, script).\n\n"
        "Style Guide:\n"
        "1. **'insight'**: 2 kalimat bijak & nendang. WAJIB sisipkan 1-2 emoji relevan di tengah/akhir kalimat.\n"
        "2. **'action'**: Tantangan 5 menit. WAJIB sisipkan 1 emoji ikonik (misal: 🔥, 📝, 💧).\n"
        "3. **'script'**: Narasi Voice Note panjang (sapaan hangat, penjelasan insight, ajakan action). Tanpa emoji (karena untuk suara).\n"
        "Bahasa: Indonesia Profesional, Elegan, namun Membakar Semangat."
    )

    config = types.GenerateContentConfig(temperature=0.75)

    for model_name in AVAILABLE_MODELS:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=prompt,
                config=config
            )
            raw_text = response.text.strip()
            clean_json = re.sub(r"```json|```", "", raw_text).strip()
            data = json.loads(clean_json)
            return data
        except Exception:
            continue

    return {
        "insight": "🌱 Ketenangan adalah kekuatan tertinggi. Di tengah badai, pikiran yang jernih adalah nahkoda terbaik.",
        "action": "🌬️ Tarik nafas dalam selama 4 detik, tahan 4 detik, hembuskan 4 detik. Ulangi 3 kali sekarang.",
        "script": "Halo. Terkadang kita lupa bahwa kekuatan terbesar ada dalam ketenangan. Ambil nafas sejenak dan kembali fokus."
    }

# --- TELEGRAM INTERFACE ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    
    # --- TAMPILAN DASHBOARD PREMIUM ---
    welcome_msg = (
        f"👋 **Halo, {user}!**\n"
        "Selamat datang di Ekosistem Produktivitas Anda.\n\n"
        "💎 **AI PERSONAL GROWTH ASSISTANT**\n"
        "Saya hadir untuk memastikan level energi dan fokus Anda tetap di puncak melalui:\n\n"
        "🧠 **Daily Wisdom** — Insight tajam untuk pola pikir.\n"
        "⚡ **Micro Actions** — Tantangan nyata, bukan sekadar wacana.\n"
        "🎧 **Audio Briefing** — Motivasi eksklusif via suara.\n\n"
        "⚙️ _Sistem telah aktif. Insight akan dikirim otomatis setiap jam._"
    )
    
    # TOMBOL INTERAKTIF (Inline Keyboard)
    keyboard = [
        [InlineKeyboardButton("⚡ Unlock Insight Sekarang", callback_data='trigger_now')],
        [InlineKeyboardButton("🛑 Matikan Layanan", callback_data='stop_service')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_msg, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    # Setup Schedule (WIB)
    setup_schedule(context, chat_id)

def setup_schedule(context, chat_id):
    """Fungsi pembantu untuk atur jadwal."""
    now_wib = get_wib_time()
    next_hour = (now_wib + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    seconds_until_next = (next_hour - now_wib).total_seconds()
    
    # Hapus job lama
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()
    
    # Buat job baru
    context.job_queue.run_repeating(
        send_motivation_routine, 
        interval=3600, 
        first=seconds_until_next, 
        chat_id=chat_id, 
        name=str(chat_id)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani Klik Tombol."""
    query = update.callback_query
    await query.answer() # Hilangkan loading di tombol
    
    if query.data == 'trigger_now':
        await query.edit_message_reply_markup(reply_markup=None) # Hilangkan tombol agar rapi
        await context.bot.send_message(chat_id=query.message.chat_id, text="🚀 *Memproses permintaan prioritas...*", parse_mode='Markdown')
        
        # Inject job manual
        class DummyJob:
            def __init__(self, chat_id): self.chat_id = chat_id
        context.job = DummyJob(query.message.chat_id)
        await send_motivation_routine(context)
        
    elif query.data == 'stop_service':
        # Panggil fungsi stop
        chat_id = query.message.chat_id
        current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
        for job in current_jobs: job.schedule_removal()
        
        await query.edit_message_text(text="🛑 **Layanan Non-Aktif.**\nTekan /start kapan saja untuk kembali.", parse_mode='Markdown')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()
    await update.message.reply_text("🛑 **Layanan Dihentikan.**", parse_mode=constants.ParseMode.MARKDOWN)

async def send_motivation_routine(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    
    data = await get_gemini_content()
    current_time_str = get_wib_time().strftime("%H:%M")
    
    # --- FORMAT PESAN YANG LEBIH CANTIK ---
    formatted_text = (
        f"🚀 **GROWTH SIGNAL** | ⏱ `{current_time_str} WIB`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 *INSIGHT*\n{data['insight']}\n\n"
        f"🎯 *ACTION*\n{data['action']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 _Audio Briefing Loading..._"
    )
    
    await context.bot.send_message(chat_id=chat_id, text=formatted_text, parse_mode=constants.ParseMode.MARKDOWN)
    
    # Kirim Audio
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.RECORD_VOICE)
    filename = f"audio_{chat_id}_{random.randint(1000,9999)}.mp3"
    audio_path = await create_voice_note(data['script'], filename)
    
    if audio_path:
        await context.bot.send_voice(
            chat_id=chat_id, 
            voice=open(audio_path, 'rb'), 
            caption="🎙️ *Executive Briefing*", 
            parse_mode='Markdown'
        )
        try: os.remove(audio_path)
        except: pass

# --- MAIN ---
def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    # Handler untuk Tombol
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 Premium Bot Online...")
    application.run_polling()

if __name__ == '__main__':
    main()
