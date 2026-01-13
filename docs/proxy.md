# Proxy Supabase (AstroAPI)

## Normalização de payload
### PASS-THROUGH (não normalizar year/natal_year)
- `/v1/solar-return/calculate`
- `/v1/chart/natal`
- `/v1/chart/transits`
- `/v1/chart/render-data`
- `/v1/chart/distributions`
- `/v1/interpretation/natal`

Esses endpoints devem receber e encaminhar o payload exatamente conforme o schema
definido, preservando os nomes originais dos campos e evitando conversões implícitas
entre `year/month/day/...` e `natal_year/natal_month/...`.

### Regras explícitas por endpoint
- `/v1/chart/render-data` espera `year/month/day/hour` (sem `natal_*`).
- `/v1/chart/natal` e `/v1/chart/transits` esperam `natal_*`.
- `/v1/solar-return/calculate` deve ser PASS-THROUGH (sem normalização).
- `/v1/chart/distributions` e `/v1/interpretation/natal` seguem `NatalChartRequest` (use `natal_*`).

### Pode normalizar (resolve-tz)
- `/v1/time/resolve-tz`

Observação: só normalize payloads quando o endpoint seguir o mesmo schema do
`/v1/chart/natal`. Caso contrário, mantenha pass-through.
