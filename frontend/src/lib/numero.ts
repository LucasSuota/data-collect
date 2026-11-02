const NUMERO_DECIMAL = /^([+-]?)(\d*)(?:\.(\d*))?$/;

/**
 * Formata um número decimal guardado como string (`"25.4647"`) para exibição em português
 * (`"25,5"`), arredondando para `casas` (meio para cima, como o CSV do backend).
 *
 * É exibição: o valor guardado e devolvido pela API mantém a precisão total (AGENTS.md §7). Usa
 * `BigInt` em vez de `Number`, que perderia dígitos e arredondaria `0.35` para `0.3`.
 */
export function formatarNumero(valor: string, casas: number | null | undefined): string {
  const partes = NUMERO_DECIMAL.exec(valor.trim());
  const [, sinal = "", inteira = "", fracao = ""] = partes ?? [];
  if (!partes || (inteira === "" && fracao === "")) return valor;

  let digitos = (inteira === "" ? "0" : inteira) + fracao;
  let escala = fracao.length;

  if (casas != null && casas < escala) {
    const sobra = escala - casas;
    const mantidos = BigInt(digitos.slice(0, digitos.length - sobra) || "0");
    const primeiroDescartado = Number(digitos[digitos.length - sobra]);
    digitos = (mantidos + (primeiroDescartado >= 5 ? 1n : 0n)).toString();
    escala = casas;
  } else if (casas != null && casas > escala) {
    digitos += "0".repeat(casas - escala);
    escala = casas;
  }

  digitos = digitos.padStart(escala + 1, "0");
  const parteInteira = digitos.slice(0, digitos.length - escala);
  const parteFracionaria = digitos.slice(digitos.length - escala);
  const texto = escala > 0 ? `${parteInteira},${parteFracionaria}` : parteInteira;
  // -0,04 arredondado a uma casa é 0,0, não "-0,0".
  const eZero = /^[0,]+$/.test(texto);
  return `${sinal === "-" && !eZero ? "-" : ""}${texto}`;
}
