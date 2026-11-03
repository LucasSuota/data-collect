import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Aviso, Botao, CampoDeTexto, EstadoVazio, Icone } from ".";

describe("Botao", () => {
  it("é type=button por padrão, para não enviar o formulário que o contém", async () => {
    const aoEnviar = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={aoEnviar}>
        <Botao>Cancelar</Botao>
      </form>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(aoEnviar).not.toHaveBeenCalled();
  });

  it("aceita type=submit quando é o botão de enviar", async () => {
    const aoEnviar = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={aoEnviar}>
        <Botao type="submit">Salvar</Botao>
      </form>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(aoEnviar).toHaveBeenCalledTimes(1);
  });

  it("desabilitado não dispara o clique", async () => {
    const aoClicar = vi.fn();
    render(
      <Botao disabled onClick={aoClicar}>
        Excluir
      </Botao>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Excluir" }));

    expect(aoClicar).not.toHaveBeenCalled();
  });

  it("carregando bloqueia novos cliques e avisa o leitor de tela", async () => {
    const aoClicar = vi.fn();
    render(
      <Botao carregando onClick={aoClicar}>
        Salvar
      </Botao>,
    );
    const botao = screen.getByRole("button", { name: "Salvar" });

    await userEvent.click(botao);

    expect(botao).toBeDisabled();
    expect(botao).toHaveAttribute("aria-busy", "true");
    expect(aoClicar).not.toHaveBeenCalled();
  });
});

describe("CampoDeTexto", () => {
  it("liga o rótulo ao campo", () => {
    render(<CampoDeTexto rotulo="Nome da pasta" />);

    expect(screen.getByLabelText("Nome da pasta")).toBeInTheDocument();
  });

  it("sem erro, não marca o campo como inválido", () => {
    render(<CampoDeTexto rotulo="Nome" />);

    expect(screen.getByLabelText("Nome")).toHaveAttribute("aria-invalid", "false");
  });

  it("com erro, marca inválido e liga a mensagem ao campo", () => {
    render(<CampoDeTexto rotulo="Nome" erros={["Já existe uma pasta com este nome."]} />);

    const campo = screen.getByLabelText("Nome");

    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription("Já existe uma pasta com este nome.");
  });

  it("junta o erro e a dica na descrição do campo", () => {
    render(<CampoDeTexto rotulo="Nome" erros={["Obrigatório."]} dica="Até 60 letras." />);

    expect(screen.getByLabelText("Nome")).toHaveAccessibleDescription(
      "Obrigatório. Até 60 letras.",
    );
  });

  it("repassa as props do input (valor e onChange)", async () => {
    const aoMudar = vi.fn();
    render(<CampoDeTexto rotulo="Nome" onChange={aoMudar} />);

    await userEvent.type(screen.getByLabelText("Nome"), "ab");

    expect(aoMudar).toHaveBeenCalledTimes(2);
  });
});

describe("Aviso", () => {
  it("erro é um alerta", () => {
    render(<Aviso tom="erro">Não foi possível salvar.</Aviso>);

    expect(screen.getByRole("alert")).toHaveTextContent("Não foi possível salvar.");
  });

  it("sucesso e informação são status, que não interrompem o leitor de tela", () => {
    render(
      <>
        <Aviso tom="sucesso">Salvo.</Aviso>
        <Aviso tom="info">Dica.</Aviso>
      </>,
    );

    expect(screen.getAllByRole("status")).toHaveLength(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("mostra as ações ao lado do texto", () => {
    render(
      <Aviso tom="sucesso" acoes={<Botao>Editar a cópia</Botao>}>
        Criado.
      </Aviso>,
    );

    expect(screen.getByRole("button", { name: "Editar a cópia" })).toBeInTheDocument();
  });
});

describe("EstadoVazio", () => {
  it("mostra título, explicação e a ação", () => {
    render(
      <EstadoVazio icone="pasta" titulo="Nenhum formulário ainda" acao={<Botao>Criar</Botao>}>
        Crie o primeiro no construtor.
      </EstadoVazio>,
    );

    expect(screen.getByRole("heading", { name: "Nenhum formulário ainda" })).toBeInTheDocument();
    expect(screen.getByText("Crie o primeiro no construtor.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar" })).toBeInTheDocument();
  });
});

describe("Icone", () => {
  it("é decorativo: escondido do leitor de tela", () => {
    const { container } = render(<Icone nome="copiar" />);

    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});
