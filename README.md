# AstroAPI

## Dependências

A fonte de verdade das dependências de runtime é o `pyproject.toml`. Para manter o pipeline de deploy/CI com uma única fonte, instale via:

```bash
pip install .
```

O `requirements.txt` existe apenas para compatibilidade com ferramentas legadas e deve espelhar o conteúdo do `pyproject.toml`.
