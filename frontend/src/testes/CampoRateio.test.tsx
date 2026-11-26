import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CampoRateio } from '../componentes/CampoRateio'

/**
 * O coração da tela do plano (docs/PLANO-DE-MIDIA-UI.md §4.3): só o campo
 * com foco guarda o texto bruto digitado, o irmão deriva em memória sem
 * rede, o PATCH sai só no blur com um campo só, e a resposta do servidor é
 * quem substitui os dois números.
 */
describe('CampoRateio', () => {
  function montar(aoSalvar = vi.fn().mockResolvedValue(undefined)) {
    const utils = render(
      <CampoRateio
        valor="100.00"
        percentual="50.000"
        valorPai="200.00"
        rotulo="Campanha de Julho"
        aoSalvar={aoSalvar}
      />,
    )
    return { ...utils, aoSalvar }
  }

  it('deriva o percentual em memória, sem perder o texto bruto digitado no campo com foco', async () => {
    const usuario = userEvent.setup()
    montar()

    const campoValor = screen.getByLabelText('Campanha de Julho — valor em reais')
    const campoPercentual = screen.getByLabelText('Campanha de Julho — percentual do orçamento acima')

    await usuario.clear(campoValor)
    await usuario.type(campoValor, '150')

    // O campo com foco mostra exatamente o que foi digitado — nunca
    // reformatado a cada tecla (isso roubaria o cursor).
    expect(campoValor).toHaveValue('150')

    // O irmão sem foco deriva ao vivo, em memória: 150 / 200 * 100 = 75,000.
    expect(campoPercentual).toHaveValue('75,000')
    expect(campoPercentual).toHaveAttribute('data-derivado')
    // O campo com foco nunca carrega `data-derivado` — é o que a pessoa
    // está digitando, não o que a tela calculou.
    expect(campoValor).not.toHaveAttribute('data-derivado')
  })

  it('não chama a rede enquanto digita — só no blur, e manda um único campo', async () => {
    const usuario = userEvent.setup()
    const { aoSalvar } = montar()

    const campoValor = screen.getByLabelText('Campanha de Julho — valor em reais')
    await usuario.clear(campoValor)
    await usuario.type(campoValor, '150')
    expect(aoSalvar).not.toHaveBeenCalled()

    await usuario.tab() // sai do campo → blur
    // `waitFor` (não a asserção direta): deixa o `finally` de `confirmar`
    // (setSalvando(null), depois da Promise resolvida) assentar dentro de
    // `act`, em vez de vazar para o próximo teste como warning.
    await waitFor(() => expect(aoSalvar).toHaveBeenCalledTimes(1))
    expect(aoSalvar).toHaveBeenCalledWith('valor', '150')
  })

  it('edita o percentual e manda só `percentual` no blur — nunca os dois', async () => {
    const usuario = userEvent.setup()
    const { aoSalvar } = montar()

    const campoPercentual = screen.getByLabelText('Campanha de Julho — percentual do orçamento acima')
    await usuario.clear(campoPercentual)
    await usuario.type(campoPercentual, '25')
    await usuario.tab()

    await waitFor(() => expect(aoSalvar).toHaveBeenCalledTimes(1))
    expect(aoSalvar).toHaveBeenCalledWith('percentual', '25')
  })

  it('a resposta do servidor (via props) substitui os dois campos depois de salvo', async () => {
    const usuario = userEvent.setup()
    const aoSalvar = vi.fn().mockResolvedValue(undefined)
    const { rerender } = render(
      <CampoRateio
        valor="100.00"
        percentual="50.000"
        valorPai="200.00"
        rotulo="Campanha de Julho"
        aoSalvar={aoSalvar}
      />,
    )

    const campoValor = screen.getByLabelText('Campanha de Julho — valor em reais')
    await usuario.clear(campoValor)
    await usuario.type(campoValor, '150')
    // `fireEvent.blur`, não `Tab`: Tab moveria o foco para o campo % IRMÃO
    // (dentro do mesmo `CampoRateio`) e o componente propositalmente NÃO
    // ressincroniza com o servidor enquanto qualquer um dos dois campos
    // ainda está com foco — este teste isola o caso "os dois estão ociosos".
    fireEvent.blur(campoValor)
    await waitFor(() => expect(aoSalvar).toHaveBeenCalledTimes(1))

    // Simula o pai atualizando as props com o que o servidor devolveu
    // (quantizado, arredondado — a fonte da verdade).
    rerender(
      <CampoRateio
        valor="150.00"
        percentual="75.000"
        valorPai="200.00"
        rotulo="Campanha de Julho"
        aoSalvar={aoSalvar}
      />,
    )

    expect(screen.getByLabelText('Campanha de Julho — valor em reais')).toHaveValue('150,00')
    expect(screen.getByLabelText('Campanha de Julho — percentual do orçamento acima')).toHaveValue(
      '75,000',
    )
  })

  it('mostra o erro do servidor no campo que falhou, sem apagar o texto digitado', async () => {
    const usuario = userEvent.setup()
    const aoSalvar = vi.fn().mockRejectedValue(new Error('Percentual não pode passar de 100.'))
    montar(aoSalvar)

    const campoValor = screen.getByLabelText('Campanha de Julho — valor em reais')
    await usuario.clear(campoValor)
    await usuario.type(campoValor, '999')
    await usuario.tab()

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível salvar.')
    expect(campoValor).toHaveAttribute('aria-invalid', 'true')
    // O texto digitado continua na tela — o erro não apaga o que a pessoa escreveu.
    expect(campoValor).toHaveValue('999')
  })

  it('Enter confirma e move o foco para o próximo campo de rateio da mesma coluna', async () => {
    const usuario = userEvent.setup()
    const aoSalvar = vi.fn().mockResolvedValue(undefined)
    render(
      <>
        <CampoRateio
          valor="100.00"
          percentual="50.000"
          valorPai="200.00"
          rotulo="Linha 1"
          aoSalvar={aoSalvar}
        />
        <CampoRateio
          valor="60.00"
          percentual="30.000"
          valorPai="200.00"
          rotulo="Linha 2"
          aoSalvar={aoSalvar}
        />
      </>,
    )

    const valor1 = screen.getByLabelText('Linha 1 — valor em reais')
    const valor2 = screen.getByLabelText('Linha 2 — valor em reais')

    valor1.focus()
    await usuario.keyboard('{Enter}')

    expect(valor2).toHaveFocus()
    await waitFor(() => expect(aoSalvar).toHaveBeenCalledTimes(1))
  })
})
