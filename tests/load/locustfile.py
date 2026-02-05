import os
import random
from locust import HttpUser, task, between

API_KEY = os.getenv("LOADTEST_API_KEY", "dev-api-key")
USER_ID = os.getenv("LOADTEST_USER_ID", "load-user")


class AstroApiUser(HttpUser):
    wait_time = between(0.2, 1.5)

    def on_start(self):
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "X-User-Id": USER_ID,
            "Content-Type": "application/json",
        }

    @task(4)
    def chart_natal(self):
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        payload = {
            "natal_year": 1992,
            "natal_month": month,
            "natal_day": day,
            "natal_hour": 10,
            "natal_minute": 30,
            "natal_second": 0,
            "year": 1992,
            "month": month,
            "day": day,
            "hour": 10,
            "minute": 30,
            "second": 0,
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
            "house_system": "P",
            "zodiac_type": "tropical",
        }
        self.client.post("/v1/chart/natal", json=payload, headers=self.headers, name="POST /v1/chart/natal")

    @task(3)
    def chart_transits(self):
        payload = {
            "natal_year": 1992,
            "natal_month": 8,
            "natal_day": 12,
            "natal_hour": 10,
            "natal_minute": 30,
            "natal_second": 0,
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
            "house_system": "P",
            "zodiac_type": "tropical",
            "target_date": "2026-01-25",
        }
        self.client.post("/v1/chart/transits", json=payload, headers=self.headers, name="POST /v1/chart/transits")

    @task(2)
    def chart_render_data(self):
        payload = {
            "year": 1992,
            "month": 8,
            "day": 12,
            "hour": 10,
            "minute": 30,
            "second": 0,
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
            "house_system": "P",
            "zodiac_type": "tropical",
        }
        self.client.post("/v1/chart/render-data", json=payload, headers=self.headers, name="POST /v1/chart/render-data")

    @task(1)
    def ai_cosmic_chat(self):
        payload = {
            "user_question": "Qual energia do meu dia?",
            "astro_payload": {
                "sun": "Leo",
                "moon": "Pisces",
                "ascendant": "Sagittarius",
            },
            "tone": "objetivo",
            "language": "pt-BR",
        }
        self.client.post("/v1/ai/cosmic-chat", json=payload, headers=self.headers, name="POST /v1/ai/cosmic-chat")
