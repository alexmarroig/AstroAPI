from __future__ import annotations
from typing import Optional

"""
Este módulo centraliza a lógica de internacionalização (i18n).

O que é i18n?
'i18n' é uma abreviação para 'Internationalization' (o número 18 representa as 18 letras entre o 'i' e o 'n').
É a prática de projetar o software para que ele possa ser adaptado a diferentes idiomas e regiões
sem alterações estruturais no código.

Nesta API, focamos principalmente em fornecer suporte robusto para Português do Brasil (pt-BR).
"""

def is_pt_br(lang: Optional[str]) -> bool:
    """Verifica se o idioma solicitado é Português do Brasil."""
    if not lang:
        return False
    return lang.lower().replace("_", "-") == "pt-br"

def get_translation_source_metadata() -> dict:
    """Retorna metadados padrão sobre a fonte de tradução."""
    return {
        "idioma": "pt-BR",
        "fonte_traducao": "backend",
    }
