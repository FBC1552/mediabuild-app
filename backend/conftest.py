"""Configuração que precisa valer **antes** de qualquer import de `app`.

O pytest carrega o conftest da raiz antes do de `tests/`, e o de `tests/`
importa `app.db`, que instancia `Settings` no import. Então é aqui, e só
aqui, que dá para preparar o ambiente.

Rodar a suíte é desenvolvimento por definição: sem isto, `pytest` num
clone sem `.env` bateria na proteção do `config.py` contra subir em
produção com dado de exemplo (`DEBUG` tem default `false` de propósito).

`setdefault` e não atribuição: quem quiser rodar a suíte contra uma
configuração real só precisa exportar as variáveis antes.
"""

import os

os.environ.setdefault("DEBUG", "true")
