"""Erros de domínio do plano de mídia.

Mesmo padrão de `app/taxonomia/erros.py`: cada erro carrega o que a UI
precisa para apontar o campo certo, e o texto é em português porque chega
ao analista. Registrados em `app/erros_http.py`, nunca vira 500.
"""


class ErroPlano(Exception):
    """Base dos erros de domínio do plano de mídia."""


class MetricaDesconhecida(ErroPlano):
    """A meta digitada referencia um código de métrica sem cadastro ativo.

    Mesmo espírito do D-005 do motor de taxonomia (termo fora do
    dicionário é erro, não passa em silêncio): uma meta presa a um código
    que ninguém reconhece não aparece em nenhum relatório, e o analista
    nem percebe. A lista de opções aceitas vem junto, para que a saída seja
    imediata — cadastrar a métrica nova ou corrigir o código digitado.
    """

    def __init__(self, codigo: str, opcoes: list[str]) -> None:
        self.chave = "metas"
        self.codigo = codigo
        self.opcoes = opcoes
        disponiveis = ", ".join(opcoes) if opcoes else "nenhuma cadastrada ainda"
        super().__init__(
            f"A métrica '{codigo}' não está cadastrada (ou está inativa). "
            f"Cadastre-a em POST /metricas ou use uma das opções ativas: {disponiveis}."
        )


class KpiPrimarioInvalido(ErroPlano):
    """O `kpi_primario_id` informado não corresponde a uma métrica
    cadastrada e ativa no catálogo.

    Mesmo espírito de `MetricaDesconhecida`, mas para o KPI primário da
    campanha em vez de uma chave de `metas`: o KPI é sempre uma referência
    ao catálogo (`Metrica`), nunca texto livre, para não deixar o analista
    escrever "Cliques" numa campanha e "clicks" na próxima. Erro só na
    *escrita* — depois de escolhido, o KPI pode ser desativado ou apagado
    do catálogo sem quebrar o plano (ver `PlanoMidiaCampanha.kpi_primario_id`);
    a leitura sinaliza isso separadamente, não rejeita.
    """

    def __init__(self, kpi_primario_id: str, opcoes: list[str]) -> None:
        self.chave = "kpi_primario_id"
        self.opcoes = opcoes
        disponiveis = ", ".join(opcoes) if opcoes else "nenhuma cadastrada ainda"
        super().__init__(
            f"'{kpi_primario_id}' não corresponde a uma métrica cadastrada e ativa. "
            f"Escolha uma das opções ativas em GET /metricas: {disponiveis}."
        )


class EntidadeForaDaHierarquia(ErroPlano):
    """A entidade escolhida para a linha não é filha da linha pai do plano.

    Por exemplo: um grupo de anúncio que pertence a outra campanha sendo
    adicionado sob a linha de campanha errada. Isso corromperia a leitura
    do plano em cascata — o rateio de verba de um grupo apareceria sob uma
    campanha que não é a dele.
    """

    def __init__(self, nivel: str, motivo: str) -> None:
        self.chave = nivel
        self.motivo = motivo
        super().__init__(motivo)
