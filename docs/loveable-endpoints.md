# Endpoints para integração (Loveable + front-end)

## Auth

- A maioria dos endpoints usa autenticação via headers `Authorization` e `X-User-Id` (API key + id do usuário). Use como `Authorization: Bearer <API_KEY>` e `X-User-Id: <user_id>`. 
- Endpoints públicos não exigem esses headers.

## Endpoints públicos (sem auth)

- `GET /` — status básico do serviço.
- `GET /health` — health check simples.
- `GET /v1/system/roadmap` — roadmap do produto.
- `GET /v1/system/endpoints` — lista de endpoints (disponível apenas quando `ENABLE_ENDPOINTS_LIST=1`).
- `POST /v1/time/resolve-tz` — resolve offset de timezone.
- `POST /v1/time/validate-local-datetime` — valida data/hora local e resolve UTC.
- `GET /v1/alerts/retrogrades` — alertas de retrogradação.

## Endpoints com auth (Authorization + X-User-Id)

### Conta & plano
- `GET /v1/account/status` — status da conta e do plano.
- `GET /v1/account/plan` — detalhes do plano/trial.
- `POST /v1/account/plan-status` — status do plano para tela de assinatura.

### Sinastria
- `POST /v1/synastry/compare` — comparação de sinastria.

### Diagnósticos/tempo
- `POST /v1/diagnostics/ephemeris-check` — diagnóstico do Swiss Ephemeris.

### Insights
- `POST /v1/insights/mercury-retrograde`
- `POST /v1/insights/dominant-theme`
- `POST /v1/insights/areas-activated`
- `POST /v1/insights/care-suggestion`
- `POST /v1/insights/life-cycles`
- `POST /v1/insights/solar-return`

### Mapas e trânsitos
- `POST /v1/chart/natal`
- `POST /v1/chart/distributions`
- `POST /v1/chart/transits`
- `POST /v1/transits/live`
- `POST /v1/transits/events`
- `POST /v1/interpretation/natal`

### Resumos, timelines e clima cósmico
- `GET /v1/daily/summary`
- `GET /v1/cosmic-timeline/next-7-days`
- `GET /v1/transits/next-days`
- `GET /v1/transits/personal-today`
- `GET /v1/revolution-solar/current-year`
- `GET /v1/moon/timeline`
- `GET /v1/cosmic-weather`
- `GET /v1/cosmic-weather/range`

### Render e IA
- `POST /v1/chart/render-data` — dados simplificados para renderização.
- `POST /v1/ai/cosmic-chat` — chat interpretativo com IA.

### Revolução solar
- `POST /v1/solar-return/calculate`
- `POST /v1/solar-return/overlay`
- `POST /v1/solar-return/timeline`

### Alertas/Notificações
- `GET /v1/alerts/system`
- `GET /v1/notifications/daily`

### Serviços isolados (routers)
- `POST /v1/lunations/calculate`
- `POST /v1/progressions/secondary/calculate`

## Comandos usados para levantar os endpoints

- `ls`
- `find .. -name AGENTS.md -print`
- `ls routes`
- `sed -n '1,200p' routes/__init__.py`
- `sed -n '1,200p' routes/lunations.py`
- `sed -n '1,200p' routes/progressions.py`
- `sed -n '1,200p' routes/time.py`
- `sed -n '1,200p' main.py`
- `rg "@app" -n main.py`
- `sed -n '2100,2525p' main.py`
- `sed -n '2480,2760p' main.py`
- `sed -n '2760,3400p' main.py`
- `sed -n '3400,3805p' main.py`
