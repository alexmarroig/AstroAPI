# Quality Gates de Carga, Segurança e UX/UI

Este documento descreve a suíte adicionada para validar qualidade contínua da API.

## Estrutura

- `tests/load/`: cenários de carga com Locust e gate automatizado de baseline.
- `tests/security/`: testes de segurança de API (headers, autenticação e fuzz básico) + artefatos de scan de dependências.
- `tests/e2e_ui/`: smoke tests cross-browser/device (Playwright) para `/docs`.

## Carga (endpoints críticos)

Cenários cobrem:
- `POST /v1/chart/natal`
- `POST /v1/chart/transits`
- `POST /v1/chart/render-data`
- `POST /v1/ai/cosmic-chat`

Thresholds e baseline:
- `tests/load/thresholds.json`
- `tests/load/baseline.json`

Gate:
- `python tests/load/evaluate_load.py`

Critérios de falha:
1. p95 acima do threshold definido.
2. taxa de erro acima do threshold definido.
3. regressão contra baseline (p95/erro pior que referência).

## Segurança

- `pytest tests/security` valida:
  - Security headers obrigatórios.
  - Enforcements de autenticação em endpoints críticos.
  - Fuzz básico de input inválido com resposta controlada.
- CI executa também:
  - `pip-audit -r requirements.txt`
  - `safety check -r requirements.txt`

## UX/UI (cross-browser/device)

- `pytest tests/e2e_ui`
- Executa em `chromium`, `firefox` e `webkit`, viewport mobile.
- Smoke de carregamento do Swagger (`/docs`).

## CI e artefatos

Workflow: `.github/workflows/quality-gates.yml`

- Executa em `push`, `pull_request` e semanalmente (`cron` segunda 08:00 UTC).
- Publica artefatos (`tests/load/artifacts` e scans de segurança JSON).
- O build falha automaticamente quando qualquer gate estoura.
