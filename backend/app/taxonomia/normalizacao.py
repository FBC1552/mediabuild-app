"""Normalização de texto.

Regra central (lacuna 4 de AVALIACAO.md): acento é **transliterado**, não
rejeitado. Devolver erro para quem digitou 'Conversão' corretamente em
português seria hostil. A RegEx de validação é rede de segurança, não
porta de entrada.
"""

import re
import unicodedata

# Aplicado ao nome final, depois de tudo montado.
PADRAO_VALIDO = re.compile(r"^[A-Z0-9_-]+$")

_ESPACOS = re.compile(r"\s+")


def remover_acentos(texto: str) -> str:
    """'Conversão' -> 'Conversao'. Decompõe em NFD e descarta os diacríticos."""
    decomposto = unicodedata.normalize("NFD", texto)
    sem_marcas = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", sem_marcas)


def normalizar(texto: str, separador: str) -> str:
    """Prepara um pedaço do nome: sem acento, maiúsculo, sem espaços.

    Não remove caracteres inválidos silenciosamente — quem reclama deles é
    `validar()`, com mensagem explícita. Sumir com um '&' sem avisar
    produziria um nome que o analista não reconhece.
    """
    texto = remover_acentos(texto.strip())
    texto = _ESPACOS.sub(separador, texto)
    return texto.upper()


def chave_de_busca(termo: str) -> str:
    """Forma canônica usada para indexar o dicionário de abreviações."""
    return _ESPACOS.sub(" ", remover_acentos(termo).strip()).lower()


def caracteres_invalidos(nome: str) -> list[str]:
    """Caracteres que impedem o nome de passar na validação, sem repetir."""
    vistos: list[str] = []
    for c in nome:
        if not re.match(r"[A-Z0-9_-]", c) and c not in vistos:
            vistos.append(c)
    return vistos
