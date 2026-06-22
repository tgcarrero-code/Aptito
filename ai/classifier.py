import os
from openai import OpenAI

_VALID = {"Vegano", "Vegetariano", "Ninguno"}

def _get_api_key():
    try:
        import streamlit as st
        return st.secrets["DEEPSEEK_API_KEY"]
    except Exception:
        return os.environ.get("DEEPSEEK_API_KEY")

def classify_dish(dish_name: str) -> str:
    api_key = _get_api_key()
    if not api_key:
        raise EnvironmentError("DEEPSEEK_API_KEY not set")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Eres un experto en nutrición. Clasifica el plato como exactamente una de estas tres categorías: 'Vegano', 'Vegetariano', o 'Ninguno'. Responde ÚNICAMENTE con esa palabra."},
            {"role": "user", "content": f"Plato: {dish_name}"},
        ],
        max_tokens=10,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    if raw in _VALID:
        return raw
    lower = raw.lower()
    if "vegano" in lower:
        return "Vegano"
    if "vegetariano" in lower:
        return "Vegetariano"
    return "Ninguno"

def classify_dishes(dish_names: list[str]) -> dict[str, str]:
    return {name: classify_dish(name) for name in dish_names}
