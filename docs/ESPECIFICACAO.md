# Especificação original

> Transcrição fiel do documento de especificação original.
> Mantida aqui para ficar versionada em Git — o `.docx` não é diffável.
> Divergências e lacunas encontradas estão em [AVALIACAO.md](AVALIACAO.md), não neste arquivo.

## 1. Arquitetura de Infraestrutura (Docker)

Manter a aplicação conteinerizada desde o dia zero é a melhor escolha para a migração planejada.

- **Contêiner 1 (Database):** PostgreSQL.
- **Contêiner 2 (Backend):** Uma API REST (sugestão: Python com FastAPI ou Node.js com Express/NestJS, pois lidam muito bem com manipulação de Excel e bancos relacionais).
- **Contêiner 3 (Frontend):** Onde ficará a interface de layout claro (React, Vue ou Svelte).

## 2. Estrutura do Banco de Dados (PostgreSQL)

Estrutura relacional aberta, que permita que uma Plataforma tenha múltiplas Campanhas, que por sua vez têm Grupos de Anúncios, etc.

| Tabela | Campos Principais | Relacionamento |
| --- | --- | --- |
| Plataformas | `id`, `nome` (ex: Meta, Google, TikTok), `sigla` (ex: FB, GO, TT), `limite_caracteres` | — |
| Campanhas | `id`, `nome_interno`, `id_banco_match`, `sigla_objetivo`, `plataforma_id` | Pertence a Plataforma |
| Grupos_Anuncio | `id`, `nome_interno`, `id_banco_match`, `sigla_publico`, `campanha_id` | Pertence a Campanha |
| Anuncios | `id`, `nome_interno`, `id_banco_match`, `sigla_formato`, `grupo_anuncio_id` | Pertence a Grupo_Anuncio |
| Taxonomias_Geradas | `id`, `nomenclatura_final`, `data_criacao`, `usuario_id` | Histórico de extrações |

## 3. Regras de Negócio e o Motor de Taxonomia

Para garantir que o **o nome de trabalho anterior** gere nomes perfeitos, o backend precisará implementar as seguintes regras:

- **Uso de Abreviações:** o sistema deve ter um dicionário/tabela de "De → Para".
  - Exemplo: Objetivo "Conversão" → `CV`; Formato "Stories" → `ST`; Público "Remarketing" → `RMKT`.
- **IDs de Match:** cada nível (Campanha, Grupo, Anúncio) deve receber um ID único gerado pelo banco (ex: um UUID ou um sequencial curto como `C123`, `G456`) que será concatenado na nomenclatura para cruzar com o banco de dados e as planilhas de performance de mídia posteriormente.
- **Limitador de Caracteres Restritos:**
  - Criar uma validação (RegEx) que bloqueie espaços em branco, acentos e caracteres especiais (como `!@#$%^&*()`).
  - O sistema deve forçar o uso de um separador padrão (geralmente underline `_` ou hífen `-`).
  - Exemplo de RegEx aceita: `^[a-zA-Z0-9_-]+$`
- **Análise de Campos por Plataforma:**
  - Meta Ads: pode exigir campos para Posicionamento.
  - Google Ads (Search): pode exigir campos para Tipo de Correspondência.
  - A modelagem de dados deve permitir "Campos Dinâmicos" (usando uma coluna JSONB no Postgres) atrelados a cada plataforma.

## 4. Extração e Interface

- **Exportação em Excel:** o backend deve pegar a lista de taxonomias geradas na sessão e compilar em um arquivo `.xlsx`. Em Python, `pandas` ou `openpyxl`; em Node, `exceljs`. O arquivo deve ter as colunas separadas para facilitar o "copiar e colar" do analista de mídia na plataforma.
- **UI (Layout em Cores Claras):** o frontend deve adotar um tema Light voltado para produtividade.
  - Cores recomendadas: fundo `#F8F9FA` (cinza muito claro), cards em `#FFFFFF` (branco), botões de ação na cor da marca (ex: azul ou verde suave).
  - Uso de formulários em "Cascata": o usuário seleciona a Plataforma → os campos da Campanha se abrem → os campos do Grupo se abrem.
