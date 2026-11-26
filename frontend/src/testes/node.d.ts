/**
 * Declaração mínima de `node:fs` só para os testes.
 *
 * O projeto não tem `@types/node` e não vai passar a ter por causa de uma
 * asserção: o `tsc -b` do build cobre `src/`, então sem isto o build quebra.
 * O único teste que lê disco é o que prova que `[hidden]` continua com
 * `!important` na folha base — regra que nenhum teste de DOM consegue provar,
 * porque o jsdom não aplica as folhas do app.
 */
declare module 'node:fs' {
  export function readFileSync(caminho: string, codificacao: 'utf8'): string
}
