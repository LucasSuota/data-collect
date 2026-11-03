import { useState, type FormEvent } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type ResumoDeFormulario } from "../api/cliente";
import type { Rota } from "../rotas";
import { Carregando, Falha, mensagemDe, useCarga } from "./Estado";

interface Props {
  navegar: (rota: Rota) => void;
}

/** A tela inicial: escolher um formulário para preencher, consultar, editar ou excluir. */
export function PaginaDeFormularios({ navegar }: Props) {
  const cliente = useApi();
  const [versao, setVersao] = useState(0);
  const carga = useCarga(() => cliente.listarFormularios(), [cliente, versao]);
  const [aviso, setAviso] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState<number | null>(null);
  const [duplicando, setDuplicando] = useState<number | null>(null);
  const [nomeDaCopia, setNomeDaCopia] = useState("");
  const [errosDaCopia, setErrosDaCopia] = useState<string[]>([]);
  const [copiando, setCopiando] = useState(false);
  const [copiado, setCopiado] = useState<{ id: number; nome: string } | null>(null);

  function abrirDuplicacao(formulario: ResumoDeFormulario) {
    setDuplicando(formulario.id);
    setNomeDaCopia("");
    setErrosDaCopia([]);
  }

  async function duplicar(evento: FormEvent, formulario: ResumoDeFormulario) {
    evento.preventDefault();
    setCopiando(true);
    try {
      // Sem nome digitado, o servidor escolhe um livre ("X (cópia)", "X (cópia 2)"…).
      const nome = nomeDaCopia.trim();
      const criada = await cliente.duplicarFormulario(
        formulario.id,
        nome === "" ? undefined : nome,
      );
      setDuplicando(null);
      setCopiado({ id: criada.id, nome: criada.nome });
      setAviso(null);
      setVersao((v) => v + 1);
    } catch (erro) {
      // 422: nome repetido vem no campo `nome`; qualquer outra falha vira mensagem geral.
      const doNome = erro instanceof ErroDaApi ? erro.mensagensPorCampo()["nome"] : undefined;
      if (doNome) setErrosDaCopia(doNome);
      else setErrosDaCopia([mensagemDe(erro)]);
    } finally {
      setCopiando(false);
    }
  }

  async function excluir(formulario: ResumoDeFormulario) {
    try {
      await cliente.excluirFormulario(formulario.id);
      setAviso(null);
      setConfirmando(null);
      setVersao((v) => v + 1);
    } catch (erro) {
      // 409: o servidor explica o vínculo (dependente ou registros) em português.
      setAviso(mensagemDe(erro));
      setConfirmando(null);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Formulários</h1>
        <button
          type="button"
          className="rounded bg-slate-900 px-3 py-1.5 text-white"
          onClick={() => navegar({ nome: "novoFormulario" })}
        >
          Novo formulário
        </button>
      </div>

      {aviso ? <Falha mensagem={aviso} /> : null}
      {copiado ? (
        <p
          role="status"
          className="flex flex-wrap items-center gap-3 rounded border border-emerald-300 bg-emerald-50 p-3 text-emerald-900"
        >
          <span>
            «{copiado.nome}» foi criado. Os registros não foram copiados, só a definição atual.
          </span>
          <button
            type="button"
            className="rounded border border-emerald-400 px-2 py-1 text-sm"
            onClick={() => navegar({ nome: "editarFormulario", formularioId: copiado.id })}
          >
            Editar a cópia
          </button>
        </p>
      ) : null}
      {carga.situacao === "carregando" ? <Carregando /> : null}
      {carga.situacao === "erro" ? <Falha mensagem={carga.mensagem} /> : null}

      {carga.situacao === "pronto" && carga.dados.length === 0 ? (
        <p className="text-slate-600">Nenhum formulário ainda. Crie o primeiro no construtor.</p>
      ) : null}

      {carga.situacao === "pronto" && carga.dados.length > 0 ? (
        <ul className="divide-y divide-slate-200 rounded border border-slate-200">
          {carga.dados.map((formulario) => (
            <li key={formulario.id} className="flex flex-wrap items-center gap-3 p-3">
              <div className="mr-auto">
                <p className="font-medium">{formulario.nome}</p>
                <p className="text-sm text-slate-500">versão {formulario.versao_atual_numero}</p>
              </div>
              <button
                type="button"
                className="rounded bg-slate-900 px-2 py-1 text-sm text-white"
                aria-label={`Novo registro em ${formulario.nome}`}
                onClick={() => navegar({ nome: "novoRegistro", formularioId: formulario.id })}
              >
                Novo registro
              </button>
              <button
                type="button"
                className="rounded border border-slate-300 px-2 py-1 text-sm"
                aria-label={`Ver registros de ${formulario.nome}`}
                onClick={() => navegar({ nome: "registros", formularioId: formulario.id })}
              >
                Registros
              </button>
              <button
                type="button"
                className="rounded border border-slate-300 px-2 py-1 text-sm"
                aria-label={`Editar o formulário ${formulario.nome}`}
                onClick={() => navegar({ nome: "editarFormulario", formularioId: formulario.id })}
              >
                Editar
              </button>
              <button
                type="button"
                className="rounded border border-slate-300 px-2 py-1 text-sm"
                aria-label={`Duplicar o formulário ${formulario.nome}`}
                onClick={() => abrirDuplicacao(formulario)}
              >
                Duplicar
              </button>
              {confirmando === formulario.id ? (
                <button
                  type="button"
                  className="rounded bg-red-600 px-2 py-1 text-sm text-white"
                  onClick={() => void excluir(formulario)}
                >
                  Confirmar exclusão de {formulario.nome}
                </button>
              ) : (
                <button
                  type="button"
                  className="rounded border border-red-300 px-2 py-1 text-sm text-red-700"
                  aria-label={`Excluir o formulário ${formulario.nome}`}
                  onClick={() => setConfirmando(formulario.id)}
                >
                  Excluir
                </button>
              )}
              {duplicando === formulario.id ? (
                <form
                  className="flex basis-full flex-col gap-2 rounded bg-slate-50 p-3"
                  onSubmit={(evento) => void duplicar(evento, formulario)}
                >
                  <label className="flex flex-col gap-1 text-sm">
                    Nome da cópia
                    <input
                      autoFocus
                      className="rounded border border-slate-300 px-2 py-1"
                      value={nomeDaCopia}
                      placeholder={`Em branco: «${formulario.nome} (cópia)»`}
                      aria-invalid={errosDaCopia.length > 0}
                      aria-describedby={errosDaCopia.length > 0 ? "erro-da-copia" : undefined}
                      onChange={(evento) => {
                        setNomeDaCopia(evento.target.value);
                        setErrosDaCopia([]);
                      }}
                    />
                  </label>
                  {errosDaCopia.length > 0 ? (
                    <p id="erro-da-copia" className="text-sm text-red-700">
                      {errosDaCopia.join(" ")}
                    </p>
                  ) : null}
                  <p className="text-sm text-slate-500">
                    A cópia leva a definição atual na versão 1, na mesma pasta. Os registros não são
                    copiados.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={copiando}
                      className="rounded bg-slate-900 px-2 py-1 text-sm text-white disabled:opacity-60"
                    >
                      Criar cópia
                    </button>
                    <button
                      type="button"
                      className="rounded border border-slate-300 px-2 py-1 text-sm"
                      onClick={() => setDuplicando(null)}
                    >
                      Cancelar
                    </button>
                  </div>
                </form>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
