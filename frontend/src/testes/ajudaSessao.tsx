/**
 * Sessão falsa para os testes.
 *
 * Todo componente que lê papel — a barra de topo, as abas da taxonomia, o
 * Dicionário — exige `<ProvedorSessao>` acima. Em vez de repetir o provedor
 * em cada arquivo, os testes rendem por aqui e dizem QUEM está logado, que é
 * a variável que de fato importa para o comportamento.
 *
 * `sessaoInicial` faz o provedor nascer resolvido, sem chamar `GET /auth/eu`:
 * os testes que não são sobre login não precisam encenar o boot.
 */
import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'

import { ProvedorSessao } from '../sessao'
import type { Usuario } from '../tipos'

export const USUARIO_PLENO: Usuario = {
  id: 'u-pleno',
  nome: 'Marina Alves',
  login: 'marina.alves',
  papel: 'pleno',
  ativo: true,
  criado_em: '2026-01-10T09:00:00Z',
  ultimo_acesso_em: '2026-08-06T18:40:00Z',
}

export const USUARIO_BASICO: Usuario = {
  ...USUARIO_PLENO,
  id: 'u-basico',
  nome: 'João Pedro',
  login: 'joao.pedro',
  papel: 'basico',
}

export const USUARIO_ADMIN: Usuario = {
  ...USUARIO_PLENO,
  id: 'u-admin',
  nome: 'Ana Souza',
  login: 'ana.souza',
  papel: 'admin',
}

export function ComSessao({
  children,
  usuario = USUARIO_PLENO,
}: {
  children: ReactNode
  usuario?: Usuario | null
}) {
  return <ProvedorSessao sessaoInicial={usuario}>{children}</ProvedorSessao>
}

export function renderComSessao(
  ui: ReactElement,
  usuario: Usuario | null = USUARIO_PLENO,
  opcoes?: RenderOptions,
) {
  return render(<ComSessao usuario={usuario}>{ui}</ComSessao>, opcoes)
}
