import type { ErroDeCampo, RascunhoGerado } from "../api/cliente";

/**
 * Um formulário proposto pela IA e ainda não publicado. `chave` é a identidade estável na tela
 * (o `nome` é editável e pode repetir); `definicao` é dado não confiável, validado pelo servidor.
 */
export interface Rascunho {
  chave: string;
  nome: string;
  definicao: unknown;
  /** `campo` no formato da definição (`umidade.formula`), sem o nome do formulário. */
  erros: ErroDeCampo[];
}

export function deGerados(gerados: RascunhoGerado[], gerarChave: () => string): Rascunho[] {
  return gerados.map((gerado) => ({
    chave: gerarChave(),
    nome: gerado.nome,
    definicao: gerado.definicao,
    erros: gerado.erros,
  }));
}

/**
 * Entrega os erros do `POST /formularios/lote` aos rascunhos. O servidor prefixa cada `campo` com
 * o nome do formulário (`Proctor.umidade.formula`); como o nome pode conter ponto, vale o nome
 * mais longo que casa. O que não casa com ninguém vai para `globais`. Os erros anteriores são
 * trocados, não acumulados: o lote inteiro é validado de novo a cada tentativa.
 */
export function atribuirErrosDoLote(
  rascunhos: Rascunho[],
  erros: ErroDeCampo[],
): { rascunhos: Rascunho[]; globais: string[] } {
  const porNome = new Map<string, ErroDeCampo[]>();
  const globais: string[] = [];
  const nomes = [...new Set(rascunhos.map((r) => r.nome))].sort((a, b) => b.length - a.length);

  for (const erro of erros) {
    const nome = nomes.find((candidato) => erro.campo.startsWith(`${candidato}.`));
    if (nome === undefined) {
      globais.push(`${erro.campo}: ${erro.mensagem}`);
      continue;
    }
    const semPrefixo = { ...erro, campo: erro.campo.slice(nome.length + 1) };
    porNome.set(nome, [...(porNome.get(nome) ?? []), semPrefixo]);
  }
  return {
    rascunhos: rascunhos.map((rascunho) => ({
      ...rascunho,
      erros: porNome.get(rascunho.nome) ?? [],
    })),
    globais,
  };
}
