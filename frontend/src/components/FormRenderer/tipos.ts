export interface Coordenadas {
  latitude: string;
  longitude: string;
}

/**
 * O valor de um campo de entrada, no formato que a API aceita: número e data como texto
 * (`"25.5"`, `"2026-11-01"`), sim/não como booleano, localização como par de textos, foto como
 * lista de `id`s de anexo e referência como o `id` do registro de origem.
 */
export type ValorDoCampo = string | boolean | number | number[] | Coordenadas | null | undefined;

/** Valores dos campos de entrada, por `id`. Campo calculado e seção nunca entram aqui. */
export type Valores = Record<string, ValorDoCampo>;

/** Mensagens de erro por `id` de campo (vêm do 422 da API). */
export type ErrosPorCampo = Record<string, string[]>;
