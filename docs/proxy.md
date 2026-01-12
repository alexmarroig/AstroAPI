# Proxy Supabase (AstroAPI)

## Normalização de payload
O proxy não deve aplicar normalização automática de campos `natal_*` no endpoint
`/v1/solar-return/calculate`. Esse endpoint deve receber e encaminhar o payload
exatamente conforme o schema definido, preservando os nomes originais dos campos
e evitando conversões implícitas entre `year/month/day/...` e `natal_year/natal_month/...`.
