"""Erros do motor de taxonomia.

Cada erro carrega os dados que a UI precisa para orientar o analista —
não só uma mensagem. O texto é em português porque chega ao usuário final.
"""


class ErroTaxonomia(Exception):
    """Base de todos os erros de geração de nomenclatura."""


class TemplateInvalido(ErroTaxonomia):
    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__(f"Template inválido: {motivo}")


class CampoAusente(ErroTaxonomia):
    def __init__(self, chave: str) -> None:
        self.chave = chave
        super().__init__(f"O campo '{chave}' é exigido pelo template e não foi preenchido.")


class TermoDesconhecido(ErroTaxonomia):
    """D-005: termo sem abreviação cadastrada é erro, não passa normalizado.

    Lista as opções existentes para que o analista possa escolher uma
    delas em vez de precisar cadastrar.
    """

    def __init__(
        self, categoria: str, termo: str, opcoes: list[str], chave: str | None = None
    ) -> None:
        self.categoria = categoria
        self.termo = termo
        self.opcoes = opcoes
        # A chave é a posição no formulário ('interesse_2'); a categoria é o
        # vocabulário consultado ('interesse'). A UI destaca a chave.
        self.chave = chave or categoria

        if opcoes:
            disponiveis = ", ".join(opcoes)
            saida = (
                f"Adicione '{termo}' ao dicionário de '{categoria}' "
                f"ou escolha uma das opções existentes: {disponiveis}."
            )
        else:
            saida = f"Não há nenhum termo cadastrado em '{categoria}'. Adicione '{termo}' ao dicionário."

        super().__init__(f"O termo '{termo}' não está no dicionário de '{categoria}'. {saida}")


class AbreviacaoReservada(ErroTaxonomia):
    """D-011: nenhuma abreviação pode **ser** o marcador de ausência.

    O marcador ocupa a posição de um campo opcional deixado em branco. Se
    um termo real abreviasse para o mesmo texto, o nome ficaria ambíguo —
    quem lê a planilha não teria como distinguir 'não preenchido' de um
    valor de verdade. E o caso não é hipotético: 'Nacional' em 'regiao'
    abrevia para 'NA' na primeira tentativa de qualquer analista.

    Igualdade exata, nunca 'contém': `NOR`, `NOV` e qualquer `NATAL` futuro
    continuam válidos.
    """

    def __init__(self, abreviacao: str, marcadores: list[str]) -> None:
        self.abreviacao = abreviacao
        self.marcadores = marcadores
        # A UI destaca o campo do formulário, não a categoria.
        self.chave = "abreviacao"

        em_uso = ", ".join(f"'{m}'" for m in marcadores)
        super().__init__(
            f"A abreviação '{abreviacao}' é reservada: ela é o marcador que ocupa o lugar "
            f"de um campo opcional deixado em branco ({em_uso} em uso nos templates). "
            "Usá-la aqui tornaria impossível distinguir, no nome gerado, um valor real de "
            "um campo não preenchido. Escolha outra abreviação — 'NOR' e 'NAC' são livres, "
            "porque a reserva vale só para o texto idêntico."
        )


class CampoLongoDemais(ErroTaxonomia):
    """Campo livre que estourou o próprio limite.

    Diferente de `LimiteExcedido`, que fala do nome inteiro: aqui o problema
    é um campo específico, então a UI consegue apontar para ele.
    """

    def __init__(self, chave: str, valor: str, maximo: int) -> None:
        self.chave = chave
        self.valor = valor
        self.tamanho = len(valor)
        self.maximo = maximo
        super().__init__(
            f"O campo '{chave}' aceita no máximo {maximo} caracteres e recebeu "
            f"{len(valor)} ('{valor}'). Encurte o valor."
        )


class NomeInvalido(ErroTaxonomia):
    def __init__(self, nome: str, invalidos: list[str]) -> None:
        self.nome = nome
        self.invalidos = invalidos
        encontrados = " ".join(f"'{c}'" for c in invalidos)
        super().__init__(
            f"O nome gerado '{nome}' contém caracteres não permitidos: {encontrados}. "
            "Só são aceitos letras sem acento, números, '_' e '-'."
        )


class LimiteExcedido(ErroTaxonomia):
    def __init__(self, nome: str, limite: int) -> None:
        self.nome = nome
        self.tamanho = len(nome)
        self.limite = limite
        super().__init__(
            f"O nome gerado tem {len(nome)} caracteres e o limite da plataforma "
            f"para este nível é {limite}. Encurte algum campo ou abreviação."
        )
