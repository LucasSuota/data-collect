import { useEffect, useState } from "react";
import type { Exemplo } from "../api/cliente";
import { useApi } from "../api/contexto";
import { mensagemDoErro } from "../lib/erros";
import type { Rota } from "../rotas";
import { Aviso, Botao, Esqueleto } from "../ui";

/** Quando um exemplo depende de outros, importar um traz os que ele precisa (origens primeiro). */
export function comDependencias(
  nome: string,
  exemplos: Exemplo[],
  escolhidos: Set<string>,
): Set<string> {
  const saida = new Set(escolhidos);
  const visitar = (n: string) => {
    if (saida.has(n) && n !== nome) return;
    saida.add(n);
    for (const dep of exemplos.find((e) => e.nome === n)?.depende_de ?? []) visitar(dep);
  };
  visitar(nome);
  return saida;
}

export function PaginaDeExemplos({ navegar }: { navegar: (rota: Rota) => void }) {
  const api = useApi();
  const [exemplos, setExemplos] = useState<Exemplo[] | null>(null);
  const [escolhidos, setEscolhidos] = useState<Set<string>>(new Set());
  const [erro, setErro] = useState<string | null>(null);
  const [importando, setImportando] = useState(false);

  useEffect(() => {
    let ativo = true;
    void api.exemplos().then(
      (e) => ativo && setExemplos(e),
      (e) => ativo && (setErro(mensagemDoErro(e)), setExemplos([])),
    );
    return () => {
      ativo = false;
    };
  }, [api]);

  function alternar(nome: string) {
    setEscolhidos((atual) => {
      if (atual.has(nome)) {
        const proximo = new Set(atual);
        proximo.delete(nome);
        return proximo;
      }
      return comDependencias(nome, exemplos ?? [], atual);
    });
  }

  async function importar() {
    setImportando(true);
    setErro(null);
    try {
      await api.importarExemplos([...escolhidos]);
      navegar({ nome: "formularios" });
    } catch (e) {
      setErro(mensagemDoErro(e));
      setImportando(false);
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <header>
        <h1 className="text-3xl font-extrabold">Galeria de exemplos</h1>
        <p className="mt-1 text-sm text-pedra-600">
          Comece por um modelo pronto. Ele vira um formulário da sua equipe, que você pode editar à
          vontade.
        </p>
      </header>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      {exemplos === null ? (
        <div role="status" aria-label="Carregando" className="flex flex-col gap-2">
          <Esqueleto className="h-20 rounded-cartao" />
          <Esqueleto className="h-20 rounded-cartao" />
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {exemplos.map((e) => (
            <li key={e.nome}>
              <label className="flex min-h-16 cursor-pointer items-start gap-3 rounded-cartao border border-pedra-200 bg-superficie p-3 shadow-cartao has-checked:border-sinal-500">
                <input
                  type="checkbox"
                  checked={escolhidos.has(e.nome)}
                  onChange={() => alternar(e.nome)}
                  className="mt-1 size-5 accent-sinal-500"
                />
                <span>
                  <span className="block font-bold">{e.nome}</span>
                  <span className="block text-sm text-pedra-600">{e.descricao}</span>
                  <span className="mt-1 block font-mono text-xs text-pedra-500">
                    {e.campos} campos
                    {e.depende_de.length > 0 ? ` · depende de ${e.depende_de.join(", ")}` : ""}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <Botao
        variante="primario"
        className="w-fit"
        disabled={escolhidos.size === 0}
        carregando={importando}
        onClick={() => void importar()}
      >
        Importar {escolhidos.size > 0 ? `(${escolhidos.size})` : ""}
      </Botao>
    </div>
  );
}
