import os
import json
import re
import streamlit as st
from openai import OpenAI

_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        # Try st.secrets first (Streamlit Cloud), then env var (local)
        try:
            api_key = st.secrets["DEEPSEEK_API_KEY"]
        except Exception:
            api_key = os.getenv("DEEPSEEK_API_KEY")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
    return _client

def classify_dish(dish: str) -> dict:
    client = _get_client()
    system_prompt = (
        "Eres un experto en nutrición y dietas vegetarianas y veganas. "
        "Clasificas platos de comida peruana y limeña de forma precisa y consistente."
    )
    user_prompt = (
        f'Clasifica el plato: "{dish}"\n'
        'Responde ÚNICAMENTE con JSON: {"label": "vegano|vegetariano|no_apto", "reason": "explicación"}\n'
        'Sin texto adicional ni markdown.'
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=150,
    )
    content = response.choices[0].message.content.strip()
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content).strip()
    result = json.loads(content)
    if result.get("label") not in ("vegano", "vegetariano", "no_apto"):
        result["label"] = "no_apto"
    return result
