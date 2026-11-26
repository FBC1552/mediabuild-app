"""Estruturas do validador de UTM (D-012).

Deliberadamente sem SQLAlchemy — a mesma disciplina do motor de taxonomia.
O contexto é um pacote de dados simples montado por `repositorio.py`; o
validador só o consome. É o que permite testar as 31 regras de forma
exaustiva sem banco, e o que permitirá reaproveitar o laudo num conferidor
em lote depois.

`nivel` viaja como **string** ('CAMPANHA' | 'GRUPO' | 'ANUNCIO') e não como
o enum `Nivel`: o enum mora em `app/models`, que importa SQLAlchemy, e
importá-lo aqui quebraria a pureza que é o motivo deste módulo existir.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextoUtm:
    """O que se sabe da taxonomia contra a qual a URL está sendo conferida.

    Todo campo é opcional de propósito: o histórico sobrevive à entidade
    (D-004/D-009), então grupo e anúncio podem ter sido apagados, e uma
    taxonomia de campanha simplesmente não tem os níveis abaixo. **Regra
    que depende de um nível ausente é pulada, nunca reprovada** — reprovar
    por falta de dado nosso seria culpar o analista pelo nosso buraco.

    `vocabulario_source` / `vocabulario_medium` vêm das categorias
    homônimas do `dicionario_abreviacoes`. Vazias, a divergência é só
    aviso: não dá para tratar como autoridade um vocabulário que ninguém
    cadastrou.
    """

    nivel: str = "CAMPANHA"

    sigla_plataforma: str | None = None
    nome_plataforma: str | None = None

    match_id_campanha: str | None = None
    match_id_grupo: str | None = None
    match_id_anuncio: str | None = None

    nomenclatura_campanha: str | None = None
    nomenclatura_grupo: str | None = None
    nomenclatura_anuncio: str | None = None

    tipo_compra: str | None = None
    canal: str | None = None

    vocabulario_source: tuple[str, ...] = ()
    vocabulario_medium: tuple[str, ...] = ()


@dataclass(frozen=True)
class Achado:
    """Um item do laudo, erro ou aviso.

    `codigo` é estável e é por ele que o cliente decide o que destacar —
    mesmo contrato dos códigos de `erros_http.py`. A mensagem é texto
    pronto para o analista ler, nunca a única informação disponível.
    """

    codigo: str
    parametro: str | None
    mensagem: str
    encontrado: str | None = None
    esperado: str | None = None

    def para_json(self) -> dict:
        return {
            "codigo": self.codigo,
            "parametro": self.parametro,
            "mensagem": self.mensagem,
            "encontrado": self.encontrado,
            "esperado": self.esperado,
        }


@dataclass(frozen=True)
class ResultadoUtm:
    """O laudo. `valido` é derivado: é `erros == []`, nada além disso."""

    erros: list[Achado] = field(default_factory=list)
    avisos: list[Achado] = field(default_factory=list)
    parametros: dict[str, str] = field(default_factory=dict)
    sugestao: dict[str, str] = field(default_factory=dict)
    url_sugerida: str = ""

    @property
    def valido(self) -> bool:
        return not self.erros

    def para_json(self) -> dict:
        return {
            "valido": self.valido,
            "erros": [a.para_json() for a in self.erros],
            "avisos": [a.para_json() for a in self.avisos],
            "parametros": self.parametros,
            "sugestao": self.sugestao,
            "url_sugerida": self.url_sugerida,
        }
