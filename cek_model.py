import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    print("=== DAFTAR MODEL YANG TERSEDIA ===")
    
    # Kita ambil semua list model tanpa filter properti
    for m in client.models.list():
        # Print nama modelnya
        print(f"- {m.name}")
            
except Exception as e:
    print(f"Error detail: {e}")