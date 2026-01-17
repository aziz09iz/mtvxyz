import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google import genai

# 1. Konfigurasi Awal
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Inisialisasi Client
client = genai.Client(api_key=GEMINI_KEY)

# Variable Global
AVAILABLE_MODELS = []

# --- FUNGSI UTAMA: PERSIAPAN MODEL ---

def refresh_available_models():
    """Scan model dan urutkan prioritas (Flash -> Pro -> Lainnya)."""
    global AVAILABLE_MODELS
    print("🔄 Menyiapkan mesin motivasi...")
    
    found_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            found_models.append(name)
        
        # Prioritas: Flash (Cepat) -> Pro (Pintar) -> Lainnya
        flash_models = [m for m in found_models if "flash" in m and "vision" not in m]
        pro_models = [m for m in found_models if "pro" in m and "vision" not in m]
        other_models = [m for m in found_models if m not in flash_models and m not in pro_models]
        
        AVAILABLE_MODELS = flash_models + pro_models + other_models
        print(f"✅ Siap dengan {len(AVAILABLE_MODELS)} jalur model AI.")
        
    except Exception as e:
        print(f"⚠️ Gagal scan model: {e}. Menggunakan mode darurat.")
        AVAILABLE_MODELS = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-pro"]

refresh_available_models()

# --- FUNGSI GENERATE (AUTO-SWITCH) ---

async def get_gemini_motivation():
    """Generate motivasi dengan gaya bahasa menarik & rotasi model otomatis."""
    
    # Prompt yang sudah dipercantik
    prompt = (
        "Buatkan saya sebuah pesan motivasi yang inspiratif dan agak panjang (sekitar 3-4 kalimat). "
        "Gunakan bahasa Indonesia yang luwes, akrab, dan menyentuh hati (tidak kaku seperti robot). "
        "Konteksnya tentang semangat hidup, produktivitas, atau bangkit dari kegagalan. "
        "Wajib sertakan 2-3 emoji yang relevan di dalam kalimatnya agar terlihat hidup."
    )

    for model_name in AVAILABLE_MODELS:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=prompt
            )
            # Sukses? Kembalikan teksnya saja
            return response.text.strip()

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                logging.warning(f"⚠️ {model_name} sibuk/limit. Pindah ke model cadangan...")
                continue
            elif "404" in error_msg or "NOT_FOUND" in error_msg:
                continue
            else:
                logging.error(f"❌ Error {model_name}: {e}")
                continue

    return "🔥 Tetap semangat ya! Maaf, sistem AI sedang istirahat sejenak, tapi kamu harus jalan terus! 💪"

# --- HANDLER TELEGRAM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    
    # Kata pembuka yang lebih menarik
    welcome_msg = (
        f"👋 **Halo, {user_name}! Selamat datang di Zona Semangat!** 🌟\n\n"
        "Senang banget kamu ada di sini. Mulai sekarang, aku bakal jadi teman setia yang ngirimin "
        "booster energi positif buat kamu setiap jam. 🔋\n\n"
        "Gak perlu seting apa-apa, duduk manis aja & biarkan notifikasi dariku bikin harimu lebih cerah!\n\n"
        "👇 _Menu Singkat:_\n"
        "✨ /test - Minta motivasi sekarang juga\n"
        "🛑 /stop - Berhenti berlangganan"
    )
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    # Reset & Jadwalkan Ulang (Setiap 1 Jam / 3600 detik)
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()
    
    context.job_queue.run_repeating(
        send_hourly_motivation, 
        interval=3600,  # 1 Jam
        first=10,       # Pesan pertama dikirim 10 detik setelah start
        chat_id=chat_id, 
        name=str(chat_id)
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if not current_jobs:
        await update.message.reply_text("Kamu belum berlangganan kok. Ketik /start untuk mulai! 😊")
        return

    for job in current_jobs: job.schedule_removal()
    await update.message.reply_text("Oke, jadwal motivasi dimatikan. Kalau butuh semangat lagi, ketik /start ya! 👋")

async def test_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Pesan tunggu yang lebih asik
    status_msg = await update.message.reply_text("⏳ *Meracik kata-kata terbaik untukmu...*", parse_mode='Markdown')
    
    quote = await get_gemini_motivation()
    
    # Hapus status, ganti dengan quote tanpa info teknis
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=status_msg.message_id,
        text=quote # Langsung teks motivasi
    )

async def send_hourly_motivation(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    quote = await get_gemini_motivation()
    
    # Format pengiriman rutin
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"🔔 *Pengingat Jam Ini:*\n\n{quote}",
        parse_mode='Markdown'
    )

# --- START ---

def main():
    if not TOKEN:
        print("Error: TOKEN atau API KEY belum diisi.")
        return

    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("test", test_motivation))

    print("Bot Motivasi (Versi Final) siap menebar semangat! 🚀")
    application.run_polling()

if __name__ == '__main__':
    main()