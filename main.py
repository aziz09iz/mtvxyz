import os
import logging
import asyncio
import random
import datetime
from datetime import timedelta
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

# --- SYSTEM: MODEL DISCOVERY ---
def refresh_available_models():
    global AVAILABLE_MODELS
    print("🔄 System Initialization: Scanning AI Models...")
    found_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            found_models.append(name)
        
        # Priority Logic: Flash -> Pro -> Others
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
    """Generate high-fidelity audio output."""
    try:
        # Menggunakan suara wanita Indonesia yang profesional
        voice = "id-ID-GadisNeural" 
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)
        return filename
    except Exception as e:
        logging.error(f"TTS Error: {e}")
        return None

# --- SERVICE: INTELLIGENCE (GEMINI) ---
async def get_gemini_content():
    """Generate professional insight & action plan."""
    
    themes = [
        "Strategic Thinking", "High Performance Habit", "Emotional Intelligence",
        "Financial Wisdom", "Leadership", "Resilience", "Mindfulness", "Time Mastery"
    ]
    theme = random.choice(themes)
    
    # Prompt Professional
    prompt = (
        f"Role: Anda adalah Executive Coach & Mentor kelas dunia. Topik saat ini: {theme}.\n\n"
        "Instruksi Output (Wajib ikuti struktur ini tanpa markdown json):\n"
        "1. Berikan 'Insight' mendalam (2 kalimat) dengan bahasa Indonesia yang elegan, berwibawa, namun membumi.\n"
        "2. Berikan 'Action Plan' (Tantangan Konkret) yang bisa diselesaikan dalam 5-10 menit.\n"
        "3. Gabungkan menjadi satu narasi yang mengalir lancar untuk dibacakan (script audio).\n\n"
        "Tone: Profesional, Tegas, Menginspirasi (Hindari bahasa alay/terlalu santai)."
    )

    config = types.GenerateContentConfig(temperature=0.7) # Sedikit lebih rendah agar stabil/profesional

    for model_name in AVAILABLE_MODELS:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=prompt,
                config=config
            )
            return response.text.strip()
        except Exception as e:
            if "429" in str(e) or "404" in str(e): continue
            logging.error(f"AI Error ({model_name}): {e}")

    return "Kesuksesan dimulai dari ketenangan. Ambil nafas dalam, dan fokus kembali pada prioritas utamamu saat ini."

# --- TELEGRAM INTERFACE ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    
    # Teks Start yang "Clean & Professional"
    welcome_msg = (
        f"✨ **Selamat Datang, {user}.**\n\n"
        "Saya adalah **AI Personal Growth Assistant** Anda.\n"
        "Tugas saya adalah memastikan Anda tetap pada performa puncak melalui motivasi terkurasi dan rencana aksi taktis.\n\n"
        "📊 **Layanan Otomatis:**\n"
        "• *Hourly Insight:* Pesan bijak setiap pergantian jam.\n"
        "• *Action Plan:* Tugas mikro untuk progres nyata.\n"
        "• *Audio Experience:* Motivasi dalam format suara.\n\n"
        "⚙️ **Status Sistem:**\n"
        "✅ AI Engine Online\n"
        "✅ Scheduler Active\n\n"
        "Sistem telah diaktifkan. Insight pertama akan dikirim pada jam berikutnya (Tepat Waktu)."
    )
    
    await update.message.reply_text(welcome_msg, parse_mode=constants.ParseMode.MARKDOWN)
    
    # Logic Sync Waktu (Jam Berikutnya :00)
    now = datetime.datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    seconds_until_next_hour = (next_hour - now).total_seconds()
    
    # Reset & Schedule
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()
    
    context.job_queue.run_repeating(
        send_motivation_routine, 
        interval=3600, 
        first=seconds_until_next_hour, 
        chat_id=chat_id, 
        name=str(chat_id)
    )
    
    # Konfirmasi waktu
    await update.message.reply_text(
        f"⏳ *Sinkronisasi Waktu...*\nNext Insight: `{next_hour.strftime('%H:%M')} WIB`",
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
        "🛑 **Layanan Dihentikan.**\n"
        "Terima kasih telah bersama kami. Gunakan /start untuk mengaktifkan kembali asisten Anda.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def test_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual Trigger."""
    loading_msg = await update.message.reply_text("⚡ *Analyzing Context & Generating Insight...*", parse_mode='Markdown')
    
    # Dummy Job Injection for Routine Call
    class DummyJob:
        def __init__(self, chat_id): self.chat_id = chat_id
    context.job = DummyJob(update.effective_chat.id)
    
    await send_motivation_routine(context)
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_msg.message_id)

async def send_motivation_routine(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    
    # 1. Generate Text
    content = await get_gemini_content()
    
    # 2. Kirim Text dengan Layout Rapi
    # Kita pisahkan konten jadi Header & Body
    current_time = datetime.datetime.now().strftime("%H:%M")
    
    formatted_text = (
        f"🌟 **DAILY INSIGHT** | ⏱ `{current_time}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Focus on Progress, Not Perfection.*"
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=formatted_text,
        parse_mode=constants.ParseMode.MARKDOWN
    )
    
    # 3. Kirim Audio
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.RECORD_VOICE)
    
    filename = f"audio_{chat_id}_{random.randint(1000,9999)}.mp3"
    audio_path = await create_voice_note(content, filename)
    
    if audio_path:
        await context.bot.send_voice(
            chat_id=chat_id,
            voice=open(audio_path, 'rb'),
            caption="🎧 *Audio Briefing*",
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
    
    print("🚀 AI Assistant System Online...")
    application.run_polling()

if __name__ == '__main__':
    main()
