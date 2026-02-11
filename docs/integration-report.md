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
