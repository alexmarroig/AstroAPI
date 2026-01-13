# Fixtures de referência

## Origem dos dados

Os dados de `tests/fixtures/solar_return_reference.jsonl` foram gerados com o engine interno `v2` de retorno solar, usando a implementação em `astro/solar_return.py` (que depende do Swiss Ephemeris via `swisseph`). Cada caso foi calculado com o mesmo algoritmo usado pela API, e os valores esperados refletem o UTC do retorno solar e a longitude do Sol nesse instante.

Comando utilizado para gerar os valores de referência:

```bash
python - <<'PY'
import json
from datetime import datetime

from astro.solar_return import SolarReturnInputs, compute_solar_return_payload

cases = [
    {
        "case_id": "sao-paulo-1995-2026",
        "natal": {
            "data": "1995-11-07",
            "hora": "22:56:00",
            "timezone": "America/Sao_Paulo",
            "local": {"nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333},
        },
        "alvo": {
            "ano": 2026,
            "timezone": "America/Sao_Paulo",
            "local": {"nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333},
        },
    },
    {
        "case_id": "nyc-1988-2024-london",
        "natal": {
            "data": "1988-04-15",
            "hora": "08:30:00",
            "timezone": "America/New_York",
            "local": {"nome": "New York, US", "lat": 40.7128, "lon": -74.0060},
        },
        "alvo": {
            "ano": 2024,
            "timezone": "Europe/London",
            "local": {"nome": "London, UK", "lat": 51.5074, "lon": -0.1278},
        },
    },
    {
        "case_id": "tokyo-2001-2025-sydney",
        "natal": {
            "data": "2001-09-11",
            "hora": "09:45:00",
            "timezone": "Asia/Tokyo",
            "local": {"nome": "Tokyo, JP", "lat": 35.6762, "lon": 139.6503},
        },
        "alvo": {
            "ano": 2025,
            "timezone": "Australia/Sydney",
            "local": {"nome": "Sydney, AU", "lat": -33.8688, "lon": 151.2093},
        },
    },
]

for case in cases:
    natal = case["natal"]
    alvo = case["alvo"]
    natal_dt = datetime.fromisoformat(f"{natal['data']}T{natal['hora']}")
    inputs = SolarReturnInputs(
        natal_date=natal_dt,
        natal_lat=natal["local"]["lat"],
        natal_lng=natal["local"]["lon"],
        natal_timezone=natal["timezone"],
        target_year=alvo["ano"],
        target_lat=alvo["local"]["lat"],
        target_lng=alvo["local"]["lon"],
        target_timezone=alvo["timezone"],
        house_system="P",
        zodiac_type="tropical",
        ayanamsa=None,
        engine="v2",
    )
    payload = compute_solar_return_payload(inputs)
    return_utc = payload["metadados_tecnicos"]["solar_return_utc"]
    sun_lon = payload["mapa_revolucao"]["planetas"]["Sun"]["lon"]
    case["esperado"] = {
        "solar_return_utc": return_utc,
        "sun_longitude_graus": round(sun_lon, 6),
        "tolerancia_graus": 0.01,
    }
    print(json.dumps(case, ensure_ascii=False))
PY
```
