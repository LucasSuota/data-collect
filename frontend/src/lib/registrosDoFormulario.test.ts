import type { Esquemas, Registro } from "../api/cliente";
import { clienteFalso } from "../test/clienteFalso";
import { carregarRegistrosDoFormulario } from "./registrosDoFormulario";

type Coluna = Esquemas["ColunaSaida"];

const registro = (id: number, versao_id: number): Registro => ({
  id,
  formulario_id: 7,
  versao_id,
  dados: {},
  criado_em: "2026-11-02T10:00:00+00:00",
  atualizado_em: "2026-11-02T10:00:00+00:00",
});

const colunas: Coluna[] = [];

describe("carregarRegistrosDoFormulario", () => {
  it("junta os registros de todas as versões, do mais novo ao mais antigo", async () => {
    const listarRegistros = vi.fn(async (_id: number, p: { versaoId?: number } = {}) =>
      p.versaoId === 10
        ? { versao_id: 10, colunas, total: 2, itens: [registro(1, 10), registro(2, 10)] }
        : { versao_id: 11, colunas, total: 1, itens: [registro(3, 11)] },
    );
    const cliente = clienteFalso({
      listarVersoes: async () => [
        { id: 10, numero: 1, publicada_em: "x" },
        { id: 11, numero: 2, publicada_em: "x" },
      ],
      listarRegistros,
    });

    const lidos = await carregarRegistrosDoFormulario(cliente, 7, 50);

    expect(lidos.registros.map((r) => r.registro.id)).toEqual([3, 2, 1]);
    expect(lidos.total).toBe(3);
    expect(lidos.truncado).toBe(false);
    expect(listarRegistros).toHaveBeenCalledWith(7, { versaoId: 10, limite: 50 });
    expect(listarRegistros).toHaveBeenCalledWith(7, { versaoId: 11, limite: 50 });
  });

  it("cada registro leva as colunas da versão em que nasceu", async () => {
    const colunasV1 = [{ id: "a" }] as unknown as Coluna[];
    const cliente = clienteFalso({
      listarVersoes: async () => [{ id: 10, numero: 1, publicada_em: "x" }],
      listarRegistros: async () => ({
        versao_id: 10,
        colunas: colunasV1,
        total: 1,
        itens: [registro(1, 10)],
      }),
    });

    const lidos = await carregarRegistrosDoFormulario(cliente, 7, 50);

    expect(lidos.registros[0]?.colunas).toBe(colunasV1);
  });

  it("avisa que cortou quando a versão tem mais registros que o limite", async () => {
    const cliente = clienteFalso({
      listarVersoes: async () => [{ id: 10, numero: 1, publicada_em: "x" }],
      listarRegistros: async () => ({
        versao_id: 10,
        colunas,
        total: 120,
        itens: [registro(1, 10)],
      }),
    });

    const lidos = await carregarRegistrosDoFormulario(cliente, 7, 1);

    expect(lidos.truncado).toBe(true);
    expect(lidos.total).toBe(120);
  });
});
