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

## Retorno solar

Exemplo com payload completo (natal, alvo e preferências) e resposta resumida.

```bash
curl -X POST "$API_URL/v1/solar-return/calculate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "natal": {
      "year": 1995,
      "month": 11,
      "day": 7,
      "hour": 22,
      "minute": 56,
      "second": 0,
      "lat": -23.5505,
      "lng": -46.6333,
      "timezone": "America/Sao_Paulo"
    },
    "alvo": {
      "year": 2025,
      "lat": -22.9068,
      "lng": -43.1729,
      "timezone": "America/Sao_Paulo"
    },
    "preferencias": {
      "house_system": "P",
      "zodiac_type": "tropical",
      "language": "pt-BR"
    }
  }'
```

Resposta (campos principais + metadados):

```json
{
  "solar_return_date": "2025-11-07T09:14:22-03:00",
  "location": {
    "lat": -22.9068,
    "lng": -43.1729,
    "timezone": "America/Sao_Paulo"
  },
  "sun": {
    "sign": "Scorpio",
    "sign_pt": "Escorpião",
    "degree": 14.32
  },
  "houses": [
    {
      "house": 1,
      "sign": "Sagittarius",
      "sign_pt": "Sagitário",
      "degree": 2.18
    },
    {
      "house": 10,
      "sign": "Virgo",
      "sign_pt": "Virgem",
      "degree": 29.44
    }
  ],
  "planets": [
    {
      "name": "Moon",
      "sign": "Aries",
      "sign_pt": "Áries",
      "degree": 8.51
    },
    {
      "name": "Mars",
      "sign": "Leo",
      "sign_pt": "Leão",
      "degree": 21.07
    }
  ],
  "meta": {
    "request_id": "b2b8d2a1-7d4e-4b6b-9d2e-ccb6f1e2c90b",
    "cached": false,
    "generated_at": "2025-08-12T18:40:12Z",
    "version": "1.1.1"
  }
}
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
