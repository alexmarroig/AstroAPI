# AstroAPI

## Instalação
Use o arquivo de dependências único do projeto para instalar as bibliotecas de runtime:

```bash
pip install -r requirements.txt
```

## Fonte de verdade das dependências
`requirements.txt` é a fonte de verdade para instalação em deploy/CI. Mantenha o `pyproject.toml` alinhado a ele, mas o pipeline deve instalar explicitamente via `requirements.txt`.
