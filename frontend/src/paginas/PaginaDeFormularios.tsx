import { useState } from "react";
import { useApi } from "../api/contexto";
import type { ResumoDeFormulario } from "../api/cliente";
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
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
