import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { ErroDaApi, type Definicao } from "../../api/cliente";
import { clienteFalso, renderizarComApi } from "../../test/clienteFalso";
import { ApiProvider } from "../../api/contexto";
import { ProvedorDeGavetas } from "../../registros/ProvedorDeGavetas";
import { FormRenderer } from "./FormRenderer";
import type { ErrosPorCampo, Valores } from "./tipos";

const DEFINICAO: Definicao = {
  campos: [
    { id: "secao_a", tipo: "secao", rotulo: "Dados do ensaio" },
    { id: "obs", tipo: "texto", rotulo: "Observação" },
    { id: "fck", tipo: "numero", rotulo: "fck", unidade: "MPa", obrigatorio: true },
    { id: "dia", tipo: "data", rotulo: "Data de moldagem" },
    { id: "resultado", tipo: "selecao", rotulo: "Resultado", opcoes: ["Aprovado", "Reprovado"] },
    { id: "ensaiado", tipo: "sim_nao", rotulo: "Ensaiado?" },
    {
      id: "resistencia",
      tipo: "calculado",
      rotulo: "Resistência",
      unidade: "MPa",
      casas_decimais: 1,
      formula: "fck * 2",
    },
  ],
};

/** Mantém o estado como a página faria, para testar a digitação de ponta a ponta. */
function Controlado({
  definicao = DEFINICAO,
  inicial = {},
  aoMudar,
  ...resto
}: {
  definicao?: Definicao;
  inicial?: Valores;
  aoMudar?: (v: Valores) => void;
} & Partial<Parameters<typeof FormRenderer>[0]>) {
  const [valores, setValores] = useState<Valores>(inicial);
  return (
    <FormRenderer
      definicao={definicao}
      valores={valores}
      aoMudar={(novos) => {
        setValores(novos);
        aoMudar?.(novos);
      }}
      {...resto}
    />
  );
}

const semPrevia = { previaAoVivo: false } as const;

describe("FormRenderer: cada tipo de campo", () => {
  it("renderiza o rótulo de cada campo e a seção como título", () => {
    renderizarComApi(<Controlado {...semPrevia} />, clienteFalso());

    expect(screen.getByRole("heading", { name: "Dados do ensaio" })).toBeInTheDocument();
    for (const rotulo of ["Observação", "fck", "Data de moldagem", "Resultado", "Ensaiado?"]) {
      expect(screen.getByLabelText(new RegExp(rotulo))).toBeInTheDocument();
    }
  });

  it("texto: digita e devolve o valor por id", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(<Controlado {...semPrevia} aoMudar={aoMudar} />, clienteFalso());

    await userEvent.type(screen.getByLabelText("Observação"), "ok");

    expect(aoMudar).toHaveBeenLastCalledWith({ obs: "ok" });
  });

  it("número: mostra a unidade, marca obrigatório e troca vírgula por ponto", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(<Controlado {...semPrevia} aoMudar={aoMudar} />, clienteFalso());

    const campo = screen.getByLabelText(/fck/);
    await userEvent.type(campo, "25,5");

    const moldura = campo.closest<HTMLElement>('[data-campo="fck"]');
    expect(moldura).not.toBeNull();
    expect(within(moldura as HTMLElement).getByText("(MPa)")).toBeInTheDocument();
    expect(campo).toHaveAttribute("aria-required", "true");
    expect(aoMudar).toHaveBeenLastCalledWith({ fck: "25.5" });
    expect(campo).toHaveValue("25.5");
  });

  it("data: usa o formato ISO que a API espera", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(<Controlado {...semPrevia} aoMudar={aoMudar} />, clienteFalso());

    await userEvent.type(screen.getByLabelText("Data de moldagem"), "2026-11-01");

    expect(aoMudar).toHaveBeenLastCalledWith({ dia: "2026-11-01" });
  });

  it("seleção: oferece as opções da definição e devolve a escolhida", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(<Controlado {...semPrevia} aoMudar={aoMudar} />, clienteFalso());

    const select = screen.getByLabelText("Resultado");
    expect(
      within(select)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["— selecione —", "Aprovado", "Reprovado"]);
    await userEvent.selectOptions(select, "Reprovado");

    expect(aoMudar).toHaveBeenLastCalledWith({ resultado: "Reprovado" });
  });

  it("sim/não: é tri-estado (não informado, sim, não) e devolve booleano", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(<Controlado {...semPrevia} aoMudar={aoMudar} />, clienteFalso());
    const select = screen.getByLabelText("Ensaiado?");

    expect(select).toHaveValue("");
    await userEvent.selectOptions(select, "Sim");
    expect(aoMudar).toHaveBeenLastCalledWith({ ensaiado: true });
    await userEvent.selectOptions(select, "Não");
    expect(aoMudar).toHaveBeenLastCalledWith({ ensaiado: false });
    await userEvent.selectOptions(select, "— não informado —");
    expect(aoMudar).toHaveBeenLastCalledWith({ ensaiado: null });
  });

  it("calculado: é somente leitura e não aceita digitação", () => {
    renderizarComApi(<Controlado {...semPrevia} />, clienteFalso());

    const saida = screen.getByLabelText(/Resistência/);

    expect(saida.tagName).toBe("OUTPUT");
    expect(saida).toHaveTextContent("—");
  });

  it("somente leitura desabilita todos os controles", () => {
    renderizarComApi(<Controlado {...semPrevia} somenteLeitura />, clienteFalso());

    for (const rotulo of ["Observação", "fck", "Data de moldagem", "Resultado", "Ensaiado?"]) {
      expect(screen.getByLabelText(new RegExp(rotulo))).toBeDisabled();
    }
  });
});

describe("FormRenderer: erros por campo", () => {
  it("mostra cada mensagem no campo certo, ligada ao controle", () => {
    const erros: ErrosPorCampo = {
      fck: ["Campo obrigatório.", "Deve ser um número."],
      dia: ["Data inválida."],
    };
    renderizarComApi(<Controlado {...semPrevia} erros={erros} />, clienteFalso());

    const fck = screen.getByLabelText(/fck/);
    expect(fck).toHaveAttribute("aria-invalid", "true");
    expect(fck).toHaveAccessibleDescription("Campo obrigatório. Deve ser um número.");
    expect(screen.getByLabelText("Data de moldagem")).toHaveAccessibleDescription("Data inválida.");
    expect(screen.getByLabelText("Observação")).not.toHaveAttribute("aria-invalid", "true");
    expect(screen.getAllByRole("alert")).toHaveLength(2);
  });

  it("os erros seguem o id do campo, não a posição: reordenar não os desloca", () => {
    const invertida: Definicao = { campos: [...DEFINICAO.campos].reverse() };
    const erros: ErrosPorCampo = { fck: ["Campo obrigatório."] };
    renderizarComApi(
      <Controlado {...semPrevia} definicao={invertida} erros={erros} />,
      clienteFalso(),
    );

    expect(screen.getByLabelText(/fck/)).toHaveAccessibleDescription("Campo obrigatório.");
  });

  it("os valores digitados ficam com o campo certo depois de reordenar", () => {
    const valores: Valores = { obs: "texto", fck: "25" };
    const { rerender } = render(
      <ApiProvider cliente={clienteFalso()}>
        <FormRenderer definicao={DEFINICAO} valores={valores} aoMudar={() => {}} {...semPrevia} />
      </ApiProvider>,
    );

    rerender(
      <ApiProvider cliente={clienteFalso()}>
        <FormRenderer
          definicao={{ campos: [...DEFINICAO.campos].reverse() }}
          valores={valores}
          aoMudar={() => {}}
          {...semPrevia}
        />
      </ApiProvider>,
    );

    expect(screen.getByLabelText("Observação")).toHaveValue("texto");
    expect(screen.getByLabelText(/fck/)).toHaveValue("25");
  });
});

describe("FormRenderer: campos calculados", () => {
  it("mostra o valor salvo arredondado só na exibição (casas_decimais)", () => {
    renderizarComApi(
      <Controlado
        {...semPrevia}
        calculadosSalvos={{ resistencia: { valor: "25.46479089470325", erro: null } }}
      />,
      clienteFalso(),
    );

    expect(screen.getByLabelText(/Resistência/)).toHaveTextContent("25,5");
  });

  it("mostra o erro de fórmula no próprio campo", () => {
    renderizarComApi(
      <Controlado
        {...semPrevia}
        calculadosSalvos={{ resistencia: { valor: null, erro: "Divisão por zero." } }}
      />,
      clienteFalso(),
    );

    expect(screen.getByLabelText(/Resistência/)).toHaveTextContent("Divisão por zero.");
  });

  it("formata booleano e data do jeito do usuário", () => {
    const definicao: Definicao = {
      campos: [
        { id: "ok", tipo: "calculado", rotulo: "Conforme?", formula: "x" },
        { id: "prazo", tipo: "calculado", rotulo: "Prazo", formula: "y" },
      ],
    };
    renderizarComApi(
      <Controlado
        {...semPrevia}
        definicao={definicao}
        calculadosSalvos={{
          ok: { valor: true, erro: null },
          prazo: { valor: "2026-11-29", erro: null },
        }}
      />,
      clienteFalso(),
    );

    expect(screen.getByLabelText("Conforme?")).toHaveTextContent("Sim");
    expect(screen.getByLabelText("Prazo")).toHaveTextContent("29/11/2026");
  });

  describe("prévia ao vivo", () => {
    beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
    afterEach(() => vi.useRealTimers());

    it("pede a prévia ao servidor, com debounce, e mostra o resultado", async () => {
      const previa = vi.fn(async () => ({
        valida: true,
        erros: [],
        calculados: { resistencia: { valor: "50.04", erro: null } },
      }));
      renderizarComApi(<Controlado atrasoDaPreviaMs={300} />, clienteFalso({ previa }));

      await userEvent.type(screen.getByLabelText(/fck/), "25", { delay: null });
      expect(previa).not.toHaveBeenCalled(); // o debounce ainda não venceu
      await act(() => vi.advanceTimersByTimeAsync(300));

      await waitFor(() => expect(screen.getByLabelText(/Resistência/)).toHaveTextContent("50,0"));
      expect(previa).toHaveBeenCalledTimes(1); // uma chamada para as duas teclas
      expect(previa).toHaveBeenCalledWith(DEFINICAO, { fck: "25" });
    });

    it("mostra o erro de fórmula devolvido pela prévia no campo calculado", async () => {
      const previa = vi.fn(async () => ({
        valida: true,
        erros: [],
        calculados: { resistencia: { valor: null, erro: "Divisão por zero." } },
      }));
      renderizarComApi(<Controlado atrasoDaPreviaMs={10} />, clienteFalso({ previa }));

      await act(() => vi.advanceTimersByTimeAsync(10));

      await waitFor(() =>
        expect(screen.getByLabelText(/Resistência/)).toHaveTextContent("Divisão por zero."),
      );
    });

    it("ignora uma resposta antiga que chega depois de uma digitação mais nova", async () => {
      let liberarAntiga: (valor: unknown) => void = () => {};
      const previa = vi
        .fn()
        .mockImplementationOnce(() => new Promise((resolve) => (liberarAntiga = resolve)))
        .mockResolvedValue({
          valida: true,
          erros: [],
          calculados: { resistencia: { valor: "20", erro: null } },
        });
      renderizarComApi(<Controlado atrasoDaPreviaMs={10} />, clienteFalso({ previa }));

      await act(() => vi.advanceTimersByTimeAsync(10)); // dispara a primeira (fica pendente)
      await userEvent.type(screen.getByLabelText(/fck/), "1", { delay: null });
      await act(() => vi.advanceTimersByTimeAsync(10)); // dispara a segunda, que responde 20
      await waitFor(() => expect(screen.getByLabelText(/Resistência/)).toHaveTextContent("20,0"));

      await act(async () =>
        liberarAntiga({
          valida: true,
          erros: [],
          calculados: { resistencia: { valor: "999", erro: null } },
        }),
      );

      expect(screen.getByLabelText(/Resistência/)).toHaveTextContent("20,0");
    });

    it("avisa quando a prévia está indisponível, sem derrubar o formulário", async () => {
      const previa = vi.fn(async () => {
        throw new ErroDaApi(0, "Não foi possível conectar à API.");
      });
      renderizarComApi(<Controlado atrasoDaPreviaMs={10} />, clienteFalso({ previa }));

      await act(() => vi.advanceTimersByTimeAsync(10));

      expect(await screen.findByText(/Não foi possível atualizar a prévia/)).toBeInTheDocument();
      expect(screen.getByLabelText("Observação")).toBeEnabled();
    });

    it("não pede prévia quando está desligada, nem em formulário sem calculados", async () => {
      const previa = vi.fn();
      renderizarComApi(<Controlado {...semPrevia} />, clienteFalso({ previa }));
      renderizarComApi(
        <Controlado definicao={{ campos: [{ id: "a", tipo: "texto", rotulo: "A" }] }} />,
        clienteFalso({ previa }),
      );

      await act(() => vi.advanceTimersByTimeAsync(2000));

      expect(previa).not.toHaveBeenCalled();
    });
  });
});

describe("FormRenderer: referência", () => {
  const origem = {
    id: 7,
    nome: "Ensaio",
    criado_em: "x",
    versao_atual_id: 1,
    versao_atual_numero: 1,
  };
  const registro = (id: number, umidade: string) => ({
    id,
    formulario_id: 7,
    versao_id: 1,
    dados: { umidade },
    criado_em: "2026-11-02T10:00:00+00:00",
    atualizado_em: "x",
  });
  const coluna = {
    id: "umidade",
    rotulo: "Umidade",
    tipo: "numero" as const,
    unidade: "%",
    casas_decimais: 1,
    resultado: null,
    opcoes: [],
    filtravel: false,
  };
  const definicaoDaOrigem = {
    campos: [{ id: "umidade", tipo: "numero", rotulo: "Umidade", compartilhado: true }],
  };
  const detalheDaOrigem = {
    ...origem,
    versao_atual: { id: 1, numero: 1, definicao: definicaoDaOrigem },
  };
  const definicao: Definicao = {
    campos: [
      { id: "ensaio", tipo: "referencia", rotulo: "Ensaio de origem", formulario: "ensaio" },
    ],
  };
  const clienteDaOrigem = (extra = {}) =>
    clienteFalso({
      listarFormularios: async () => [origem],
      obterFormulario: async () => detalheDaOrigem as never,
      listarVersoes: async () => [{ id: 1, numero: 1, publicada_em: "x" }],
      listarRegistros: async () => ({
        versao_id: 1,
        total: 2,
        colunas: [coluna],
        itens: [registro(11, "12.34"), registro(12, "9.8")],
      }),
      ...extra,
    });

  it("lista os registros da origem com os valores e devolve o id escolhido", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} aoMudar={aoMudar} />,
      clienteDaOrigem(),
    );

    await userEvent.click(await screen.findByRole("button", { name: /Selecionar registro$/ }));
    const gaveta = await screen.findByRole("dialog");
    expect(within(gaveta).getByText("12,3")).toBeInTheDocument();
    await userEvent.click(within(gaveta).getByRole("button", { name: "Selecionar registro 12" }));

    expect(aoMudar).toHaveBeenLastCalledWith({ ensaio: 12 });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("a busca filtra os registros pelo valor", async () => {
    renderizarComApi(<Controlado {...semPrevia} definicao={definicao} />, clienteDaOrigem());
    await userEvent.click(await screen.findByRole("button", { name: /Selecionar registro$/ }));
    const gaveta = await screen.findByRole("dialog");

    await userEvent.type(within(gaveta).getByRole("searchbox"), "9,8");

    expect(within(gaveta).queryByRole("button", { name: "Selecionar registro 11" })).toBeNull();
    expect(within(gaveta).getByRole("button", { name: "Selecionar registro 12" })).toBeVisible();
  });

  it("Esc fecha a lista sem escolher nada", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} aoMudar={aoMudar} />,
      clienteDaOrigem(),
    );
    await userEvent.click(await screen.findByRole("button", { name: /Selecionar registro$/ }));
    await screen.findByRole("dialog");

    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(aoMudar).not.toHaveBeenCalled();
  });

  it("registro escolhido aparece com os valores que a origem libera", async () => {
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} inicial={{ ensaio: 11 }} />,
      clienteDaOrigem(),
    );

    expect(await screen.findByText("12,3")).toBeInTheDocument();
    expect(screen.getByText("Umidade")).toBeInTheDocument();
    expect(screen.getByText("#11")).toBeInTheDocument();
  });

  it("remover a referência devolve null", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(
      <Controlado
        {...semPrevia}
        definicao={definicao}
        inicial={{ ensaio: 11 }}
        aoMudar={aoMudar}
      />,
      clienteDaOrigem(),
    );

    await userEvent.click(await screen.findByRole("button", { name: "Remover a referência" }));

    expect(aoMudar).toHaveBeenLastCalledWith({ ensaio: null });
  });

  it("referência preenchida aparece mesmo antes da lista carregar", () => {
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} inicial={{ ensaio: 99 }} />,
      clienteFalso({ listarFormularios: () => new Promise(() => {}) }),
    );

    expect(screen.getByText("#99")).toBeInTheDocument();
    expect(screen.getByText("Carregando os valores…")).toBeInTheDocument();
  });

  it("avisa quando a origem ainda não tem registros", async () => {
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} />,
      clienteDaOrigem({
        listarRegistros: async () => ({ versao_id: 1, colunas: [], total: 0, itens: [] }),
      }),
    );

    expect(await screen.findByText(/Ainda não há registros em “ensaio”/)).toBeInTheDocument();
  });

  it("avisa quando não consegue carregar a origem", async () => {
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} />,
      clienteFalso({ listarFormularios: async () => Promise.reject(new Error("sem rede")) }),
    );

    expect(
      await screen.findByText(/Não foi possível carregar os registros de origem/),
    ).toBeInTheDocument();
  });

  it("sem o provedor de gavetas não oferece criar nem editar a origem", async () => {
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} inicial={{ ensaio: 11 }} />,
      clienteDaOrigem(),
    );
    await screen.findByText("12,3");

    expect(screen.queryByRole("button", { name: /Criar ensaio/i })).toBeNull();
    expect(screen.queryByRole("button", { name: "Editar origem" })).toBeNull();
  });

  describe("com o provedor de gavetas", () => {
    const origemEditavel = (criarRegistro: ReturnType<typeof vi.fn>, extra = {}) =>
      clienteDaOrigem({
        criarRegistro,
        previa: async () => ({ valida: true, erros: [], calculados: {} }),
        ...extra,
      });

    it("cria o registro de origem numa gaveta e já o seleciona", async () => {
      const criarRegistro = vi.fn(async () => registro(50, "7.5"));
      const aoMudar = vi.fn();
      renderizarComApi(
        <ProvedorDeGavetas>
          <Controlado {...semPrevia} definicao={definicao} aoMudar={aoMudar} />
        </ProvedorDeGavetas>,
        origemEditavel(criarRegistro),
      );

      await userEvent.click(await screen.findByRole("button", { name: "Criar ensaio" }));
      const gaveta = await screen.findByRole("dialog", { name: /Novo registro · Ensaio/ });
      await userEvent.type(await within(gaveta).findByLabelText(/Umidade/), "7,5");
      await userEvent.click(within(gaveta).getByRole("button", { name: "Salvar" }));

      await waitFor(() => expect(aoMudar).toHaveBeenLastCalledWith({ ensaio: 50 }));
      expect(criarRegistro).toHaveBeenCalledWith(7, 1, { umidade: "7.5" });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("salvar na gaveta não envia o formulário que está por baixo", async () => {
      const criarRegistro = vi.fn(async () => registro(50, "7.5"));
      const aoEnviar = vi.fn((evento: { preventDefault: () => void }) => evento.preventDefault());
      renderizarComApi(
        <ProvedorDeGavetas>
          <form onSubmit={aoEnviar}>
            <Controlado {...semPrevia} definicao={definicao} />
          </form>
        </ProvedorDeGavetas>,
        origemEditavel(criarRegistro),
      );
      await userEvent.click(await screen.findByRole("button", { name: "Criar ensaio" }));
      const gaveta = await screen.findByRole("dialog");
      await userEvent.type(await within(gaveta).findByLabelText(/Umidade/), "7,5");

      await userEvent.click(within(gaveta).getByRole("button", { name: "Salvar" }));

      await waitFor(() => expect(criarRegistro).toHaveBeenCalled());
      expect(aoEnviar).not.toHaveBeenCalled();
    });

    it("cancelar a gaveta não muda a referência", async () => {
      const aoMudar = vi.fn();
      renderizarComApi(
        <ProvedorDeGavetas>
          <Controlado {...semPrevia} definicao={definicao} aoMudar={aoMudar} />
        </ProvedorDeGavetas>,
        origemEditavel(vi.fn()),
      );
      await userEvent.click(await screen.findByRole("button", { name: "Criar ensaio" }));
      const gaveta = await screen.findByRole("dialog");
      await within(gaveta).findByLabelText(/Umidade/);

      await userEvent.click(within(gaveta).getByRole("button", { name: "Cancelar" }));

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(aoMudar).not.toHaveBeenCalled();
    });

    it("edita a origem selecionada e recarrega os valores", async () => {
      const atualizarRegistro = vi.fn(async () => registro(11, "20"));
      const aoMudar = vi.fn();
      renderizarComApi(
        <ProvedorDeGavetas>
          <Controlado
            {...semPrevia}
            definicao={definicao}
            inicial={{ ensaio: 11 }}
            aoMudar={aoMudar}
          />
        </ProvedorDeGavetas>,
        origemEditavel(vi.fn(), {
          atualizarRegistro,
          obterRegistro: async () => registro(11, "12.34"),
          obterVersao: async () => ({
            id: 1,
            formulario_id: 7,
            numero: 1,
            definicao: definicaoDaOrigem,
            publicada_em: "x",
          }),
        }),
      );

      await userEvent.click(await screen.findByRole("button", { name: "Editar origem" }));
      const gaveta = await screen.findByRole("dialog", { name: /Registro 11 · Ensaio/ });
      const campo = await within(gaveta).findByLabelText(/Umidade/);
      await userEvent.clear(campo);
      await userEvent.type(campo, "20");
      await userEvent.click(within(gaveta).getByRole("button", { name: "Salvar" }));

      await waitFor(() => expect(atualizarRegistro).toHaveBeenCalledWith(11, { umidade: "20" }));
      await waitFor(() => expect(aoMudar).toHaveBeenLastCalledWith({ ensaio: 11 }));
    });
  });
});

describe("FormRenderer: localização", () => {
  const definicao: Definicao = { campos: [{ id: "local", tipo: "localizacao", rotulo: "Local" }] };

  it("tem latitude e longitude e devolve o par como texto (vírgula vira ponto)", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} aoMudar={aoMudar} />,
      clienteFalso(),
    );

    await userEvent.type(screen.getByLabelText("Local: latitude"), "-23,550520");
    await userEvent.type(screen.getByLabelText("Local: longitude"), "-46.633308");

    expect(aoMudar).toHaveBeenLastCalledWith({
      local: { latitude: "-23.550520", longitude: "-46.633308" },
    });
  });

  it("mostra o erro do servidor (faixa, par incompleto) no campo", () => {
    renderizarComApi(
      <Controlado
        {...semPrevia}
        definicao={definicao}
        erros={{ local: ["Informe latitude e longitude juntas."] }}
      />,
      clienteFalso(),
    );

    expect(screen.getByLabelText("Local: latitude")).toHaveAccessibleDescription(
      "Informe latitude e longitude juntas.",
    );
  });
});

describe("FormRenderer: foto", () => {
  const definicao: Definicao = {
    campos: [{ id: "fotos", tipo: "foto", rotulo: "Fotos", maximo: 2 }],
  };
  const arquivo = (nome = "a.jpg") =>
    new File([new Uint8Array([1, 2])], nome, { type: "image/jpeg" });
  const blob = new Blob([new Uint8Array([1])], { type: "image/webp" });

  it("envia o arquivo, guarda só o id e mostra a miniatura", async () => {
    const enviarAnexo = vi.fn(async () => ({ id: 41, largura: 10, altura: 10, tamanho_bytes: 99 }));
    const obterAnexo = vi.fn(async () => blob);
    const aoMudar = vi.fn();
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} aoMudar={aoMudar} />,
      clienteFalso({ enviarAnexo, obterAnexo }),
    );

    await userEvent.upload(screen.getByLabelText("Fotos"), arquivo());

    expect(enviarAnexo).toHaveBeenCalledTimes(1);
    expect(aoMudar).toHaveBeenLastCalledWith({ fotos: [41] });
    expect(await screen.findByRole("img", { name: "Fotos: foto 41" })).toHaveAttribute(
      "src",
      "blob:miniatura-de-teste",
    );
    expect(obterAnexo).toHaveBeenCalledWith(41);
  });

  it("remove uma foto sem apagar as outras", async () => {
    const aoMudar = vi.fn();
    renderizarComApi(
      <Controlado
        {...semPrevia}
        definicao={definicao}
        inicial={{ fotos: [1, 2] }}
        aoMudar={aoMudar}
      />,
      clienteFalso({ obterAnexo: async () => blob }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Remover foto 1" }));

    expect(aoMudar).toHaveBeenLastCalledWith({ fotos: [2] });
  });

  it("respeita o máximo: ao atingir, bloqueia o envio e avisa", async () => {
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} inicial={{ fotos: [1, 2] }} />,
      clienteFalso({ obterAnexo: async () => blob }),
    );

    expect(screen.getByLabelText("Fotos")).toBeDisabled();
    expect(screen.getByText("Limite de 2 foto(s) atingido.")).toBeInTheDocument();
  });

  it("com vários arquivos de uma vez, para no máximo", async () => {
    let proximo = 100;
    const enviarAnexo = vi.fn(async () => ({
      id: proximo++,
      largura: 1,
      altura: 1,
      tamanho_bytes: 1,
    }));
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} />,
      clienteFalso({ enviarAnexo, obterAnexo: async () => blob }),
    );

    await userEvent.upload(screen.getByLabelText("Fotos"), [
      arquivo("1.jpg"),
      arquivo("2.jpg"),
      arquivo("3.jpg"),
    ]);

    expect(enviarAnexo).toHaveBeenCalledTimes(2);
  });

  it("mostra o motivo em português quando o servidor recusa a foto", async () => {
    const enviarAnexo = vi.fn(async () => {
      throw new ErroDaApi(422, "Foto inválida.", [
        { campo: "arquivo", mensagem: "Fotos em formato HEIC não são suportadas." },
      ]);
    });
    const aoMudar = vi.fn();
    renderizarComApi(
      <Controlado {...semPrevia} definicao={definicao} aoMudar={aoMudar} />,
      clienteFalso({ enviarAnexo }),
    );

    await userEvent.upload(screen.getByLabelText("Fotos"), arquivo("x.heic"));

    expect(
      await screen.findByText("Fotos em formato HEIC não são suportadas."),
    ).toBeInTheDocument();
    expect(aoMudar).not.toHaveBeenCalled();
  });

  it("só aceita os formatos que a API aceita no seletor de arquivo", () => {
    renderizarComApi(<Controlado {...semPrevia} definicao={definicao} />, clienteFalso());

    expect(screen.getByLabelText("Fotos")).toHaveAttribute(
      "accept",
      "image/jpeg,image/png,image/webp",
    );
  });
});
