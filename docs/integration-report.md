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

## Resultado esperado
- Nenhum endpoint crítico retorna `422` por divergência `camelCase` vs `snake_case`.
- Contratos de auth e shape JSON mantidos estáveis para front/proxy.
