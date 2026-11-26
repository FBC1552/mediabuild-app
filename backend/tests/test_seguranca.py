import io

from openpyxl import Workbook, load_workbook

from app.exportacao import neutralizar_formulas
from app.logs import _ID_VALIDO


def test_texto_iniciado_por_igual_nao_vira_formula():
    wb = Workbook()
    wb.active.append(['=HYPERLINK("http://exemplo.com","clique")', "normal", 10])
    neutralizar_formulas(wb.active)
    buffer = io.BytesIO()
    wb.save(buffer)

    celulas = load_workbook(io.BytesIO(buffer.getvalue())).active[1]

    assert [c.data_type for c in celulas] == ["s", "s", "n"]
    assert celulas[0].value.startswith("=HYPERLINK")


def test_request_id_so_no_formato_esperado():
    assert _ID_VALIDO.fullmatch("abc-123")
    assert not _ID_VALIDO.fullmatch("x" * 65)
    assert not _ID_VALIDO.fullmatch("com espaco")
