# Relatório de integração — Lovable ↔ Supabase proxy ↔ AstroAPI

## 1) Inventário de contrato (endpoints do `astroApi`)

| Método | Path | Body mínimo aceito | Resposta mínima esperada |
|---|---|---|---|
| POST | `/v1/chart/distributions` | `birthDate/birthTime` **ou** `birth_date/birth_time` **ou** `year/month/day/hour...`, `lat`, `lng`, `timezone` ou `tz_offset_minutes` | `elements`, `modalities`, `houses` |
| POST | `/v1/interpretation/natal` | mesmo contrato de nascimento acima | `titulo`, `sintese`, `summary` |
| POST | `/v1/solar-return/calculate` | `natal{data,hora,timezone,local{lat,lon}}`, `alvo{ano,local{lat,lon}}` | `mapa_revolucao`, `metadados_tecnicos` |
| POST | `/v1/solar-return/timeline` | `natal{...}`, `year` | `year_timeline`, `metadados` |
| POST | `/v1/progressions/secondary/calculate` | `birthDate/birthTime` ou `birth_date/birth_time` ou `year...`, `targetDate/target_date`, `lat`, `lng`, `timezone` ou `tz_offset_minutes` | `target_date`, `chart`, `tz_offset_minutes` |
| POST | `/v1/lunations/calculate` | `date` ou `targetDate`, `timezone` ou `tz_offset_minutes` | `date`, `phase`, `moon_sign` |
| GET | `/v1/cosmic-weather/range` | query `from`, `to`, `timezone` (ou `tz_offset_minutes`) | `from`, `to`, `items` |
| POST | `/v1/ai/cosmic-chat` | `userQuestion/user_question`, `astroPayload/astro_payload` | `response`, `usage` (ou erro 503 estável quando IA indisponível) |
| POST | `/v1/time/resolve-tz` | `datetimeLocal/datetime_local` ou `year/month/day/hour...`, `timezone` | `tz_offset_minutes`, `metadados_tecnicos` |
| POST (compat) | `/api/chat/astral-oracle` | `question`, `context` | `success`, `answer`, `theme` |

## 2) Auth backend compatível com proxy

Backend protegido exige:
- `Authorization: Bearer <API_KEY>`
- `X-User-Id: <userId>` (obrigatório)

Códigos de erro padronizados:
- token inválido/ausente: `401`
- `X-User-Id` ausente: `400`
- bloqueio por limite/plano: `429`

## 3) Normalização de payload (snake_case + camelCase)

### Nascimento
Aceitos em todos os fluxos principais:
- `birth_date` / `birthDate`
- `birth_time` / `birthTime`
- `birth_datetime` / `birthDateTime` / `birthDatetime`
- componentes numéricos: `year/month/day/hour/minute/second` e `natal_year/...`

Regras:
- `birthTime` vazio/null → assume `12:00` explicitamente.
- função central `normalize_birth_payload(data)` converte para um formato interno único (`datetime_local`, `timezone`, `tz_offset_minutes`, `lat`, `lng`).
- `lat`/`latitude` e `lng`/`longitude` são aceitos.

### IA
Aceitos:
- `user_question` / `userQuestion`
- `astro_payload` / `astroPayload`

### Timezone
Aceitos:
- `datetime_local` / `datetimeLocal`
- `strict_birth` / `strictBirth`
- `prefer_fold` / `preferFold`
- `tz_offset_minutes` / `tzOffsetMinutes` (em endpoints compatibilizados)

## 4) Allowlist do proxy (check final)

Validação automática confirma que todos os endpoints críticos acima estão dentro da allowlist do proxy em `supabase/functions/astro-proxy/index.ts`.

## 5) Como rodar contract tests

```bash
python scripts/contract_test_proxy_backend.py
```

O script simula o proxy chamando o backend com:
- `Authorization: Bearer <API_KEY>`
- `X-User-Id`
- `Content-Type: application/json`

e valida status + shape JSON, incluindo cenários de auth inválida.

Cobertura explícita de naming style:
- payload camelCase
- payload snake_case
- payload por componentes `year/month/day/hour/minute/second`

Todos esses cenários passam com `200` para endpoints principais (sem `422` por naming style).
