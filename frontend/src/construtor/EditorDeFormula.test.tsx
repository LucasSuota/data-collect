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

  it("não interpreta o texto como HTML", () => {
    render(<Controlado inicial="<img src=x onerror=alert(1)>" />);

    expect(document.querySelector("img")).toBeNull();
  });
});
