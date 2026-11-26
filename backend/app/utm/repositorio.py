"""Monta o `ContextoUtm` a partir do banco.

Espelho do `app/taxonomia/repositorio.py`: é aqui que mora o SQLAlchemy,
para que `validador.py` continue puro.

Duas cautelas atravessam o módulo:

1. **A entidade pode não existir mais.** O histórico sobrevive à campanha
   apagada de propósito (D-004/D-009), então tudo é resolvido de forma
   tolerante: o que não der para carregar vira `None`, e o validador pula a
   regra correspondente em vez de reprovar a URL por buraco nosso.
2. **Os ids denormalizados são o caminho curto.** `plataforma_id` e
   `campanha_id` já estão na linha de `taxonomias_geradas` (D-009), então
   plataforma e campanha são alcançáveis sem subir a hierarquia — o que é
   justamente o que continua funcionando depois da exclusão.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Anuncio,
    Campanha,
    DicionarioAbreviacao,
    GrupoAnuncio,
    Nivel,
    Plataforma,
    TaxonomiaGerada,
)
from app.utm.tipos import ContextoUtm

CATEGORIA_SOURCE = "utm_source"
CATEGORIA_MEDIUM = "utm_medium"


def _nomenclatura_mais_recente(
    session: Session, nivel: Nivel, entidade_id: uuid.UUID
) -> str | None:
    """Último nome gerado para a entidade. Nulo é resposta legítima: a
    entidade pode existir sem nunca ter tido nome gerado."""
    return session.scalar(
        select(TaxonomiaGerada.nomenclatura_final)
        .where(TaxonomiaGerada.nivel == nivel, TaxonomiaGerada.entidade_id == entidade_id)
        .order_by(TaxonomiaGerada.criado_em.desc())
        .limit(1)
    )


def _vocabulario(session: Session, plataforma_id: uuid.UUID | None, categoria: str) -> tuple[str, ...]:
    """Valores aceitos numa categoria de UTM, global mais os da plataforma.

    Aceita tanto o termo quanto a abreviação: quem cadastra 'Facebook →
    facebook' espera que as duas formas sejam reconhecidas na URL. O que é
    devolvido — e listado no erro — é a abreviação, porque é ela que se
    escreve na URL.
    """
    consulta = select(DicionarioAbreviacao).where(DicionarioAbreviacao.categoria == categoria)
    if plataforma_id is not None:
        consulta = consulta.where(
            or_(
                DicionarioAbreviacao.plataforma_id.is_(None),
                DicionarioAbreviacao.plataforma_id == plataforma_id,
            )
        )
    else:
        consulta = consulta.where(DicionarioAbreviacao.plataforma_id.is_(None))

    valores: list[str] = []
    for registro in session.scalars(consulta):
        for candidato in (registro.abreviacao, registro.termo):
            if candidato and candidato not in valores:
                valores.append(candidato)
    return tuple(valores)


def carregar_contexto(session: Session, taxonomia_id: uuid.UUID) -> ContextoUtm | None:
    """Contexto da taxonomia pedida, ou `None` se ela não existe."""
    taxonomia = session.get(TaxonomiaGerada, taxonomia_id)
    if taxonomia is None:
        return None

    plataforma = (
        session.get(Plataforma, taxonomia.plataforma_id)
        if taxonomia.plataforma_id is not None
        else None
    )
    campanha = (
        session.get(Campanha, taxonomia.campanha_id)
        if taxonomia.campanha_id is not None
        else None
    )

    grupo: GrupoAnuncio | None = None
    anuncio: Anuncio | None = None
    if taxonomia.nivel is Nivel.GRUPO:
        grupo = session.get(GrupoAnuncio, taxonomia.entidade_id)
    elif taxonomia.nivel is Nivel.ANUNCIO:
        anuncio = session.get(Anuncio, taxonomia.entidade_id)
        if anuncio is not None:
            grupo = session.get(GrupoAnuncio, anuncio.grupo_anuncio_id)

    # A nomenclatura do nível pedido vem da própria linha; as dos outros
    # níveis, da mais recente de cada entidade.
    nomes = {
        Nivel.CAMPANHA: None,
        Nivel.GRUPO: None,
        Nivel.ANUNCIO: None,
    }
    nomes[taxonomia.nivel] = taxonomia.nomenclatura_final
    if nomes[Nivel.CAMPANHA] is None and campanha is not None:
        nomes[Nivel.CAMPANHA] = _nomenclatura_mais_recente(session, Nivel.CAMPANHA, campanha.id)
    if nomes[Nivel.GRUPO] is None and grupo is not None:
        nomes[Nivel.GRUPO] = _nomenclatura_mais_recente(session, Nivel.GRUPO, grupo.id)

    campos_campanha = campanha.campos if campanha is not None else {}
    campos_anuncio = anuncio.campos if anuncio is not None else {}
    # `tipo_compra` é campo do anúncio (CPC/CPM) e é o que o utm_medium
    # deveria espelhar; sem anúncio no contexto, a regra é pulada.
    tipo_compra = campos_anuncio.get("tipo_compra")

    return ContextoUtm(
        nivel=taxonomia.nivel.value,
        sigla_plataforma=plataforma.sigla if plataforma else None,
        nome_plataforma=plataforma.nome if plataforma else None,
        match_id_campanha=campanha.match_id if campanha else None,
        match_id_grupo=grupo.match_id if grupo else None,
        match_id_anuncio=anuncio.match_id if anuncio else None,
        nomenclatura_campanha=nomes[Nivel.CAMPANHA],
        nomenclatura_grupo=nomes[Nivel.GRUPO],
        nomenclatura_anuncio=nomes[Nivel.ANUNCIO],
        tipo_compra=tipo_compra,
        canal=campos_campanha.get("canal"),
        vocabulario_source=_vocabulario(session, taxonomia.plataforma_id, CATEGORIA_SOURCE),
        vocabulario_medium=_vocabulario(session, taxonomia.plataforma_id, CATEGORIA_MEDIUM),
    )
