"""Conferência de UTM (D-012).

Uma rota só, e sem escrita: conferir URL não gera taxonomia nem altera a
existente (D-004). A resposta é **sempre 200** quando a taxonomia existe —
o laudo de uma URL cheia de erros é uma resposta bem-sucedida, não uma
requisição malformada. 422 fica para corpo inválido, que é assunto do
Pydantic; 404, para taxonomia inexistente.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import UtmResposta, UtmValidarPedido
from app.utm.repositorio import carregar_contexto
from app.utm.validador import validar_utm

router = APIRouter(prefix="/utm", tags=["utm"])

logger = logging.getLogger("mediabuild.utm")


@router.post("/validar", response_model=UtmResposta)
def validar(dados: UtmValidarPedido, session: Session = Depends(get_session)) -> dict:
    contexto = carregar_contexto(session, dados.taxonomia_id)
    if contexto is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Taxonomia não encontrada. Gere a nomenclatura antes de conferir a URL.",
        )

    resultado = validar_utm(dados.url, contexto)

    # A frequência por código diz quais armadilhas aparecem de verdade —
    # é o que orienta o que vale automatizar depois. O conteúdo da URL não
    # vai para o log: pode conter parâmetro de terceiro.
    logger.info(
        "url conferida",
        extra={
            "valido": resultado.valido,
            "erros": [a.codigo for a in resultado.erros],
            "avisos": [a.codigo for a in resultado.avisos],
        },
    )
    return resultado.para_json()
