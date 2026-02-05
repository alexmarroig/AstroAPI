# QA Checklist — Backend Astrológico Premium

| Domínio | Endpoint | Método | Auth | Cenário mínimo de teste | Resultado esperado |
|---|---|---|---|---|---|
| Billing | `/v1/billing/status` | GET | Sim | user `free@local` | `ok=true`, `role=free` |
| Billing | `/v1/billing/entitlements` | GET | Sim | user `premium@local` | entitlements premium habilitados |
| Astro Pro | `/v1/astro/chart` | POST | Sim | payload natal completo | `chart` + `planets[*].glyph_id` |
| Astro Pro | `/v1/astro/chart/render-spec` | POST | Sim | mesmo payload do chart | `layers` + `points` para render profissional |
| Astro Pro | `/v1/astro/transits` | POST | Sim | `date=YYYY-MM-DD` | trânsitos do dia |
| Astro Pro | `/v1/astro/solar-return` | POST | Sim | natal + `target_year` | retorno solar estruturado |
| Astro Pro | `/v1/astro/progressions` | POST | Sim | natal + `target_date` | progressões secundárias |
| Astro Pro | `/v1/astro/synastry` | POST | Sim | `inner` + `outer` charts | `biwheel=true` |
| Astro Pro | `/v1/astro/composite` | POST | Sim | `inner` + `outer` charts | composto midpoint |
| Astro Pro | `/v1/astro/lunar-phases` | POST | Sim | `date`, `timezone` | 30 itens de lunação (cacheável) |
| Oracle | `/v1/oracle/chat` | POST | Sim | mensagem + idempotency_key | resposta com fallback determinístico |
| Telemetria | `/v1/telemetry/event` | POST | Sim | `event_name=oracle_send` | evento aceito |
| Bugs | `/v1/bugs/report` | POST | Sim | bug report mínimo | bug criado com status `open` |
| Admin | `/v1/admin/dashboard` | GET | Sim | user `admin@local` | métricas agregadas + bugs |
| Dev-only | `/v1/dev/login-as` | POST | Não | `email=admin@local` em dev | role resolvida para QA |

## Perfis seed (dev/staging)

- `free@local`
- `premium@local`
- `admin@local`

> Observação: em produção, endpoints dev-only devem permanecer bloqueados.
