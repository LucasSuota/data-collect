import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown, lerBlocos } from "./Markdown";

describe("Markdown", () => {
  it("renderiza título, parágrafo e negrito como elementos", () => {
    render(<Markdown texto={"# Termos\n\nTexto com **destaque**."} />);

    expect(screen.getByRole("heading", { name: "Termos" })).toBeInTheDocument();
    expect(screen.getByText("destaque").tagName).toBe("STRONG");
  });

  it("nunca injeta HTML cru: a tag vira texto", () => {
    const { container } = render(
      <Markdown texto={'<img src=x onerror="alert(1)"> e <script>x</script>'} />,
    );

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>");
  });

  it("descarta links com esquema perigoso e mantém só o texto", () => {
    render(<Markdown texto={"[clique](javascript:alert(1)) e [ok](https://exemplo.com)"} />);

    expect(screen.queryByRole("link", { name: "clique" })).toBeNull();
    expect(screen.getByText(/clique/)).toBeInTheDocument();
    const ok = screen.getByRole("link", { name: "ok" });
    expect(ok).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("aceita link interno por hash sem abrir outra aba", () => {
    render(<Markdown texto={"[Equipe](#/equipe)"} />);

    expect(screen.getByRole("link", { name: "Equipe" })).not.toHaveAttribute("target");
  });

  it("monta listas ordenadas e não ordenadas", () => {
    render(<Markdown texto={"- um\n- dois\n\n1. primeiro\n2. segundo"} />);

    expect(screen.getAllByRole("list")).toHaveLength(2);
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("monta tabelas com cabeçalho", () => {
    render(<Markdown texto={"| Tipo | Uso |\n|---|---|\n| texto | livre |"} />);

    expect(screen.getByRole("columnheader", { name: "Tipo" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "livre" })).toBeInTheDocument();
  });

  it("ignora o cabeçalho `versao:` dos textos legais", () => {
    expect(lerBlocos("versao: 2026-11-03\n\n# Termos")).toEqual([
      { tipo: "titulo", nivel: 1, texto: "Termos" },
    ]);
  });

  it("mantém o código em bloco, sem interpretar o conteúdo", () => {
    render(<Markdown texto={"```\nse(a > 1, **x**, 0)\n```"} />);

    expect(screen.getByText("se(a > 1, **x**, 0)")).toBeInTheDocument();
  });
});
