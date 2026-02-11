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
# Relatório rápido — contrato Lovable ↔ Proxy ↔ AstroAPI

## Endpoints mínimos validados
- `POST /v1/time/resolve-tz`
- `POST /v1/chart/render-data`
- `POST /v1/interpretation/natal`
- `POST /v1/ai/cosmic-chat`
- `POST /v1/solar-return/calculate`
- `POST /v1/solar-return/timeline`
- `GET /v1/cosmic-weather/range`

## Auth backend compatível com o proxy
Backend exige exatamente:
- `Authorization: Bearer <API_KEY>`
- `X-User-Id: <userId>`

Erros explícitos:
- token inválido/ausente: `401`
- `X-User-Id` ausente: `401`

## Payloads aceitos (snake_case + camelCase)

### Nascimento (natal/transits/interpretation)
Aceitos:
- `birth_date` / `birthDate`
- `birth_time` / `birthTime`
- `birth_datetime` / `birthDateTime` / `birthDatetime`
- componentes numéricos: `year/month/day/hour/minute/second` e `natal_year/...`

Regras:
- `birthTime` vazio/null → assume `12:00` explicitamente.
- função central `normalize_birth_payload(data)` converte para um formato interno único (`datetime_local`, `timezone`, `tz_offset_minutes`, `lat`, `lng`).
- `lat`/`latitude` e `lng`/`longitude` são aceitos.
Normalização interna: parser converte para um único `datetime` e os schemas preenchem os campos internos `natal_*` e/ou `year/month/...`.

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


## Exemplos rápidos

### Interpretation (camelCase)
```json
{
  "birthDate": "1990-09-15",
  "birthTime": "10:30",
  "lat": -23.5505,
  "lng": -46.6333,
  "timezone": "America/Sao_Paulo"
}
```

### Interpretation (snake_case)
```json
{
  "birth_date": "1990-09-15",
  "birth_time": "10:30:00",
  "lat": -23.5505,
  "lng": -46.6333,
  "timezone": "America/Sao_Paulo"
}
```

### AI cosmic-chat (camelCase)
```json
{
  "userQuestion": "Resumo curto do meu momento atual",
  "astroPayload": {"sun": "Virgo", "moon": "Aries"},
  "language": "pt-BR"
}
```

## Execução de testes de contrato
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
## Resultado esperado
- Nenhum endpoint crítico retorna `422` por divergência `camelCase` vs `snake_case`.
- Contratos de auth e shape JSON mantidos estáveis para front/proxy.
# Relatório de integração Lovable ↔ AstroAPI

## a) Endpoints que o frontend/proxy exige

### Núcleo astrológico
- `POST /v1/chart/distributions`
- `POST /v1/interpretation/natal`
- `POST /v1/chart/render-data`
- `POST /v1/chart/transits`

### IA / chat
- `POST /v1/ai/cosmic-chat`
- `POST /api/chat/astral-oracle` (compatibilidade do módulo Inner Sky)

### Tempo / timezone
- `POST /v1/time/resolve-tz`
- `POST /v1/time/validate-local-datetime`

### Revolução solar
- `POST /v1/solar-return/calculate`
- `POST /v1/solar-return/timeline`
- `POST /v1/solar-return/overlay`

### Clima cósmico / timeline
- `GET /v1/cosmic-weather`
- `GET /v1/cosmic-weather/range`
- `GET /v1/moon/timeline`

### Progressões / lunações
- `POST /v1/progressions/secondary/calculate`
- `POST /v1/lunations/calculate`

## b) Autenticação

Validação confirmada para o contrato esperado pelo proxy:
- `Authorization: Bearer <API_KEY>`
- `X-User-Id: <userId>`

O backend rejeita explicitamente token inválido e ausência de `X-User-Id`.

## c) Inconsistências de payload encontradas

### Antes das correções
- O backend aceitava melhor `snake_case` (`birth_date`, `birth_time`, `birth_datetime`) do que `camelCase` (`birthDate`, `birthTime`), gerando risco de 422 quando o front enviava contrato camelCase.
- `CosmicChatRequest` aceitava `user_question`/`astro_payload`, mas não aliases camelCase (`userQuestion`/`astroPayload`).
- `resolve_birth_datetime_payload` só lia chaves snake_case.

### Após as correções
- Backend passou a aceitar ambos formatos (`snake_case` e `camelCase`) para campos de nascimento.
- Backend passou a aceitar ambos formatos para payload de chat IA.
- `TimezoneResolveRequest` passou a aceitar aliases camelCase (`datetimeLocal`, `strictBirth`, `preferFold`).

## d) Mudanças aplicadas no backend

- Parsing robusto de data/hora de nascimento (`birthDate`, `birthTime`, `birthDateTime`) em `services/time_utils.py`.
- Aliases de contrato em `schemas/chart.py` e `schemas/transits.py` para aceitar camelCase + snake_case.
- Aliases em `schemas/ai.py` para `userQuestion` e `astroPayload`.
- Aliases em `schemas/time.py` para `datetimeLocal`, `strictBirth`, `preferFold`.

## e) Script de testes de contrato

Arquivo: `scripts/contract_test_proxy_backend.py`

Esse script:
1. Simula envelope `{ path, method, body/query }` do front/proxy.
2. Simula headers que o proxy injeta no backend (`Authorization`, `X-User-Id`, `Content-Type`).
3. Executa e valida os contratos essenciais de:
   - `/v1/time/resolve-tz`
   - `/v1/chart/render-data`
   - `/v1/interpretation/natal`
   - `/v1/ai/cosmic-chat`
   - `/v1/solar-return/calculate`
   - `/v1/solar-return/timeline`
   - `/v1/cosmic-weather/range`
