# AstroAPI

## Instalação
Use o `requirements.txt` como fonte de verdade das dependências de runtime. Mantenha o `pyproject.toml` alinhado a ele, mas o pipeline de deploy/CI deve instalar explicitamente via:

```bash
pip install -r requirements.txt
```
## Revolução Solar

O endpoint `/v1/solar-return/calculate` calcula o instante exato da Revolução Solar e retorna o mapa completo do retorno (casas, planetas e aspectos).

### Feature flags

- `SOLAR_RETURN_ENGINE=v1|v2`  
  - `v1` (padrão): busca simples pela melhor aproximação horária.  
  - `v2`: busca robusta com bracket + bissecção para maior precisão.
- `SOLAR_RETURN_COMPARE=1`  
  Quando `SOLAR_RETURN_ENGINE=v2`, registra no log a diferença de precisão em relação ao `v1` (sem alterar a resposta).
