# Arquitetura do AstroAPI

## Visão geral
O AstroAPI é um backend FastAPI que calcula mapas astrológicos, trânsitos e informações de “cosmic weather”, com cache em memória e um endpoint de chat com IA. A camada de API vive em `main.py`, que orquestra chamadas para módulos de astrologia (`astro/`), segurança/rate limit (`core/`), e prompts para IA (`ai/`).【F:main.py†L1-L911】【F:astro/ephemeris.py†L1-L149】【F:core/security.py†L1-L32】【F:ai/prompts.py†L1-L85】

## Arquitetura
- **API (FastAPI)**: declara rotas, valida requests via Pydantic e aplica middleware de logging/trace ID. Também resolve fuso horário e faz cache de respostas específicas por usuário. 【F:main.py†L1-L911】
- **Astrologia (astro/)**: calcula mapas natais, trânsitos e dados mínimos da Lua usando Swiss Ephemeris. 【F:astro/ephemeris.py†L1-L149】
- **Aspectos (astro/aspects.py)**: gera aspectos entre planetas de trânsito e natal. 【F:astro/aspects.py†L1-L48】
- **IA (ai/prompts.py)**: prepara mensagens do chat e formata contexto astrológico para a OpenAI. 【F:ai/prompts.py†L1-L85】
- **Segurança e limites (core/)**: valida API key, cabeçalhos, plano do usuário e aplica rate limit diário por endpoint. 【F:core/security.py†L1-L32】【F:core/limits.py†L1-L46】【F:core/plans.py†L1-L38】
- **Cache (core/cache.py)**: cache TTL em memória para respostas de endpoints. 【F:core/cache.py†L1-L22】

## Módulos
- **`main.py`**: definição do app, modelos Pydantic, middleware, helpers de timezone/cache, rotas e integração com IA. 【F:main.py†L1-L911】
- **`astro/ephemeris.py`**: funções `compute_chart`, `compute_transits`, `compute_moon_only` baseadas no Swiss Ephemeris. 【F:astro/ephemeris.py†L1-L149】
- **`astro/aspects.py`**: `compute_transit_aspects` para cruzar planetas. 【F:astro/aspects.py†L1-L48】
- **`astro/utils.py`**: utilidades de signos, ângulos e Julian Day. 【F:astro/utils.py†L1-L43】
- **`ai/prompts.py`**: `build_cosmic_chat_messages` e `format_astro_payload`. 【F:ai/prompts.py†L1-L85】
- **`core/security.py`**: `require_api_key_and_user` (auth + rate limit). 【F:core/security.py†L1-L32】
- **`core/limits.py`**: contagem diária e limites por plano/endpoint. 【F:core/limits.py†L1-L46】
- **`core/plans.py`**: controle em memória de planos (trial/free/premium). 【F:core/plans.py†L1-L38】
- **`core/cache.py`**: cache TTL em memória. 【F:core/cache.py†L1-L22】
- **`tests/`**: testes de endpoints e cálculos (health, timezone, cosmic weather, alerts).【F:tests/test_health.py†L1-L8】【F:tests/test_timezone.py†L1-L63】【F:tests/test_cosmic_weather_range.py†L1-L62】

## Endpoints
### Saúde e sistema
- **`GET /`**
  - **Auth**: não exige
  - **Response**: `ok`, `service`, `version`, `commit`, status de envs básicos.
  - **Erros**: não lança erros específicos; exceções são tratadas por handler global. 【F:main.py†L526-L541】
- **`GET /health`**
  - **Auth**: não exige
  - **Response**: `{ "ok": true }` 【F:main.py†L544-L547】
- **`GET /v1/system/roadmap`**
  - **Auth**: não exige
  - **Response**: features planejadas e status. 【F:main.py†L550-L555】【F:main.py†L509-L517】

### Timezone
- **`POST /v1/time/resolve-tz`**
  - **Request model**: `TimezoneResolveRequest`
  - **Auth**: não exige
  - **Response**: `{ "tz_offset_minutes": int }`
  - **Erros**: `400` se timezone inválido; `400` se horário ambíguo e `strict_birth=true`. 【F:main.py†L271-L282】【F:main.py†L432-L479】【F:main.py†L558-L563】

### Mapas e trânsitos
- **`POST /v1/chart/natal`**
  - **Request model**: `NatalChartRequest`
  - **Auth**: `Authorization: Bearer <API_KEY>` + `X-User-Id`
  - **Response**: mapa natal com planetas e casas (payload de `compute_chart`).
  - **Cache**: `TTL_NATAL_SECONDS` (30 dias) por usuário.
  - **Erros**: `400` se timezone ausente/ambígua; `500` para falha de cálculo. 【F:main.py†L120-L188】【F:main.py†L602-L653】【F:main.py†L483-L487】
- **`POST /v1/chart/transits`**
  - **Request model**: `TransitsRequest`
  - **Auth**: obrigatório
  - **Response**: natal, trânsitos, aspectos e bloco `cosmic_weather`.
  - **Cache**: `TTL_TRANSITS_SECONDS` (6h) por usuário/data.
  - **Erros**: `400` para data inválida; `500` para falha de cálculo. 【F:main.py†L189-L247】【F:main.py†L655-L731】【F:main.py†L483-L487】
- **`POST /v1/chart/render-data`**
  - **Request model**: `RenderDataRequest`
  - **Auth**: obrigatório
  - **Response**: dados simplificados de casas/planetas para render gráfico.
  - **Cache**: `TTL_RENDER_SECONDS` (30 dias) por usuário.
  - **Erros**: `500` se casas não retornarem 12 cúspides. 【F:main.py†L284-L334】【F:main.py†L775-L858】【F:main.py†L485-L488】

### Cosmic weather e alertas
- **`GET /v1/cosmic-weather`**
  - **Request params**: `date` (YYYY-MM-DD opcional), `timezone`, `tz_offset_minutes`
  - **Auth**: obrigatório
  - **Response model**: `CosmicWeatherResponse`
  - **Cache**: `TTL_COSMIC_WEATHER_SECONDS` (6h) por usuário/data. 【F:main.py†L234-L240】【F:main.py†L632-L688】【F:main.py†L483-L488】
- **`GET /v1/cosmic-weather/range`**
  - **Request params**: `from`, `to`, `timezone`, `tz_offset_minutes`
  - **Auth**: obrigatório
  - **Response model**: `CosmicWeatherRangeResponse`
  - **Erros**: `400` se `from > to` ou intervalo > 90 dias. 【F:main.py†L242-L247】【F:main.py†L690-L739】
- **`GET /v1/alerts/system`**
  - **Request params**: `date`, `lat`, `lng`, `timezone`, `tz_offset_minutes`
  - **Auth**: obrigatório
  - **Response model**: `SystemAlertsResponse`
  - **Funcionalidade**: alerta de Mercúrio retrógrado baseado em trânsitos. 【F:main.py†L336-L361】【F:main.py†L863-L888】
- **`GET /v1/notifications/daily`**
  - **Request params**: `date` (opcional), `lat`, `lng`, `timezone`, `tz_offset_minutes`
  - **Auth**: obrigatório
  - **Response model**: `NotificationsDailyResponse`
  - **Cache**: `TTL_COSMIC_WEATHER_SECONDS` (6h). 【F:main.py†L363-L371】【F:main.py†L891-L911】

### IA
- **`POST /v1/ai/cosmic-chat`**
  - **Request model**: `CosmicChatRequest`
  - **Auth**: obrigatório
  - **Response**: texto gerado, modelo e uso de tokens.
  - **Erros**: `500` se `OPENAI_API_KEY` não configurada ou falha da OpenAI. 【F:main.py†L248-L252】【F:main.py†L801-L848】

## Fluxos
### 1) Mapa natal
1. Cliente envia `POST /v1/chart/natal` com data/hora, localização e timezone/offset. 【F:main.py†L120-L188】【F:main.py†L602-L653】
2. `get_auth` valida API key, `X-User-Id` e rate limit. 【F:main.py†L103-L114】【F:core/security.py†L1-L32】
3. `_tz_offset_for` resolve timezone (IANA ou offset) e trata DST ambíguo se `strict_timezone=true`. 【F:main.py†L432-L479】
4. Cache por usuário é consultado e, se necessário, calcula-se `compute_chart` via Swiss Ephemeris. 【F:main.py†L612-L646】【F:astro/ephemeris.py†L29-L96】
5. Resposta é armazenada no cache e enviada ao cliente. 【F:main.py†L648-L653】

### 2) Trânsitos
1. Cliente envia `POST /v1/chart/transits` com dados natais e `target_date`. 【F:main.py†L189-L247】【F:main.py†L655-L731】
2. API valida auth, resolve timezone e verifica cache. 【F:main.py†L103-L114】【F:main.py†L655-L672】
3. `compute_chart` gera o mapa natal; `compute_transits` gera mapa do dia alvo. 【F:main.py†L674-L698】【F:astro/ephemeris.py†L29-L118】
4. `compute_transit_aspects` calcula aspectos entre planetas. 【F:main.py†L700-L706】【F:astro/aspects.py†L11-L48】
5. `compute_moon_only` complementa o bloco de `cosmic_weather`. 【F:main.py†L708-L724】【F:astro/ephemeris.py†L121-L149】

### 3) Render data
1. Cliente envia `POST /v1/chart/render-data`. 【F:main.py†L284-L334】【F:main.py†L775-L858】
2. Autenticação/rate limit via `get_auth` e resolução de timezone. 【F:main.py†L103-L114】【F:main.py†L778-L788】
3. `compute_chart` retorna casas e planetas; API converte em uma estrutura amigável ao front (casas com graus, planetas em lista). 【F:main.py†L790-L851】【F:astro/ephemeris.py†L29-L96】
4. Resposta é cacheada e enviada. 【F:main.py†L855-L858】

### 4) Cosmic weather
1. Cliente chama `GET /v1/cosmic-weather` ou `GET /v1/cosmic-weather/range`. 【F:main.py†L632-L739】
2. API resolve fuso e consulta cache (por usuário/data). 【F:main.py†L494-L507】【F:main.py†L632-L673】
3. `compute_moon_only` calcula Lua, fase e signo; API monta headline/texto. 【F:main.py†L504-L507】【F:main.py†L485-L488】【F:astro/ephemeris.py†L121-L149】

### 5) AI chat
1. Cliente envia `POST /v1/ai/cosmic-chat` com pergunta e payload astrológico. 【F:main.py†L248-L252】【F:main.py†L801-L848】
2. API valida auth, lê `OPENAI_API_KEY` e monta prompts com `build_cosmic_chat_messages`. 【F:main.py†L801-L828】【F:ai/prompts.py†L23-L57】
3. Chamada à OpenAI é feita com limites de tokens por plano. 【F:main.py†L818-L834】
4. Retorna texto e métricas de uso. 【F:main.py†L836-L845】

## Modelos
### Pydantic (requests/responses)
- **`NatalChartRequest`**: dados natalícios, geo e timezone/offset. 【F:main.py†L120-L188】
- **`TransitsRequest`**: dados natalícios + `target_date`. 【F:main.py†L189-L247】
- **`RenderDataRequest`**: dados de renderização de mapa. 【F:main.py†L284-L334】
- **`TimezoneResolveRequest`**: `datetime_local`, timezone e `strict_birth`. 【F:main.py†L271-L282】
- **`CosmicChatRequest`**: pergunta, payload astrológico, tom/idioma. 【F:main.py†L248-L252】
- **`CosmicWeatherResponse`**, **`CosmicWeatherRangeResponse`**: resposta de clima cósmico. 【F:main.py†L254-L270】
- **`SystemAlert`**, **`SystemAlertsResponse`**: alertas sistêmicos. 【F:main.py†L293-L324】
- **`NotificationsDailyResponse`**: feed diário de notificações. 【F:main.py†L326-L334】

### Enums
- **`HouseSystem`** (P, K, R) e **`ZodiacType`** (tropical, sidereal). 【F:main.py†L117-L118】

### Outros modelos
- **`UserPlan`** (dataclass) usado para controle de plano em memória. 【F:core/plans.py†L6-L18】

## Infra
### Configuração e env vars
- **`API_KEY`**: chave usada para autenticação. 【F:core/security.py†L10-L25】
- **`OPENAI_API_KEY`**, **`OPENAI_MODEL`**, **`OPENAI_MAX_TOKENS_FREE`**, **`OPENAI_MAX_TOKENS_PAID`**: controle de IA. 【F:main.py†L801-L834】
- **`LOG_LEVEL`**: nível do logger. 【F:main.py†L36-L55】
- **`ALLOWED_ORIGINS`**: CORS. 【F:main.py†L80-L90】

### Cache
- Cache em memória com TTL por endpoint:
  - `TTL_NATAL_SECONDS`: 30 dias
  - `TTL_TRANSITS_SECONDS`: 6 horas
  - `TTL_RENDER_SECONDS`: 30 dias
  - `TTL_COSMIC_WEATHER_SECONDS`: 6 horas
  【F:main.py†L483-L488】

### Rate limits
- Contagem diária por usuário/endpoint com limites por plano (free/trial/premium). 【F:core/limits.py†L1-L46】【F:core/plans.py†L6-L38】

### Dependências externas
- **OpenAI SDK** para chat. 【F:main.py†L13-L14】【F:main.py†L801-L834】
- **Swiss Ephemeris (`pyswisseph`)** para cálculos astrológicos. 【F:astro/ephemeris.py†L1-L8】
- **ZoneInfo + tzdata** para resolução de fuso horário. 【F:main.py†L10-L11】【F:requirements.txt†L1-L10】
- **FastAPI/Pydantic/uvicorn** para API e validação. 【F:requirements.txt†L1-L10】

## Observabilidade
- **Logs estruturados JSON** com request_id, path, status e latency. 【F:main.py†L24-L76】
- **Middleware** injeta `X-Request-Id` e registra métricas de request. 【F:main.py†L92-L136】
- **Handler de HTTPException** centraliza resposta com request_id. 【F:main.py†L139-L155】

## Segurança
- **Autenticação por API key** com `Authorization: Bearer <API_KEY>`. 【F:core/security.py†L10-L25】
- **Identidade do usuário** via `X-User-Id` obrigatório. 【F:core/security.py†L25-L31】
- **Rate limit** por endpoint/plano. 【F:core/security.py†L25-L32】【F:core/limits.py†L1-L46】

## Limitações / Riscos
- **Cache e planos em memória**: dados não persistem entre reinícios e não escalam horizontalmente. 【F:core/cache.py†L1-L22】【F:core/plans.py†L6-L38】
- **Rate limit em memória**: contagem é por processo e reinicia com restart. 【F:core/limits.py†L1-L46】
- **Dependência de API externa (OpenAI)**: indisponibilidade ou quota afeta `cosmic-chat`. 【F:main.py†L801-L848】
- **Timezone/DST ambíguo**: exige input explícito quando `strict_timezone/strict_birth` ativado. 【F:main.py†L432-L479】

## Diagrama textual (alto nível)
```
[Client]
  │
  ▼
[FastAPI: main.py]
  │  ├─ Auth + Rate limit (core/security.py, core/limits.py)
  │  ├─ Cache TTL (core/cache.py)
  │  ├─ Timezone resolver (ZoneInfo)
  │  ├─ Astro engine (astro/ephemeris.py + astro/aspects.py)
  │  └─ AI prompts + OpenAI (ai/prompts.py + OpenAI SDK)
  ▼
[Response]
```
