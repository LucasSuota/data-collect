import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { Esquemas } from "../api/cliente";
import { EditorDeFormula } from "./EditorDeFormula";

const FUNCOES: Esquemas["FuncaoDoCatalogoSaida"][] = [
  {
    nome: "soma",
    assinatura: "soma(a, b, ...)",
    descricao: "Soma de números.",
    exemplo: "soma(a, b)",
  },
  {
    nome: "se",
    assinatura: "se(cond, a, b)",
    descricao: "Escolhe um valor.",
    exemplo: "se(a > 1, 1, 2)",
  },
  { nome: "dias", assinatura: "dias(n)", descricao: "Duração em dias.", exemplo: "dias(28)" },
];
const CAMPOS = [
  { id: "fck_mpa", rotulo: "fck" },
  { id: "carga_kn", rotulo: "Carga" },
];

function Controlado({
  inicial = "",
  erro,
  aoMudar,
}: {
  inicial?: string;
  erro?: { mensagem: string; posicao?: { inicio: number; fim: number } | null };
  aoMudar?: (v: string) => void;
}) {
  const [valor, setValor] = useState(inicial);
  return (
    <EditorDeFormula
      id="formula"
      rotulo="Fórmula"
      valor={valor}
      aoMudar={(novo) => {
        setValor(novo);
        aoMudar?.(novo);
      }}
      funcoes={FUNCOES}
      constantes={["pi"]}
      campos={CAMPOS}
      erro={erro}
    />
  );
}

describe("EditorDeFormula", () => {
  it("edita o texto da fórmula", async () => {
    const aoMudar = vi.fn();
    render(<Controlado aoMudar={aoMudar} />);

    await userEvent.type(screen.getByLabelText("Fórmula"), "a + 1");

    expect(aoMudar).toHaveBeenLastCalledWith("a + 1");
  });

  describe("erro sublinhado por posição", () => {
    it("sublinha exatamente o trecho indicado pelo servidor", () => {
      render(
        <Controlado
          inicial="carga + __import__('os')"
          erro={{ mensagem: "Função '__import__' não permitida.", posicao: { inicio: 8, fim: 24 } }}
        />,
      );

      expect(screen.getByTestId("trecho-com-erro")).toHaveTextContent("__import__('os')");
      expect(screen.getByRole("alert")).toHaveTextContent("Função '__import__' não permitida.");
    });

    it("sem posição, mostra só a mensagem", () => {
      render(<Controlado inicial="a +" erro={{ mensagem: "Sintaxe inválida.", posicao: null }} />);

      expect(screen.queryByTestId("trecho-com-erro")).not.toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent("Sintaxe inválida.");
    });

    it("posição fora do texto atual (o usuário já editou) não quebra nem sublinha", () => {
      render(<Controlado inicial="a" erro={{ mensagem: "x", posicao: { inicio: 40, fim: 50 } }} />);

      expect(screen.queryByTestId("trecho-com-erro")).not.toBeInTheDocument();
    });

    it("conta caracteres, não unidades UTF-16 (emoji conta como um)", () => {
      render(
        <Controlado inicial="😀 + ruim" erro={{ mensagem: "x", posicao: { inicio: 4, fim: 8 } }} />,
      );

      expect(screen.getByTestId("trecho-com-erro")).toHaveTextContent("ruim");
    });

    it("liga o campo à mensagem para leitores de tela", () => {
      render(<Controlado inicial="a +" erro={{ mensagem: "Sintaxe inválida.", posicao: null }} />);

      const campo = screen.getByLabelText("Fórmula");
      expect(campo).toHaveAttribute("aria-invalid", "true");
      expect(campo).toHaveAccessibleDescription(/Sintaxe inválida/);
    });

    it("sem erro, nada é sublinhado e o campo é válido", () => {
      render(<Controlado inicial="a + 1" />);

      expect(screen.queryByTestId("trecho-com-erro")).not.toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.getByLabelText("Fórmula")).not.toHaveAttribute("aria-invalid", "true");
    });
  });

  describe("ajuda e autocompletar (vindos do catálogo)", () => {
    it("lista as funções do catálogo, com assinatura e descrição", () => {
      render(<Controlado />);

      const ajuda = screen.getByRole("group", { name: "Funções disponíveis" });
      expect(
        within(ajuda)
          .getAllByRole("listitem")
          .map((li) => li.textContent),
      ).toEqual([
        expect.stringContaining("soma(a, b, ...)"),
        expect.stringContaining("se(cond, a, b)"),
        expect.stringContaining("dias(n)"),
      ]);
      expect(within(ajuda).getByText("Escolhe um valor.")).toBeInTheDocument();
    });

    it("lista os campos referenciáveis e as constantes", () => {
      render(<Controlado />);

      const campos = screen.getByRole("group", { name: "Campos e constantes" });
      expect(within(campos).getByRole("button", { name: /fck_mpa/ })).toBeInTheDocument();
      expect(within(campos).getByRole("button", { name: /carga_kn/ })).toBeInTheDocument();
      expect(within(campos).getByRole("button", { name: "pi" })).toBeInTheDocument();
    });

    it("sugere funções e campos que combinam com o que está sendo digitado", async () => {
      render(<Controlado />);

      await userEvent.type(screen.getByLabelText("Fórmula"), "2 * ca");

      const sugestoes = screen.getByRole("listbox", { name: "Sugestões" });
      expect(
        within(sugestoes)
          .getAllByRole("option")
          .map((o) => o.textContent),
      ).toEqual([expect.stringContaining("carga_kn")]);
    });

    it("escolher uma função sugerida a completa com o parêntese", async () => {
      render(<Controlado inicial="1 + " />);

      await userEvent.type(screen.getByLabelText("Fórmula"), "so");
      await userEvent.click(screen.getByRole("option", { name: /soma/ }));

      expect(screen.getByLabelText("Fórmula")).toHaveValue("1 + soma(");
    });

    it("escolher um campo sugerido o completa sem parêntese", async () => {
      render(<Controlado />);

      await userEvent.type(screen.getByLabelText("Fórmula"), "fck");
      await userEvent.click(screen.getByRole("option", { name: /fck_mpa/ }));

      expect(screen.getByLabelText("Fórmula")).toHaveValue("fck_mpa");
    });

    it("sem nada digitado ou sem correspondência, não mostra sugestões", async () => {
      render(<Controlado />);

      expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
      await userEvent.type(screen.getByLabelText("Fórmula"), "zzz");
      expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    });

    it("clicar numa função da ajuda a insere no fim", async () => {
      render(<Controlado inicial="a + " />);

      await userEvent.click(screen.getByRole("button", { name: "Inserir dias(n)" }));

      expect(screen.getByLabelText("Fórmula")).toHaveValue("a + dias(");
    });

    it("clicar num campo da ajuda o insere", async () => {
      render(<Controlado inicial="2 * " />);

      await userEvent.click(screen.getByRole("button", { name: /carga_kn/ }));

      expect(screen.getByLabelText("Fórmula")).toHaveValue("2 * carga_kn");
    });
  });

  describe("autocompletar pelo teclado (combobox)", () => {
    it("o campo é um combobox ligado à lista de sugestões", async () => {
      render(<Controlado />);

      const campo = screen.getByRole("combobox", { name: "Fórmula" });
      expect(campo).toHaveAttribute("aria-expanded", "false");
      await userEvent.type(campo, "so");

      expect(campo).toHaveAttribute("aria-expanded", "true");
      expect(campo).toHaveAttribute("aria-controls", screen.getByRole("listbox").id);
    });

    it("seta para baixo escolhe a primeira sugestão e Enter a insere", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "so");
      await userEvent.keyboard("{ArrowDown}");
      expect(screen.getByRole("option", { name: /soma/ })).toHaveAttribute("aria-selected", "true");
      expect(campo).toHaveAttribute("aria-activedescendant", screen.getByRole("option").id);
      await userEvent.keyboard("{Enter}");

      expect(campo).toHaveValue("soma(");
    });

    it("seta para cima a partir do nada vai para a última, e as setas dão a volta", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "d");
      // Sugestões para "d": dias (função). Só uma, então cima e baixo ficam nela.
      await userEvent.keyboard("{ArrowUp}");
      expect(screen.getByRole("option", { name: /dias/ })).toHaveAttribute("aria-selected", "true");
      await userEvent.keyboard("{ArrowDown}");

      expect(screen.getByRole("option", { name: /dias/ })).toHaveAttribute("aria-selected", "true");
    });

    it("Tab também aceita a sugestão escolhida", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "fck");
      await userEvent.keyboard("{ArrowDown}{Tab}");

      expect(campo).toHaveValue("fck_mpa");
    });

    it("Enter sem sugestão escolhida não insere nada (segue a quebra de linha)", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "so{Enter}");

      expect(campo).toHaveValue("so\n");
    });

    it("Esc fecha a lista, e digitar de novo a reabre", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "so");
      await userEvent.keyboard("{Escape}");
      expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
      await userEvent.type(campo, "m");

      expect(screen.getByRole("listbox")).toBeInTheDocument();
    });
  });

  describe("dica da função", () => {
    it("mostra a assinatura, a descrição e o exemplo da função em que o cursor está", () => {
      render(<Controlado inicial="1 + se(" />);

      const dica = screen.getByRole("note", { name: "Ajuda da função se" });
      expect(dica).toHaveTextContent("se(cond, a, b)");
      expect(dica).toHaveTextContent("Escolhe um valor.");
      expect(dica).toHaveTextContent("se(a > 1, 1, 2)");
    });

    it("destaca o argumento que está sendo digitado", () => {
      render(<Controlado inicial="se(a > 1, " />);

      const dica = screen.getByRole("note", { name: "Ajuda da função se" });
      expect(
        within(dica).getByText("a", { selector: "[aria-current='true']" }),
      ).toBeInTheDocument();
    });

    it("em função variádica, os argumentos extras destacam o `...`", () => {
      render(<Controlado inicial="soma(1, 2, 3, 4, " />);

      const dica = screen.getByRole("note", { name: "Ajuda da função soma" });
      expect(
        within(dica).getByText("...", { selector: "[aria-current='true']" }),
      ).toBeInTheDocument();
    });

    it("fora de uma função, ou numa função desconhecida, não mostra dica", () => {
      const { rerender } = render(<Controlado inicial="1 + (2" />);
      expect(screen.queryByRole("note")).not.toBeInTheDocument();

      rerender(<Controlado inicial="desconhecida(" />);
      expect(screen.queryByRole("note")).not.toBeInTheDocument();
    });
  });

  describe("parênteses", () => {
    it("ao digitar `(` insere o par e deixa o cursor no meio", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "2 * (3 + 4");

      expect(campo).toHaveValue("2 * (3 + 4)");
    });

    it("digitar `)` quando o próximo já é `)` só avança, sem duplicar", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "(3 + 4)");

      expect(campo).toHaveValue("(3 + 4)");
    });

    it("apagar entre `(` e `)` vazios remove o par", async () => {
      render(<Controlado />);
      const campo = screen.getByRole("combobox", { name: "Fórmula" });

      await userEvent.type(campo, "a + (");
      await userEvent.keyboard("{Backspace}");

      expect(campo).toHaveValue("a + ");
    });

    it("destaca o par do parêntese ao lado do cursor", () => {
      render(<Controlado inicial="soma(a, (b + c))" />);

      // O cursor começa no fim, logo depois do último `)`.
      const pares = screen.getAllByTestId("par-do-cursor");
      expect(pares.map((p) => p.textContent)).toEqual(["(", ")"]);
    });

    it("sinaliza o parêntese sem par antes mesmo de validar", () => {
      render(<Controlado inicial="(a + b" />);

      expect(screen.getByTestId("parentese-sem-par")).toHaveTextContent("(");
    });

    it("sinaliza o `)` que sobrou", () => {
      render(<Controlado inicial="a + b)" />);

      expect(screen.getByTestId("parentese-sem-par")).toHaveTextContent(")");
    });

    it("parênteses casados não são sinalizados como erro", () => {
      render(<Controlado inicial="(a + b) * 2" />);

      expect(screen.queryByTestId("parentese-sem-par")).not.toBeInTheDocument();
    });
  });

  it("não interpreta o texto como HTML", () => {
    render(<Controlado inicial="<img src=x onerror=alert(1)>" />);

    expect(document.querySelector("img")).toBeNull();
  });
});
