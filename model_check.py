from google import genai
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
for m in client.models.list():
    print(m.name)
