# 🚀 AI Personal Growth Assistant (Telegram Bot)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0?style=for-the-badge&logo=telegram)
![Gemini AI](https://img.shields.io/badge/Google-Gemini_AI-8E75B2?style=for-the-badge)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=for-the-badge&logo=railway)

**AI Personal Growth Assistant** adalah bot Telegram canggih yang dirancang untuk meningkatkan produktivitas dan kesehatan mental pengguna. Bot ini mengintegrasikan **Google Gemini AI** untuk menghasilkan insight bijak dan **Edge TTS** untuk mengubah teks menjadi narasi suara (Voice Note) yang natural.

Bot ini bukan sekadar pengirim pesan random, melainkan asisten cerdas yang tersinkronisasi dengan waktu, memiliki antarmuka interaktif, dan manajemen error yang tangguh.

---

## ✨ Fitur Utama

* **🧠 Multi-Model AI Intelligence:** Menggunakan sistem rotasi otomatis antara model `Gemini Flash`, `Pro`, dan lainnya untuk menghindari Rate Limit (Error 429).
* **🎧 High-Fidelity Voice Note:** Mengubah motivasi tertulis menjadi suara wanita Indonesia yang natural (*id-ID-GadisNeural*) menggunakan `edge-tts`.
* **📅 Precision Scheduler (WIB):** Pesan dikirim otomatis setiap pergantian jam (misal: 08:00, 09:00) mengikuti Waktu Indonesia Barat (UTC+7).
* **🎨 Premium UI/UX:** Tampilan pesan yang bersih menggunakan parsing JSON (memisahkan Insight, Action Plan, dan Script Audio) serta tombol interaktif (Inline Buttons).
* **🛡️ Robust Error Handling:** Otomatis mendeteksi model yang bermasalah (seperti model khusus vision/audio) dan memfilternya agar bot tidak crash.

---

## 🛠️ Tech Stack

* **Language:** Python 3.11+
* **Framework:** `python-telegram-bot` (JobQueue enabled)
* **AI Core:** `google-genai` (Official SDK)
* **TTS Engine:** `edge-tts`
* **Environment:** `python-dotenv`

---

