import os
from openai import OpenAI

_VALID = {"Vegano", "Vegetariano", "Ninguno"}

def _client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise EnvironmentError("DEEPSEEK_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def classify_dish(dish_name: str) -> str:
    """Return 'Vegano', 'Vegetariano', or 'Ninguno' for a given dish name."""
    client = _client()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un experto en nutrición. "
                    "Clasifica el plato que te digan como exactamente una de estas tres categorías: "
                    "'Vegano', 'Vegetariano', o 'Ninguno'. "
                    "Responde ÚNICAMENTE con esa palabra, sin explicación ni puntuación adicional."
                ),
            },
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
