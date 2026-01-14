# AstroAPI Examples (PT-BR)

## Cabeçalhos comuns (quando houver auth)
- `Authorization: Bearer $API_KEY`
- `X-User-Id: user_123`
- `Content-Type: application/json`

## /v1/time/validate-local-datetime

### Horário ambíguo (fim do DST) com `strict=true`

**cURL**
```bash
curl -X POST "$API_URL/v1/time/validate-local-datetime" \
  -H "Content-Type: application/json" \
  -d '{
    "datetime_local": "2024-11-03T01:30:00",
    "timezone": "America/New_York",
    "strict": true
  }'
```

**Response (exemplo)**
```json
{
  "detail": {
    "detail": "Horário ambíguo na transição de horário de verão.",
    "offset_options_minutes": [-300, -240],
    "hint": "Envie tz_offset_minutes explicitamente ou ajuste o horário local."
  }
}
```

### Horário ambíguo (fim do DST) com `strict=false`

**cURL**
```bash
curl -X POST "$API_URL/v1/time/validate-local-datetime" \
  -H "Content-Type: application/json" \
  -d '{
    "datetime_local": "2024-11-03T01:30:00",
    "timezone": "America/New_York",
    "strict": false
  }'
```

**Response (exemplo)**
```json
{
  "datetime_local": "2024-11-03T01:30:00",
  "timezone": "America/New_York",
  "tz_offset_minutes": -240,
  "status": "ok"
}
```

### Horário inexistente (início do DST)

**cURL**
```bash
curl -X POST "$API_URL/v1/time/validate-local-datetime" \
  -H "Content-Type: application/json" \
  -d '{
    "datetime_local": "2024-03-10T02:30:00",
    "timezone": "America/New_York",
    "strict": true
  }'
```

**Response (exemplo)**
```json
{
  "detail": "Horário inexistente na transição de horário de verão."
}
```

## /v1/chart/natal

**cURL**
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

**Response (exemplo)**
```json
{
  "utc_datetime": "1995-11-08T00:56:00",
  "houses": { "system": "Placidus", "cusps": [0.0], "asc": 0.0, "mc": 0.0 },
  "planets": { "Sun": { "lon": 0.0, "sign": "Scorpio", "deg_in_sign": 15.14 } },
  "planetas_ptbr": { "Sol": { "nome_ptbr": "Sol", "signo_ptbr": "Escorpião" } },
  "casas_ptbr": { "system_ptbr": "Placidus" },
  "metadados_tecnicos": { "idioma": "pt-BR", "fonte_traducao": "backend" }
}
```

**Notas de normalização (astro-proxy)**: usar `natal_*` (pass-through).

## /v1/chart/transits

**cURL**
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

**Response (exemplo)**
```json
{
  "date": "2026-01-09",
  "cosmic_weather": { "moon_phase": "waxing", "moon_sign": "Aries" },
  "cosmic_weather_ptbr": { "moon_sign_ptbr": "Áries" },
  "natal": { "planets": {} },
  "natal_ptbr": { "planetas_ptbr": {} },
  "transits": { "planets": {} },
  "transits_ptbr": { "planetas_ptbr": {} },
  "aspects": [],
  "aspectos_ptbr": []
}
```

**Notas de normalização**: usar `natal_*` (pass-through).

## /v1/transits/events

**cURL**
```bash
curl -X POST "$API_URL/v1/transits/events" \
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
    "range": { "from": "2026-11-07", "to": "2026-11-08" },
    "preferencias": { "perfil": "padrao" }
  }'
```

**Response (exemplo)**
```json
{
  "events": [
    {
      "event_id": "7af5c1b2...",
      "date_range": { "start_utc": "2026-11-07T00:00:00Z", "peak_utc": "2026-11-07T12:00:00Z", "end_utc": "2026-11-07T23:59:59Z" },
      "transitando": "Marte",
      "alvo_tipo": "PLANETA_NATAL",
      "alvo": "Sol",
      "aspecto": "Quadratura",
      "orb_graus": 1.2,
      "casa_ativada": 10,
      "tags": ["Ação", "Ajuste"],
      "severidade": "MEDIA",
      "impact_score": 58.4,
      "copy": {
        "headline": "Marte em Quadratura com Sol",
        "mecanica": "Trânsito enfatiza ação em temas ligados a Sol.",
        "use_bem": "Tendência a favorecer clareza e ação prática quando você organiza prioridades.",
        "risco": "Pede atenção a impulsos e excesso de carga; ajuste o ritmo com consistência."
      }
    }
  ],
  "metadados": { "range": { "from": "2026-11-07", "to": "2026-11-08" } },
  "avisos": []
}
```

**Notas de normalização**: usar `natal_*` (pass-through).

## /v1/chart/render-data

**cURL**
```bash
curl -X POST "$API_URL/v1/chart/render-data" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "year": 1995,
    "month": 11,
    "day": 7,
    "hour": 22,
    "minute": 56,
    "second": 0,
    "lat": -23.5505,
    "lng": -46.6333,
    "timezone": "America/Sao_Paulo",
    "house_system": "P",
    "zodiac_type": "tropical"
  }'
```

**Response (exemplo)**
```json
{
  "houses": [{ "house": 1, "start_deg": 0.0, "end_deg": 30.0 }],
  "planets": [{ "name": "Sun", "sign": "Scorpio" }],
  "planetas_ptbr": [{ "nome_ptbr": "Sol", "signo_ptbr": "Escorpião" }],
  "casas_ptbr": [{ "house": 1, "label_ptbr": "Casa 1: 0°00' Áries → 0°00' Touro" }]
}
```

**Notas de normalização**: deve usar `year/month/day/hour` (sem `natal_*`).

## /v1/cosmic-weather

**cURL**
```bash
curl -X GET "$API_URL/v1/cosmic-weather?date=2024-05-01&timezone=America/Sao_Paulo" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123"
```

**Response (exemplo)**
```json
{
  "date": "2024-05-01",
  "moon_phase": "waxing",
  "moon_sign": "Aries",
  "headline": "Lua Crescente em Aries",
  "moon_ptbr": { "signo_ptbr": "Áries", "fase_ptbr": "Crescente" },
  "top_event": null,
  "trigger_event": null,
  "secondary_events": [],
  "summary": { "tom": "Fase de avanço com energia de construção.", "gatilho": "Tendência a buscar progresso em temas de Áries.", "acao": "Escolha uma meta prática e execute em etapas curtas." }
}
```

**Opcional (curadoria com mapa natal)**: envie `natal_year`, `natal_month`, `natal_day`, `natal_hour`, `lat`, `lng` e `timezone` como query params para preencher `top_event`, `trigger_event` e `secondary_events`.

## /v1/cosmic-weather/range

**cURL**
```bash
curl -X GET "$API_URL/v1/cosmic-weather/range?from=2024-05-01&to=2024-05-07" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123"
```

**Response (exemplo)**
```json
{
  "from": "2024-05-01",
  "to": "2024-05-07",
  "items": [{ "date": "2024-05-01", "moon_sign": "Aries" }],
  "items_ptbr": [{ "date": "2024-05-01", "moon_sign_ptbr": "Áries" }]
}
```

**Regra de intervalo**: máximo de 90 dias (inclusive).

## /v1/solar-return/calculate

**cURL**
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
      "local": { "nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333, "alt_m": 760 }
    },
    "alvo": {
      "ano": 2026,
      "timezone": "America/Sao_Paulo",
      "local": { "nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333, "alt_m": 760 }
    },
    "preferencias": { "zodiaco": "tropical", "sistema_casas": "P", "modo": "geocentrico" }
  }'
```

**Response (exemplo)**
```json
{
  "metadados_tecnicos": { "engine": "v2", "solar_return_utc": "2026-11-07T13:12:27" },
  "mapa_revolucao": { "planetas": {}, "casas": {}, "aspectos": [] },
  "areas_ativadas": [],
  "destaques": []
}
```

**Notas de normalização**: PASS-THROUGH (não normalizar).

## /v1/solar-return/overlay

**cURL**
```bash
curl -X POST "$API_URL/v1/solar-return/overlay" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "natal": {
      "data": "1995-11-07",
      "hora": "22:56:00",
      "timezone": "America/Sao_Paulo",
      "local": { "nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333, "alt_m": 760 }
    },
    "alvo": {
      "ano": 2026,
      "timezone": "America/Sao_Paulo",
      "local": { "nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333, "alt_m": 760 }
    },
    "rs": { "year": 2026 },
    "preferencias": { "perfil": "padrao" }
  }'
```

**Response (exemplo)**
```json
{
  "rs_em_casas_natais": [{ "planeta_rs": "Sol", "casa_natal": 10 }],
  "natal_em_casas_rs": [{ "planeta_natal": "Sol", "casa_rs": 3 }],
  "aspectos_rs_x_natal": [{ "transitando": "Sol", "alvo": "Lua", "aspecto": "Trígono", "orb_graus": 2.1 }],
  "avisos": [],
  "metadados": { "perfil": "padrao" }
}
```

## /v1/solar-return/timeline

**cURL**
```bash
curl -X POST "$API_URL/v1/solar-return/timeline" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "natal": {
      "data": "1995-11-07",
      "hora": "22:56:00",
      "timezone": "America/Sao_Paulo",
      "local": { "nome": "São Paulo, BR", "lat": -23.5505, "lon": -46.6333, "alt_m": 760 }
    },
    "year": 2026,
    "preferencias": { "perfil": "padrao" }
  }'
```

**Response (exemplo)**
```json
{
  "year_timeline": [
    {
      "start": "2026-03-20",
      "peak": "2026-03-21",
      "end": "2026-03-22",
      "method": "solar_aspects",
      "trigger": "Sol em Conjunção com Sol",
      "tags": ["Ano", "Direção", "Ajuste"],
      "score": 68.2
    }
  ],
  "avisos": [],
  "metadados": { "perfil": "padrao" }
}
```

## /v1/chart/distributions

**cURL**
```bash
curl -X POST "$API_URL/v1/chart/distributions" \
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
    "timezone": "America/Sao_Paulo"
  }'
```

**Response (exemplo)**
```json
{
  "elementos": { "Fogo": 3, "Terra": 2, "Ar": 2, "Água": 3 },
  "modalidades": { "Cardinal": 3, "Fixo": 4, "Mutável": 3 },
  "casas": [{ "casa": 1, "contagem": 2, "planetas": ["Sol"] }],
  "dominancias": { "elemento_dominante": "Fogo", "modalidade_dominante": "Fixo", "casas_mais_ativadas": [1, 10, 7] },
  "metadados": { "fonte": "natal", "version": "v1" }
}
```

**Notas de normalização**: usa `natal_*` (pass-through).

## /v1/interpretation/natal

**cURL**
```bash
curl -X POST "$API_URL/v1/interpretation/natal" \
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
    "timezone": "America/Sao_Paulo"
  }'
```

**Response (exemplo)**
```json
{
  "titulo": "Resumo Geral do Mapa",
  "sintese": ["Sol em Escorpião aponta foco em temas de vida mais visíveis."],
  "temas_principais": [{ "titulo": "Foco solar", "porque": "Sol em Escorpião na casa 8." }],
  "planetas_com_maior_peso": [{ "planeta": "Sol", "peso": 0.92, "porque": "Casa 8 com influência de ângulos (3.2°)." }],
  "distribuicao": { "elementos": { "Fogo": 3, "Terra": 2, "Ar": 2, "Água": 3 } },
  "avisos": [],
  "metadados": { "version": "v1", "fonte": "regras" }
}
```

**Notas de normalização**: usa `natal_*` (pass-through).

## /v1/lunations/calculate

**cURL**
```bash
curl -X POST "$API_URL/v1/lunations/calculate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{ "date": "2024-05-01", "timezone": "America/Sao_Paulo" }'
```

**Response (exemplo)**
```json
{
  "date": "2024-05-01",
  "phase": "first_quarter",
  "phase_pt": "Quarto Crescente",
  "moon_sign": "Aries",
  "moon_sign_pt": "Áries",
  "sun_sign": "Taurus",
  "sun_sign_pt": "Touro"
}
```

## /v1/progressions/secondary/calculate

**cURL**
```bash
curl -X POST "$API_URL/v1/progressions/secondary/calculate" \
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
    "target_date": "2026-11-07"
  }'
```

**Response (exemplo)**
```json
{
  "titulo": "Resumo Geral do Mapa",
  "sintese": ["Sol em Escorpião aponta foco em temas de vida mais visíveis."],
  "temas_principais": [{ "titulo": "Foco solar", "porque": "Sol em Escorpião na casa 8." }],
  "planetas_com_maior_peso": [{ "planeta": "Sol", "peso": 0.92, "porque": "Casa 8 com influência de ângulos (3.2°)." }],
  "distribuicao": { "elementos": { "Fogo": 3, "Terra": 2, "Ar": 2, "Água": 3 } },
  "avisos": [],
  "metadados": { "version": "v1", "fonte": "regras" }
}
```

**Notas de normalização**: usa `natal_*` (pass-through).

## /v1/lunations/calculate

**cURL**
```bash
curl -X POST "$API_URL/v1/lunations/calculate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{ "date": "2024-05-01", "timezone": "America/Sao_Paulo" }'
```

**Response (exemplo)**
```json
{
  "date": "2024-05-01",
  "phase": "first_quarter",
  "phase_pt": "Quarto Crescente",
  "moon_sign": "Aries",
  "moon_sign_pt": "Áries",
  "sun_sign": "Taurus",
  "sun_sign_pt": "Touro"
}
```

## /v1/progressions/secondary/calculate

**cURL**
```bash
curl -X POST "$API_URL/v1/progressions/secondary/calculate" \
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
    "target_date": "2026-11-07"
  }'
```

**Response (exemplo)**
```json
{
  "natal_datetime_local": "1995-11-07T22:56:00",
  "target_date": "2026-11-07",
  "progressed_datetime_local": "1995-12-13T22:56:00",
  "age_years": 31.0,
  "chart": {},
  "chart_ptbr": { "planetas_ptbr": {}, "casas_ptbr": {} }
}
```

## /v1/ai/cosmic-chat

**cURL**
```bash
curl -X POST "$API_URL/v1/ai/cosmic-chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-User-Id: user_123" \
  -d '{
    "user_question": "Quais temas principais aparecem no meu mapa?",
    "astro_payload": { "natal": {}, "transits": {} },
    "tone": "calmo, adulto, tecnológico",
    "language": "pt-BR"
  }'
```

**Response (exemplo)**
```json
{
  "response": "Texto de resposta...",
  "model": "gpt-4o-mini",
  "usage": { "prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30 },
  "metadados_tecnicos": { "idioma": "pt-BR", "fonte_traducao": "backend" }
}
```

## /v1/time/validate-local-datetime

**cURL (horário ambíguo — fim do DST)**
```bash
curl -X POST "$API_URL/v1/time/validate-local-datetime" \
  -H "Content-Type: application/json" \
  -d '{
    "datetime_local": "2024-11-03T01:30:00",
    "timezone": "America/New_York",
    "strict": false
  }'
```

**Response (exemplo)**
```json
{
  "status": "ambiguous",
  "is_valid": true,
  "offset_options_minutes": [-300, -240],
  "resolved_offset_minutes": -300,
  "fold": 0
}
```

**cURL (horário inexistente — início do DST)**
```bash
curl -X POST "$API_URL/v1/time/validate-local-datetime" \
  -H "Content-Type: application/json" \
  -d '{
    "datetime_local": "2024-03-10T02:30:00",
    "timezone": "America/New_York",
    "strict": true
  }'
```

**Response (exemplo)**
```json
{
  "detail": "Horário inexistente na transição de horário de verão.",
  "hint": "Ajuste o horário local ou envie outro horário válido."
}
```

**cURL (preferindo o segundo horário na ambiguidade)**
```bash
curl -X POST "$API_URL/v1/time/validate-local-datetime" \
  -H "Content-Type: application/json" \
  -d '{
    "datetime_local": "2024-11-03T01:30:00",
    "timezone": "America/New_York",
    "strict": false,
    "prefer_fold": 1
  }'
```

**Response (exemplo)**
```json
{
  "status": "ambiguous",
  "is_valid": true,
  "offset_options_minutes": [-300, -240],
  "resolved_offset_minutes": -240,
  "fold": 1
}
```

**Notas**
- `strict=true` faz o endpoint rejeitar horários ambíguos (fim do DST) e inexistentes (início do DST) com erro 400, garantindo validação rígida do horário local.
- `prefer_fold` permite escolher qual instância usar quando o horário é ambíguo (`0` = primeira ocorrência, `1` = segunda ocorrência), mantendo a consistência do offset retornado.

## Erros comuns
- **401**: faltando `Authorization` ou `X-User-Id` em endpoints protegidos.
- **400**: data inválida (formato YYYY-MM-DD) ou timezone inválido.
- **422**: payload incompleto ou campos fora do intervalo permitido.

> Proxy/Edge: não normalize payloads de `/v1/solar-return/calculate` para `natal_*`. Esse endpoint espera os campos de revolução solar conforme o schema acima.

## Frontend Quick Start
- **Base URL**: `https://<sua-base-url>`
- **Headers**: `Authorization: Bearer <API_KEY>`, `X-User-Id: <user_id>`
- **Sequência recomendada**:
  1) `POST /v1/time/resolve-tz` (quando necessário)
  2) `POST /v1/chart/render-data`
  3) `POST /v1/chart/natal`
  4) `POST /v1/chart/distributions`
  5) `POST /v1/interpretation/natal`
  6) `POST /v1/solar-return/calculate`
- **Observação**: PWA não requer mudanças no backend.
