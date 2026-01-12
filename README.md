# AstroAPI

## Dependências

A fonte de verdade das dependências de runtime é o `pyproject.toml`. Para manter o pipeline de deploy/CI com uma única fonte, instale via:

```bash
pip install .
```

O `requirements.txt` existe apenas para compatibilidade com ferramentas legadas e deve espelhar o conteúdo do `pyproject.toml`.
## Revolução Solar

O endpoint `/v1/solar-return/calculate` calcula o instante exato da Revolução Solar e retorna o mapa completo do retorno (casas, planetas e aspectos).

### Feature flags

- `SOLAR_RETURN_ENGINE=v1|v2`  
  - `v1` (padrão): busca simples pela melhor aproximação horária.  
  - `v2`: busca robusta com bracket + bissecção para maior precisão.
- `SOLAR_RETURN_COMPARE=1`  
  Quando `SOLAR_RETURN_ENGINE=v2`, registra no log a diferença de precisão em relação ao `v1` (sem alterar a resposta).
