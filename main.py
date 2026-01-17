import os
import logging
import asyncio
import random
import datetime
import json
import re
from datetime import timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, ContextTypes
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

# --- UTILS: TIMEZONE (WIB) ---
def get_wib_time():
    """Mengambil waktu saat ini dalam WIB (UTC+7)."""
    utc_now = datetime.datetime.now(timezone.utc)
    wib_now = utc_now + timedelta(hours=7)
    return wib_now

# --- SYSTEM: MODEL DISCOVERY ---
def refresh_available_models():
    global AVAILABLE_MODELS
    print("🔄 System Initialization: Scanning AI Models...")
    found_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            # Filter model TTS/Audio agar tidak error
            if "tts" in name or "audio" in name or "embedding" in name or "imagen" in name:
                continue
            found_models.append(name)
        
        flash_models = [m for m in found_models if "flash" in m and "vision" not in m]
        pro_models = [m for m in found_models if "pro" in m and "vision" not in m]
        other_models = [m for m in found_models if m not in flash_models and m not in pro_models]
        
        AVAILABLE_MODELS = flash_models + pro_models + other_models
        if not AVAILABLE_MODELS: AVAILABLE_MODELS = ["gemini-1.5-flash"]
        print(f"✅ AI Engine Ready. Primary Core: {AVAILABLE_MODELS[0]}")
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

# --- SERVICE: INTELLIGENCE (GEMINI JSON MODE) ---
async def get_gemini_content():
    """Generate konten terpisah (Teks Chat vs Script Audio) via JSON."""
    
    themes = [
        "Strategic Thinking", "High Performance Habit", "Emotional Intelligence",
        "Financial Wisdom", "Leadership", "Resilience", "Mindfulness", "Time Mastery",
        "Personal Branding", "Critical Thinking"
    ]
    theme = random.choice(themes)
    
    # Prompt khusus meminta JSON
    prompt = (
        f"Role: Executive Coach. Topik: {theme}.\n"
        "Tugas: Berikan output dalam format **JSON Murni** (tanpa markdown ```json).\n"
        "Struktur JSON harus memiliki 3 kunci:\n"
        "1. 'insight': Kutipan mendalam (maksimal 2 kalimat) untuk dibaca di chat.\n"
        "2. 'action': Tantangan konkret 5 menit untuk dilakukan user.\n"
        "3. 'script': Narasi lengkap, panjang, dan mengalir untuk dibacakan sebagai Voice Note (sapa user, jelaskan insight, lalu ajak lakukan aksi).\n\n"
        "Pastikan bahasa Indonesia elegan, profesional, dan menyentuh."
    )

    config = types.GenerateContentConfig(temperature=0.7)

    for model_name in AVAILABLE_MODELS:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=prompt,
                config=config
            )
            raw_text = response.text.strip()
            
            # Bersihkan jika AI tidak sengaja pakai markdown code block
            clean_json = re.sub(r"```json|```", "", raw_text).strip()
            
            # Parsing JSON
            data = json.loads(clean_json)
            return data
            
        except json.JSONDecodeError:
            logging.warning(f"⚠️ JSON Parse Error di {model_name}. Retrying...")
            continue
        except Exception as e:
            if "429" in str(e) or "404" in str(e): continue
            logging.error(f"AI Error ({model_name}): {e}")

    # Fallback Data jika semua error
    return {
        "insight": "Ketenangan adalah kunci kejernihan berpikir.",
        "action": "Ambil nafas dalam selama 1 menit.",
        "script": "Halo, mohon maaf sistem sedang sibuk. Namun ingatlah bahwa ketenangan adalah kunci."
    }

# --- TELEGRAM INTERFACE ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    
    welcome_msg = (
        f"✨ **Selamat Datang, {user}.**\n\n"
        "Saya adalah **AI Personal Growth Assistant** Anda.\n"
        "Sistem kini telah aktif dan tersinkronisasi dengan Waktu Indonesia Barat (WIB).\n\n"
        "📊 **Layanan Otomatis:**\n"
        "• *Hourly Insight:* Pesan bijak setiap pergantian jam.\n"
        "• *Action Plan:* Tugas mikro untuk progres nyata.\n"
        "• *Audio Experience:* Motivasi dalam format suara.\n\n"
        "Insight pertama akan dikirim tepat pada jam berikutnya."
    )
    
    await update.message.reply_text(welcome_msg, parse_mode=constants.ParseMode.MARKDOWN)
    
    # Logic Sync Waktu WIB
    now_wib = get_wib_time()
    next_hour = (now_wib + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    # Hitung selisih detik dari sekarang sampai jam berikutnya
    seconds_until_next = (next_hour - now_wib).total_seconds()
    
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()
    
    context.job_queue.run_repeating(
        send_motivation_routine, 
        interval=3600, 
        first=seconds_until_next, 
        chat_id=chat_id, 
        name=str(chat_id)
    )
    
    await update.message.reply_text(
        f"⏳ *Sinkronisasi Waktu WIB...*\nNext Insight: `{next_hour.strftime('%H:%M')} WIB`",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if not current_jobs:
        await update.message.reply_text("ℹ️ *Status:* Tidak ada langganan aktif.", parse_mode='Markdown')
        return

    for job in current_jobs: job.schedule_removal()
    
    await update.message.reply_text(
        "🛑 **Layanan Dihentikan.**\nTerima kasih, sampai jumpa kembali.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def test_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual Trigger."""
    loading_msg = await update.message.reply_text("⚡ *Generating Professional Insight...*", parse_mode='Markdown')
    
    class DummyJob:
        def __init__(self, chat_id): self.chat_id = chat_id
    context.job = DummyJob(update.effective_chat.id)
    
    await send_motivation_routine(context)
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_msg.message_id)

async def send_motivation_routine(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    
    # 1. Generate Konten (JSON Dictionary)
    data = await get_gemini_content()
    
    # 2. Kirim Text (Hanya Insight & Action)
    # Ambil jam WIB untuk header
    current_time_str = get_wib_time().strftime("%H:%M")
    
    formatted_text = (
        f"🌟 **DAILY INSIGHT** | ⏱ `{current_time_str} WIB`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 *Insight:*\n{data['insight']}\n\n"
        f"🔥 *Action Plan:*\n{data['action']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 _Dengarkan audio di bawah untuk brief lengkap._"
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=formatted_text,
        parse_mode=constants.ParseMode.MARKDOWN
    )
    
    # 3. Kirim Audio (Menggunakan script narasi panjang)
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.RECORD_VOICE)
    
    filename = f"audio_{chat_id}_{random.randint(1000,9999)}.mp3"
    # Gunakan data['script'] yang isinya narasi lengkap
    audio_path = await create_voice_note(data['script'], filename)
    
    if audio_path:
        await context.bot.send_voice(
            chat_id=chat_id,
            voice=open(audio_path, 'rb'),
            caption="🎧 *Executive Briefing*",
            parse_mode='Markdown'
        )
        try:
            os.remove(audio_path)
        except:
            pass

# --- MAIN EXECUTION ---
def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("test", test_motivation))
    
    print("🚀 AI Assistant System Online (WIB Mode)...")
    application.run_polling()

if __name__ == '__main__':
    main()
