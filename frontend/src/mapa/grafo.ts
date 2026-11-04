import type { Definicao } from "../api/cliente";
import type { Celula } from "../lib/celulas";
import { dataBrasileira } from "../lib/formatacao";

/**
 * O grafo de dependências, em dois níveis: de *formulários* (quem aponta para quem, pela
 * definição) e de *registros* (qual registro aponta para qual, pelos valores guardados). Só
 * organiza o que a API já devolveu; ciclo é rejeitado pelo servidor ao publicar (§2.7).
 */
export interface FormularioDoMapa {
  id: number;
  nome: string;
  versao: number | null;
  /** A definição da versão atual: é ela que diz as referências e os campos compartilhados. */
  definicao: Definicao;
  totalDeRegistros: number;
}

export interface RegistroDoMapa {
  id: number;
  formularioId: number;
  criadoEm: string;
  celulas: Celula[];
  referencias: { campoId: string; rotulo: string; destinoId: number }[];
}

export type TipoDeLinha = "entrada" | "compartilhado" | "conformidade" | "campo";

export interface LinhaDoNo {
  chave: string;
  tipo: TipoDeLinha;
  rotulo: string;
  valor: string;
  unidade: string | null;
  conforme: boolean | null;
}

export interface NoDoGrafo {
  id: string;
  tipo: "formulario" | "registro";
  formularioId: number;
  registroId: number | null;
  titulo: string;
  subtitulo: string;
  linhas: LinhaDoNo[];
  /** Quantas linhas não couberam no cartão. */
  linhasOcultas: number;
}

export interface Aresta {
  /** `<de>><para>`: um por par de nós, mesmo que dois campos liguem o mesmo par. */
  id: string;
  de: string;
  para: string;
  rotulo: string;
}

export interface Grafo {
  nos: NoDoGrafo[];
  arestas: Aresta[];
}

export interface OpcoesDoGrafo {
  /** Mostrar também o que não tem vínculo nenhum (padrão da tela: não). */
  incluirIsolados: boolean;
}

export const MAXIMO_DE_LINHAS = 6;

const chaveDoNome = (nome: string) => nome.trim().toLowerCase();

export const idDoNoDeFormulario = (id: number) => `formulario-${id}`;
export const idDoNoDeRegistro = (id: number) => `registro-${id}`;

/** Une rótulos quando dois campos ligam o mesmo par de nós. */
function somarAresta(arestas: Map<string, Aresta>, de: string, para: string, rotulo: string) {
  const id = `${de}>${para}`;
  const existente = arestas.get(id);
  if (!existente) arestas.set(id, { id, de, para, rotulo });
  else if (!existente.rotulo.split(" · ").includes(rotulo)) existente.rotulo += ` · ${rotulo}`;
}

function limitar(linhas: LinhaDoNo[]): { linhas: LinhaDoNo[]; linhasOcultas: number } {
  return {
    linhas: linhas.slice(0, MAXIMO_DE_LINHAS),
    linhasOcultas: Math.max(0, linhas.length - MAXIMO_DE_LINHAS),
  };
}

function semIsolados(grafo: Grafo, { incluirIsolados }: OpcoesDoGrafo): Grafo {
  if (incluirIsolados || grafo.arestas.length === 0) return grafo;
  const ligados = new Set(grafo.arestas.flatMap((a) => [a.de, a.para]));
  return { nos: grafo.nos.filter((no) => ligados.has(no.id)), arestas: grafo.arestas };
}

export function montarGrafoDeFormularios(
  formularios: FormularioDoMapa[],
  opcoes: OpcoesDoGrafo,
): Grafo {
  const porNome = new Map(formularios.map((f) => [chaveDoNome(f.nome), f]));
  const arestas = new Map<string, Aresta>();

  const nos = formularios.map((formulario): NoDoGrafo => {
    const entradas: LinhaDoNo[] = [];
    for (const campo of formulario.definicao.campos) {
      if (campo.tipo !== "referencia") continue;
      const origem = porNome.get(chaveDoNome(campo.formulario ?? ""));
      if (!origem) continue;
      entradas.push({
        chave: campo.id,
        tipo: "entrada",
        rotulo: campo.rotulo,
        valor: origem.nome,
        unidade: null,
        conforme: null,
      });
      somarAresta(
        arestas,
        idDoNoDeFormulario(origem.id),
        idDoNoDeFormulario(formulario.id),
        campo.rotulo,
      );
    }
    const liberados = formulario.definicao.campos
      .filter((campo) => campo.compartilhado === true)
      .map((campo): LinhaDoNo => ({
        chave: campo.id,
        tipo: "compartilhado",
        rotulo: campo.rotulo,
        valor: campo.unidade ?? "",
        unidade: campo.unidade ?? null,
        conforme: null,
      }));
    const quantidade = formulario.totalDeRegistros;
    return {
      id: idDoNoDeFormulario(formulario.id),
      tipo: "formulario",
      formularioId: formulario.id,
      registroId: null,
      titulo: formulario.nome,
      subtitulo: `v${formulario.versao ?? "?"} · ${quantidade} registro${quantidade === 1 ? "" : "s"}`,
      ...limitar([...entradas, ...liberados]),
    };
  });

  return semIsolados({ nos, arestas: [...arestas.values()] }, opcoes);
}

export function montarGrafoDeRegistros(
  formularios: FormularioDoMapa[],
  registros: RegistroDoMapa[],
  opcoes: OpcoesDoGrafo,
): Grafo {
  const formularioPorId = new Map(formularios.map((f) => [f.id, f]));
  const carregados = new Set(registros.map((r) => r.id));
  const arestas = new Map<string, Aresta>();

  const nos = registros.map((registro): NoDoGrafo => {
    const formulario = formularioPorId.get(registro.formularioId);
    const referenciados = new Set(registro.referencias.map((r) => r.campoId));
    for (const referencia of registro.referencias) {
      if (!carregados.has(referencia.destinoId)) continue;
      somarAresta(
        arestas,
        idDoNoDeRegistro(referencia.destinoId),
        idDoNoDeRegistro(registro.id),
        referencia.rotulo,
      );
    }
    // Quem o registro aponta já aparece como aresta: repetir o "#12" como linha só ocupa espaço.
    const linhas = registro.celulas
      .filter((celula) => !referenciados.has(celula.id))
      .map((celula): LinhaDoNo => ({
        chave: celula.id,
        tipo: celula.compartilhado
          ? "compartilhado"
          : celula.conforme !== null
            ? "conformidade"
            : "campo",
        rotulo: celula.rotulo,
        valor: celula.texto,
        unidade: celula.unidade,
        conforme: celula.conforme,
      }));
    const ordem: Record<TipoDeLinha, number> = {
      compartilhado: 0,
      conformidade: 1,
      campo: 2,
      entrada: 3,
    };
    linhas.sort((a, b) => ordem[a.tipo] - ordem[b.tipo]);
    return {
      id: idDoNoDeRegistro(registro.id),
      tipo: "registro",
      formularioId: registro.formularioId,
      registroId: registro.id,
      titulo: formulario?.nome ?? `Formulário ${registro.formularioId}`,
      subtitulo: `#${registro.id} · ${dataBrasileira(registro.criadoEm.slice(0, 10))}`,
      ...limitar(linhas),
    };
  });

  return semIsolados({ nos, arestas: [...arestas.values()] }, opcoes);
}

export interface Cadeia {
  nos: Set<string>;
  arestas: Set<string>;
}

/** Tudo que origina `noId` e tudo que depende dele (transitivamente), sem os "irmãos". */
export function cadeiaDe(grafo: Grafo, noId: string): Cadeia {
  const cadeia: Cadeia = { nos: new Set(), arestas: new Set() };
  if (!grafo.nos.some((no) => no.id === noId)) return cadeia;
  cadeia.nos.add(noId);

  const percorrer = (sentido: "para-origem" | "para-dependente") => {
    const fila = [noId];
    const visitados = new Set(fila);
    for (let atual = fila.shift(); atual !== undefined; atual = fila.shift()) {
      for (const aresta of grafo.arestas) {
        const vizinho =
          sentido === "para-origem"
            ? aresta.para === atual
              ? aresta.de
              : null
            : aresta.de === atual
              ? aresta.para
              : null;
        if (vizinho === null) continue;
        cadeia.arestas.add(aresta.id);
        cadeia.nos.add(vizinho);
        if (!visitados.has(vizinho)) {
          visitados.add(vizinho);
          fila.push(vizinho);
        }
      }
    }
  };
  percorrer("para-origem");
  percorrer("para-dependente");
  return cadeia;
}
