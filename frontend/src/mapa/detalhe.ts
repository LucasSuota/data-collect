import type { DadosDoMapa } from "./carregarMapa";
import type { FormularioDoMapa, RegistroDoMapa } from "./grafo";

export type DetalheDoNo =
  | {
      tipo: "formulario";
      formulario: FormularioDoMapa;
      recebeDe: { campo: string; origem: FormularioDoMapa }[];
      usadoPor: FormularioDoMapa[];
    }
  | {
      tipo: "registro";
      registro: RegistroDoMapa;
      formulario: FormularioDoMapa;
      origens: { rotulo: string; registro: RegistroDoMapa }[];
      dependentes: { rotulo: string; registro: RegistroDoMapa }[];
    };

const chaveDoNome = (nome: string) => nome.trim().toLowerCase();

/** Tudo que o inspetor mostra de um nó: só os vizinhos diretos (o mapa já mostra a cadeia). */
export function detalheDoNo(dados: DadosDoMapa, noId: string): DetalheDoNo | null {
  const formularioPorId = new Map(dados.formularios.map((f) => [f.id, f]));
  const formularioPorNome = new Map(dados.formularios.map((f) => [chaveDoNome(f.nome), f]));
  const [tipo, texto] = noId.split("-");
  const id = Number(texto);

  if (tipo === "formulario") {
    const formulario = formularioPorId.get(id);
    if (!formulario) return null;
    const recebeDe = formulario.definicao.campos.flatMap((campo) => {
      const origem =
        campo.tipo === "referencia"
          ? formularioPorNome.get(chaveDoNome(campo.formulario ?? ""))
          : undefined;
      return origem ? [{ campo: campo.rotulo, origem }] : [];
    });
    const usadoPor = dados.formularios.filter((outro) =>
      outro.definicao.campos.some(
        (campo) =>
          campo.tipo === "referencia" &&
          chaveDoNome(campo.formulario ?? "") === chaveDoNome(formulario.nome),
      ),
    );
    return { tipo: "formulario", formulario, recebeDe, usadoPor };
  }

  if (tipo === "registro") {
    const registro = dados.registros.find((r) => r.id === id);
    const formulario = registro ? formularioPorId.get(registro.formularioId) : undefined;
    if (!registro || !formulario) return null;
    const porId = new Map(dados.registros.map((r) => [r.id, r]));
    const origens = registro.referencias.flatMap((referencia) => {
      const origem = porId.get(referencia.destinoId);
      return origem ? [{ rotulo: referencia.rotulo, registro: origem }] : [];
    });
    const dependentes = dados.registros.flatMap((outro) =>
      outro.referencias
        .filter((referencia) => referencia.destinoId === registro.id)
        .map((referencia) => ({ rotulo: referencia.rotulo, registro: outro })),
    );
    return { tipo: "registro", registro, formulario, origens, dependentes };
  }
  return null;
}
