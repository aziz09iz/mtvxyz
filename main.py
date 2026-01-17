import os
import logging
import asyncio
import random
import datetime
from datetime import timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google import genai
from google.genai import types
import edge_tts  # Library Suara

# 1. Konfigurasi Awal
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not GEMINI_KEY:
    logging.error("❌ TOKEN atau GEMINI_API_KEY belum diisi!")
    exit(1)

try:
    client = genai.Client(api_key=GEMINI_KEY)
except Exception as e:
    logging.error(f"❌ Gagal inisialisasi Gemini: {e}")
    exit(1)

AVAILABLE_MODELS = []

# --- FUNGSI 1: AUTO-DETECT MODELS ---
def refresh_available_models():
    global AVAILABLE_MODELS
    print("🔄 Scanning model AI...")
    found_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            found_models.append(name)
        
        flash_models = [m for m in found_models if "flash" in m and "vision" not in m]
        pro_models = [m for m in found_models if "pro" in m and "vision" not in m]
        other_models = [m for m in found_models if m not in flash_models and m not in pro_models]
        
        AVAILABLE_MODELS = flash_models + pro_models + other_models
        if not AVAILABLE_MODELS: AVAILABLE_MODELS = ["gemini-1.5-flash"]
        print(f"✅ Siap dengan model utama: {AVAILABLE_MODELS[0]}")
    except:
        AVAILABLE_MODELS = ["gemini-1.5-flash"]

refresh_available_models()

# --- FUNGSI 2: GENERATE AUDIO (TTS) ---
async def create_voice_note(text, filename="motivasi.mp3"):
    """Mengubah teks menjadi suara (Bahasa Indonesia)."""
    try:
        # Suara ID: id-ID-GadisNeural (Cewek) atau id-ID-ArdiNeural (Cowok)
        voice = "id-ID-GadisNeural" 
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)
        return filename
    except Exception as e:
        logging.error(f"Gagal membuat audio: {e}")
        return None

# --- FUNGSI 3: GENERATE TEXT (GEMINI) ---
async def get_gemini_content():
    """Generate Motivasi + Action Plan."""
    topik = random.choice([
        "disiplin", "kesehatan", "keuangan", "belajar", "karir",
        "bersyukur", "sabar", "bangkit gagal", "relasi", "produktifitas"
    ])
    
    # Prompt meminta struktur khusus (Quote & Challenge)
    prompt = (
        f"Topik: {topik}.\n"
        "Berikan respons dengan format json (tanpa markdown json) atau format teks terstruktur:\n"
        "1. Bagian Motivasi: 2 kalimat menyentuh hati, bahasa luwes & akrab.\n"
        "2. Bagian Tantangan: Satu tugas kecil (micro-action) yang bisa dilakukan user dalam 5 menit ke depan.\n"
        "Gabungkan keduanya dalam satu paragraf narasi yang enak dibaca untuk dijadikan script voice note. "
        "Jangan gunakan simbol aneh, gunakan tanda baca yang tepat untuk intonasi suara."
    )

    config = types.GenerateContentConfig(temperature=0.8)

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
            logging.error(f"Error {model_name}: {e}")

    return "Tetap semangat! Minumlah segelas air putih sekarang agar fokusmu kembali."

# --- HANDLER TELEGRAM ---

async def send_motivation_routine(context: ContextTypes.DEFAULT_TYPE):
    """Fungsi utama yang mengirim Text + Audio."""
    job = context.job
    chat_id = job.chat_id
    
    # 1. Ambil Teks dari AI
    full_text = await get_gemini_content()
    
    # 2. Kirim Teks dulu
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔔 *Reminder Jam Ini:*\n\n{full_text}",
        parse_mode='Markdown'
    )
    
    # 3. Buat & Kirim Audio
    # Kita kirim status "recording voice..."
    await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
    
    audio_path = await create_voice_note(full_text, f"voice_{chat_id}.mp3")
    
    if audio_path:
        await context.bot.send_voice(
            chat_id=chat_id,
            voice=open(audio_path, 'rb'),
            caption="🎧 Dengerin ya biar makin semangat!"
        )
        # Bersihkan file
        os.remove(audio_path)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        "👋 **Halo! Bot Motivasi Suara Aktif!** 🎙️\n\n"
        "Saya akan mengirimkan:\n"
        "1. Kata Motivasi 📖\n"
        "2. Tantangan Aksi (Action Plan) 🔥\n"
        "3. Voice Note Spesial 🎧\n\n"
        "⏳ *Jadwal:* Setiap jam tepat (Contoh: 08:00, 09:00, dst)."
    )
    
    # --- LOGIKA PENJADWALAN TEPAT WAKTU ---
    # Hitung detik menuju jam berikutnya (misal sekarang 07:15 -> next 08:00)
    now = datetime.datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    seconds_until_next_hour = (next_hour - now).total_seconds()
    
    # Hapus job lama
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()
    
    # Job Pertama: Jalan pas di jam berikutnya
    # Job Selanjutnya: Jalan setiap 3600 detik (1 jam) setelahnya
    context.job_queue.run_repeating(
        send_motivation_routine, 
        interval=3600, 
        first=seconds_until_next_hour, 
        chat_id=chat_id, 
        name=str(chat_id)
    )
    
    await update.message.reply_text(
        f"✅ Jadwal diatur!\n"
        f"Pesan pertama akan dikirim pukul: {next_hour.strftime('%H:%M')}\n"
        f"(Sekitar {int(seconds_until_next_hour//60)} menit lagi)."
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()
    await update.message.reply_text("✅ Berlangganan dihentikan.")

async def test_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test manual (langsung kirim tanpa nunggu jam)."""
    await update.message.reply_text("⏳ Sedang memproses teks & suara...")
    
    # Kita pakai fungsi routine tapi kita inject job dummy
    class DummyJob:
        def __init__(self, chat_id): self.chat_id = chat_id
    
    # Hack sedikit context agar fungsi routine bisa dipanggil manual
    context.job = DummyJob(update.effective_chat.id)
    await send_motivation_routine(context)

# --- MAIN ---
def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("test", test_motivation))
    
    print("🚀 Bot Voice Motivasi Berjalan...")
    application.run_polling()

if __name__ == '__main__':
    main()
