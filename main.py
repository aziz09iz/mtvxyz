import os
import logging
import asyncio
import random
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google import genai
from google.genai import types

# 1. Konfigurasi Awal
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Cek Ketersediaan Kunci
if not TOKEN or not GEMINI_KEY:
    logging.error("❌ TOKEN atau GEMINI_API_KEY belum diisi di Environment Variables!")
    exit(1)

# Inisialisasi Client
try:
    client = genai.Client(api_key=GEMINI_KEY)
except Exception as e:
    logging.error(f"❌ Gagal inisialisasi Gemini Client: {e}")
    exit(1)

# Variable Global
AVAILABLE_MODELS = []

# --- FUNGSI 1: AUTO-DETECT MODELS ---

def refresh_available_models():
    """Scan model yang tersedia di akun dan urutkan prioritasnya."""
    global AVAILABLE_MODELS
    print("🔄 Scanning model AI yang tersedia...")
    
    found_models = []
    try:
        # Ambil list model dari Google
        for m in client.models.list():
            name = m.name.replace("models/", "")
            found_models.append(name)
        
        # Urutan Prioritas: Flash (Cepat & Murah) -> Pro (Pintar) -> Lainnya
        flash_models = [m for m in found_models if "flash" in m and "vision" not in m]
        pro_models = [m for m in found_models if "pro" in m and "vision" not in m]
        other_models = [m for m in found_models if m not in flash_models and m not in pro_models]
        
        # Gabungkan
        AVAILABLE_MODELS = flash_models + pro_models + other_models
        
        if not AVAILABLE_MODELS:
            print("⚠️ Tidak ada model ditemukan. Menggunakan default fallback.")
            AVAILABLE_MODELS = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-pro"]
            
        print(f"✅ Siap! {len(AVAILABLE_MODELS)} model aktif. Prioritas utama: {AVAILABLE_MODELS[0]}")
        
    except Exception as e:
        print(f"⚠️ Gagal scan model (Mungkin API Key bermasalah?): {e}")
        # Tetap isi default agar bot tidak crash saat start
        AVAILABLE_MODELS = ["gemini-1.5-flash"]

# Jalankan scan saat bot nyala
refresh_available_models()

# --- FUNGSI 2: GENERATE MOTIVASI (RANDOMIZED) ---

async def get_gemini_motivation():
    """Generate motivasi unik dengan topik acak dan failover system."""
    
    # List topik agar konten selalu fresh
    topik_list = [
        "disiplin dan konsistensi", "bangkit dari kegagalan", "bersyukur hal kecil",
        "kesehatan mental", "fokus masa depan", "belajar skill baru",
        "kesabaran berproses", "mencintai diri sendiri", "berani ambil resiko",
        "manajemen waktu", "menghindari penundaan", "kekuatan doa dan usaha"
    ]
    
    topik = random.choice(topik_list)
    
    prompt = (
        f"Buatkan satu pesan motivasi singkat (2-3 kalimat) yang sangat 'relate' dan menyentuh hati "
        f"tentang topik: '{topik}'. "
        "Gunakan bahasa Indonesia yang santai tapi bijak (tidak kaku). "
        "Wajib sertakan 1-2 emoji yang relevan."
    )

    # Config agar output kreatif (tidak monoton)
    config = types.GenerateContentConfig(temperature=0.9)

    # Loop mencoba model satu per satu jika ada yang error/limit
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
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                logging.warning(f"⚠️ {model_name} Limit Habis. Mencoba model lain...")
                continue # Coba model berikutnya
            elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                logging.critical("❌ API KEY DITOLAK! Cek konfigurasi di Railway.")
                return "⚠️ Maaf, sistem sedang maintenance (API Key Error)."
            elif "404" in error_msg:
                continue # Skip model tidak valid
            else:
                logging.error(f"❌ Error pada {model_name}: {e}")
                continue

    return "🔥 Tetap semangat! (Sistem AI sedang sibuk, tapi kamu hebat!). 💪"

# --- HANDLER TELEGRAM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name
    
    welcome_text = (
        f"👋 **Halo, {name}! Selamat datang!** 🌟\n\n"
        "Bot Motivasi AI siap menemani harimu.\n"
        "Saya akan mengirim pesan positif setiap 1 jam agar kamu tetap semangat! 🔥\n\n"
        "👇 _Perintah:_\n"
        "⚡ /test - Coba minta motivasi sekarang\n"
        "🛑 /stop - Berhenti berlangganan"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    # Hapus job lama agar tidak double
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
    
    # Buat job baru (3600 detik = 1 jam)
    context.job_queue.run_repeating(
        send_hourly_motivation, 
        interval=3600, 
        first=10, 
        chat_id=chat_id, 
        name=str(chat_id)
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if not current_jobs:
        await update.message.reply_text("Kamu belum berlangganan. Ketik /start untuk mulai.")
        return

    for job in current_jobs:
        job.schedule_removal()
    
    await update.message.reply_text("✅ Berlangganan dihentikan. Sampai jumpa lagi! 👋")

async def test_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ *Meracik kata-kata semangat...*", parse_mode='Markdown')
    quote = await get_gemini_motivation()
    
    # Update pesan tunggu menjadi quote
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=msg.message_id,
        text=quote
    )

async def send_hourly_motivation(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    quote = await get_gemini_motivation()
    
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"🔔 *Reminder Semangat:*\n\n{quote}",
        parse_mode='Markdown'
    )

# --- START BOT ---

def main():
    # Inisialisasi Aplikasi dengan JobQueue
    application = Application.builder().token(TOKEN).build()

    # Register Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("test", test_motivation))

    print(f"🚀 Bot Berjalan! Menunggu pesan...")
    
    # Jalankan polling (Block main thread)
    application.run_polling()

if __name__ == '__main__':
    main()
