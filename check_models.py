import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

print("API KEY FOUND:", api_key is not None)

genai.configure(api_key=api_key)

for model in genai.list_models():
    print(model.name)