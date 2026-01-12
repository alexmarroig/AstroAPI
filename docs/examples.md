# AstroAPI Examples

## Natal chart

```bash
curl -X POST "$API_URL/v1/chart/natal" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "natal_year": 1995,
    "natal_month": 11,
    "natal_day": 7,
    "natal_hour": 22,
    "natal_minute": 56,
    "natal_second": 0,
    "lat": -23.5505,
    "lng": -46.6333,
    "timezone": "America/Sao_Paulo",
    "house_system": "P",
    "zodiac_type": "tropical"
  }'
```

## Transits

```bash
curl -X POST "$API_URL/v1/chart/transits" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "natal_year": 1995,
    "natal_month": 11,
    "natal_day": 7,
    "natal_hour": 22,
    "natal_minute": 56,
    "natal_second": 0,
    "lat": -23.5505,
    "lng": -46.6333,
    "timezone": "America/Sao_Paulo",
    "target_date": "2026-01-09",
    "house_system": "P",
    "zodiac_type": "tropical"
  }'
```

## Render data (UI)

```bash
curl -X POST "$API_URL/v1/chart/render-data" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "natal_year": 1995,
    "natal_month": 11,
    "natal_day": 7,
    "natal_hour": 22,
    "natal_minute": 56,
    "natal_second": 0,
    "lat": -23.5505,
    "lng": -46.6333,
    "timezone": "America/Sao_Paulo",
    "house_system": "P",
    "zodiac_type": "tropical"
  }'
```

## Retrogrades alerts

```bash
curl -X GET "$API_URL/v1/alerts/retrogrades?date=2024-01-01&timezone=Etc/UTC"
```

## Cosmic weather (range)

`from` e `to` são opcionais. Quando ausentes, o backend assume `today..today+6`. O intervalo máximo é de 90 dias.

```bash
curl -X GET "$API_URL/v1/cosmic-weather/range?from=2024-05-01&to=2024-05-07" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123"
```

```bash
curl -X GET "$API_URL/v1/cosmic-weather/range" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123"
```

## Revolução Solar

```bash
curl -X POST "$API_URL/v1/solar-return/calculate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "natal": {
      "data": "1995-11-07",
      "hora": "22:56:00",
      "timezone": "America/Sao_Paulo",
      "local": {
        "nome": "São Paulo, BR",
        "lat": -23.5505,
        "lon": -46.6333,
        "alt_m": 760
      }
    },
    "alvo": {
      "ano": 2026,
      "timezone": "America/Sao_Paulo",
      "local": {
        "nome": "São Paulo, BR",
        "lat": -23.5505,
        "lon": -46.6333,
        "alt_m": 760
      }
    },
    "preferencias": {
      "zodiaco": "tropical",
      "sistema_casas": "P",
      "modo": "geocentrico"
    }
  }'
```

> Proxy/Edge: não normalize payloads de `/v1/solar-return/calculate` para `natal_*`. Esse endpoint espera os campos de revolução solar conforme o schema acima.
