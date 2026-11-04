import type { Definicao, ResultadoCalculado } from "../../api/cliente";
import type { Coordenadas, Valores } from "./tipos";

type Dados = Record<string, unknown>;

/**
 * Converte o que a API guardou no registro para o que o `FormRenderer` edita. Só os campos de
 * entrada; vazio (`null`) vira ausente, e um valor de tipo inesperado é ignorado em vez de quebrar.
 */
export function valoresDoRegistro(definicao: Definicao, dados: Dados): Valores {
  const valores: Valores = {};
  for (const campo of definicao.campos) {
    const valor = dados[campo.id];
    switch (campo.tipo) {
      case "texto":
      case "numero":
      case "data":
      case "selecao":
        if (typeof valor === "string") valores[campo.id] = valor;
        break;
      case "sim_nao":
        if (typeof valor === "boolean") valores[campo.id] = valor;
        break;
      case "referencia":
        if (typeof valor === "number") valores[campo.id] = valor;
        break;
      case "localizacao":
        if (ehCoordenadas(valor)) valores[campo.id] = valor;
        break;
      default:
        break; // calculado e seção não são entrada
    }
  }
  return valores;
}

/** O `{valor, erro}` gravado de cada campo calculado do registro. */
export function calculadosDoRegistro(
  definicao: Definicao,
  dados: Dados,
): Record<string, ResultadoCalculado> {
  const calculados: Record<string, ResultadoCalculado> = {};
  for (const campo of definicao.campos) {
    const valor = dados[campo.id];
    if (campo.tipo === "calculado" && ehResultado(valor)) calculados[campo.id] = valor;
  }
  return calculados;
}

function ehCoordenadas(valor: unknown): valor is Coordenadas {
  return (
    typeof valor === "object" &&
    valor !== null &&
    typeof (valor as Coordenadas).latitude === "string" &&
    typeof (valor as Coordenadas).longitude === "string"
  );
}

function ehResultado(valor: unknown): valor is ResultadoCalculado {
  return typeof valor === "object" && valor !== null && "valor" in valor && "erro" in valor;
}
