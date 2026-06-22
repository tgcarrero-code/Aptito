
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class FoodClassifier:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://api.deepseek.com",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
        )

    def classify_dish(self, dish_name: str) -> dict:
        if not self.client.api_key:
            return {"label": "error", "reason": "DEEPSEEK_API_KEY not set."}

        prompt = (
            f"Classify the following dish '{dish_name}' as 'vegano' (vegan), "
            f"'vegetariano' (vegetarian), or 'no_apto' (not suitable for vegans/vegetarians). "
            f"Provide a concise reason for the classification. "
            f"Respond with a JSON object like: "
            f"{{'label': 'vegano/vegetariano/no_apto', 'reason': '...'}}"
        )

        try:
            chat_completion = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            response_content = chat_completion.choices[0].message.content
            import json
            return json.loads(response_content)
        except Exception as e:
            return {"label": "error", "reason": f"API call failed: {e}"}

if __name__ == "__main__":
    classifier = FoodClassifier()
    print(classifier.classify_dish("Lomo Saltado"))
    print(classifier.classify_dish("Ceviche de champiñones"))
    print(classifier.classify_dish("Ensalada de quinua"))
