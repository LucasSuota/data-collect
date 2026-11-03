import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { Esquemas } from "../api/cliente";
import { EditorDeBlocos } from "./EditorDeBlocos";

const FUNCOES: Esquemas["FuncaoDoCatalogoSaida"][] = [
  { nome: "soma", assinatura: "soma(a, b, ...)", descricao: "Soma.", exemplo: "soma(a, b)" },
  { nome: "se", assinatura: "se(cond, a, b)", descricao: "Escolhe.", exemplo: "se(a, 1, 2)" },
];
const CAMPOS = [
  { id: "carga_kn", rotulo: "Carga" },
  { id: "diametro_mm", rotulo: "Diâmetro" },
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
    <EditorDeBlocos
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

const fila = () => screen.getByRole("list", { name: "Fórmula em blocos" });
const textosDosBlocos = () =>
  within(fila())
    .queryAllByRole("button", { name: /^Bloco / })
    // o "×" de remover faz parte do texto do chip
    .map((chip) => chip.textContent?.replace(/×$/, "") ?? "");
const inserir = (nome: string | RegExp) =>
  userEvent.click(screen.getByRole("button", { name: nome }));

describe("EditorDeBlocos: mostrar", () => {
  it("mostra a fórmula como uma fila de blocos", () => {
    render(<Controlado inicial="carga_kn * 2 / (pi + 1)" />);

    expect(textosDosBlocos()).toEqual(["carga_kn", "*", "2", "/", "(", "pi", "+", "1", ")"]);
  });

  it("fórmula vazia mostra a fila vazia com uma dica", () => {
    render(<Controlado />);

    expect(textosDosBlocos()).toEqual([]);
    expect(screen.getByText(/Escolha um bloco/)).toBeInTheDocument();
  });

  it("marca o par de parênteses ao lado do cursor e o parêntese sem par", () => {
    render(<Controlado inicial="(a + b" />);

    expect(screen.getByRole("button", { name: "Bloco parêntese que abre" })).toHaveAttribute(
      "data-sem-par",
      "true",
    );
  });

  it("avisa dos trechos que não têm bloco, sem descartá-los", () => {
    render(<Controlado inicial="a.b" />);

    expect(screen.getByText(/sem bloco/)).toBeInTheDocument();
    expect(textosDosBlocos()).toContain(".");
  });

  it("destaca os blocos sobre os quais o servidor apontou o erro", () => {
    render(
      <Controlado
        inicial="carga_kn + ruim"
        erro={{ mensagem: "Campo 'ruim' não existe.", posicao: { inicio: 11, fim: 15 } }}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Campo 'ruim' não existe.");
    expect(screen.getByRole("button", { name: "Bloco campo ruim" })).toHaveAttribute(
      "data-erro",
      "true",
    );
    expect(screen.getByRole("button", { name: "Bloco campo carga_kn" })).not.toHaveAttribute(
      "data-erro",
    );
  });
});

describe("EditorDeBlocos: inserir pela paleta", () => {
  it("clicar num campo o acrescenta no fim", async () => {
    const aoMudar = vi.fn();
    render(<Controlado inicial="2 *" aoMudar={aoMudar} />);

    await inserir("Inserir o campo carga_kn");

    expect(aoMudar).toHaveBeenLastCalledWith("2 * carga_kn");
  });

  it("inserir um operador e um número monta a fórmula com os espaços certos", async () => {
    const aoMudar = vi.fn();
    render(<Controlado inicial="carga_kn" aoMudar={aoMudar} />);

    await inserir("Inserir o operador *");
    await userEvent.type(screen.getByLabelText("Número"), "1000");
    await userEvent.click(screen.getByRole("button", { name: "Inserir o número" }));

    expect(aoMudar).toHaveBeenLastCalledWith("carga_kn * 1000");
  });

  it("número inválido não pode ser inserido", async () => {
    render(<Controlado />);

    await userEvent.type(screen.getByLabelText("Número"), "12abc");

    expect(screen.getByRole("button", { name: "Inserir o número" })).toBeDisabled();
  });

  it("clicar num bloco leva o cursor para depois dele, e a próxima inserção entra ali", async () => {
    const aoMudar = vi.fn();
    render(<Controlado inicial="a + b" aoMudar={aoMudar} />);

    await userEvent.click(screen.getByRole("button", { name: "Cursor depois de a" }));
    await inserir("Inserir o operador *");

    expect(aoMudar).toHaveBeenLastCalledWith("a * + b");
  });

  it("uma função entra com os dois parênteses e o cursor fica entre eles", async () => {
    const aoMudar = vi.fn();
    render(<Controlado aoMudar={aoMudar} />);

    await inserir("Inserir a função soma");
    expect(aoMudar).toHaveBeenLastCalledWith("soma()");
    await inserir("Inserir o campo carga_kn");
    await inserir("Inserir a vírgula");
    await inserir("Inserir o campo diametro_mm");

    expect(aoMudar).toHaveBeenLastCalledWith("soma(carga_kn, diametro_mm)");
  });

  it("recria a fórmula do corpo de prova só com blocos", async () => {
    const aoMudar = vi.fn();
    render(<Controlado aoMudar={aoMudar} />);
    const numero = async (valor: string) => {
      await userEvent.clear(screen.getByLabelText("Número"));
      await userEvent.type(screen.getByLabelText("Número"), valor);
      await userEvent.click(screen.getByRole("button", { name: "Inserir o número" }));
    };

    await inserir("Inserir o campo carga_kn");
    await inserir("Inserir o operador *");
    await numero("1000");
    await inserir("Inserir o operador /");
    await inserir("Inserir o parêntese que abre");
    await inserir("Inserir a constante pi");
    await inserir("Inserir o operador *");
    await inserir("Inserir o parêntese que abre");
    await inserir("Inserir o campo diametro_mm");
    await inserir("Inserir o operador /");
    await numero("2");
    await inserir("Inserir o parêntese que fecha");
    await inserir("Inserir o operador **");
    await numero("2");
    await inserir("Inserir o parêntese que fecha");

    expect(aoMudar).toHaveBeenLastCalledWith("carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)");
  });
});

describe("EditorDeBlocos: remover e reordenar", () => {
  it("o × remove o bloco", async () => {
    const aoMudar = vi.fn();
    render(<Controlado inicial="a + b" aoMudar={aoMudar} />);

    await userEvent.click(screen.getByRole("button", { name: "Remover o bloco +" }));

    expect(aoMudar).toHaveBeenLastCalledWith("a b");
  });

  it("Delete num bloco focado o remove", async () => {
    const aoMudar = vi.fn();
    render(<Controlado inicial="a + b" aoMudar={aoMudar} />);

    screen.getByRole("button", { name: "Bloco operador +" }).focus();
    await userEvent.keyboard("{Delete}");

    expect(aoMudar).toHaveBeenLastCalledWith("a b");
  });

  it("Alt+seta move o bloco focado, como alternativa a arrastar", async () => {
    const aoMudar = vi.fn();
    render(<Controlado inicial="a + b" aoMudar={aoMudar} />);

    screen.getByRole("button", { name: "Bloco campo a" }).focus();
    await userEvent.keyboard("{Alt>}{ArrowRight}{/Alt}");

    expect(aoMudar).toHaveBeenLastCalledWith("+ a b");
  });

  it("Alt+seta no limite não faz nada", async () => {
    const aoMudar = vi.fn();
    render(<Controlado inicial="a + b" aoMudar={aoMudar} />);

    screen.getByRole("button", { name: "Bloco campo a" }).focus();
    await userEvent.keyboard("{Alt>}{ArrowLeft}{/Alt}");

    expect(aoMudar).not.toHaveBeenCalled();
  });
});

describe("EditorDeBlocos: paleta", () => {
  it("lista os campos, as funções e as constantes recebidos do catálogo", () => {
    render(<Controlado />);

    expect(screen.getByRole("button", { name: "Inserir o campo carga_kn" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inserir a função se" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inserir a constante pi" })).toBeInTheDocument();
  });
});
