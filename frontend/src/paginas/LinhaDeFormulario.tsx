import { useDraggable } from "@dnd-kit/core";
import { useState, type FormEvent } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type ResumoDeFormulario } from "../api/cliente";
import type { Rota } from "../rotas";
import { ComPermissao } from "../shell/permissoes";
import { Botao, CampoDeTexto, Icone, Selecao, Selo } from "../ui";
import { mensagemDe, mensagemDetalhada } from "./Estado";
import { idDeArraste, type Destino } from "./pastas";

interface Props {
  formulario: ResumoDeFormulario;
  /** Pastas para onde este formulário pode ir (sem a que ele já ocupa). */
  destinos: Destino[];
  /** Onde ele está ("Obras / Fundação"); só quando a lista mistura pastas, como na busca. */
  caminho?: string;
  navegar: (rota: Rota) => void;
  /** Algo mudou no servidor (mover, duplicar, excluir): recarregar a lista. */
  aoAlterar: () => void;
  aoCopiado: (copia: { id: number; nome: string }) => void;
  aoFalhar: (mensagem: string) => void;
}

/** Um formulário na lista: abrir, editar, duplicar, mover (por menu ou arrastando) e excluir. */
export function LinhaDeFormulario({
  formulario,
  destinos,
  caminho,
  navegar,
  aoAlterar,
  aoCopiado,
  aoFalhar,
}: Props) {
  const cliente = useApi();
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: idDeArraste(formulario.id),
  });
  const [confirmando, setConfirmando] = useState(false);
  const [duplicando, setDuplicando] = useState(false);
  const [nomeDaCopia, setNomeDaCopia] = useState("");
  const [errosDaCopia, setErrosDaCopia] = useState<string[]>([]);
  const [copiando, setCopiando] = useState(false);

  async function duplicar(evento: FormEvent) {
    evento.preventDefault();
    setCopiando(true);
    try {
      // Sem nome digitado, o servidor escolhe um livre ("X (cópia)", "X (cópia 2)"…).
      const nome = nomeDaCopia.trim();
      const criada = await cliente.duplicarFormulario(
        formulario.id,
        nome === "" ? undefined : nome,
      );
      setDuplicando(false);
      aoCopiado({ id: criada.id, nome: criada.nome });
      aoAlterar();
    } catch (erro) {
      // 422: nome repetido vem no campo `nome`; qualquer outra falha vira mensagem geral.
      const doNome = erro instanceof ErroDaApi ? erro.mensagensPorCampo()["nome"] : undefined;
      setErrosDaCopia(doNome ?? [mensagemDe(erro)]);
    } finally {
      setCopiando(false);
    }
  }

  async function excluir() {
    try {
      await cliente.excluirFormulario(formulario.id);
      aoAlterar();
    } catch (erro) {
      // 409: o servidor explica o vínculo (dependente ou registros) em português.
      aoFalhar(mensagemDe(erro));
    } finally {
      setConfirmando(false);
    }
  }

  async function mover(valor: string) {
    if (valor === "") return;
    try {
      await cliente.moverFormulario(formulario.id, valor === "raiz" ? null : Number(valor));
      aoAlterar();
    } catch (erro) {
      aoFalhar(mensagemDetalhada(erro));
    }
  }

  /*
   * Duas colunas fixas (identificação e ações) em contêiner largo, então todas as linhas alinham
   * igual, qualquer que seja o tamanho do nome. Em contêiner estreito, as ações descem para uma
   * segunda linha, sempre alinhadas ao nome; e só com espaço de sobra os botões de ícone ganham
   * texto. A decisão é pela largura da lista, não da janela.
   */
  return (
    <li
      ref={setNodeRef}
      className={`@container p-4 transition-opacity duration-(--duracao-rapida) ${isDragging ? "opacity-40" : ""}`}
    >
      <div className="grid grid-cols-[1.75rem_minmax(0,1fr)] items-center gap-x-3 gap-y-3 @3xl:grid-cols-[1.75rem_minmax(0,1fr)_auto]">
        <button
          type="button"
          aria-label={`Arrastar o formulário ${formulario.nome}`}
          className="grid size-7 shrink-0 cursor-grab touch-none place-items-center rounded-controle text-pedra-400 hover:bg-pedra-100 hover:text-pedra-700 active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <Icone nome="alca" />
        </button>
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-controle bg-pedra-100 text-pedra-600">
            <Icone nome="registros" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium">{formulario.nome}</p>
            <p className="mt-0.5 flex min-w-0 items-center gap-2 text-sm text-pedra-500">
              <Selo>v{formulario.versao_atual_numero}</Selo>
              <span className="sr-only">versão {formulario.versao_atual_numero}</span>
              {caminho ? (
                <span className="flex min-w-0 items-center gap-1">
                  <Icone nome="pasta" tamanho={13} className="shrink-0" />
                  <span className="truncate">{caminho}</span>
                </span>
              ) : null}
            </p>
          </div>
        </div>
        <div className="col-start-2 flex flex-wrap items-center gap-1.5 @3xl:col-start-3">
          <ComPermissao permissao="registros:criar">
            <Botao
              variante="primario"
              tamanho="pequeno"
              aria-label={`Novo registro em ${formulario.nome}`}
              onClick={() => navegar({ nome: "novoRegistro", formularioId: formulario.id })}
            >
              Novo registro
            </Botao>
          </ComPermissao>
          <Botao
            tamanho="pequeno"
            aria-label={`Ver registros de ${formulario.nome}`}
            onClick={() => navegar({ nome: "registros", formularioId: formulario.id })}
          >
            Registros
          </Botao>
          <span aria-hidden="true" className="mx-1 h-4 w-px bg-pedra-200" />
          <ComPermissao permissao="formularios:publicar">
            <Botao
              variante="fantasma"
              tamanho="pequeno"
              aria-label={`Editar o formulário ${formulario.nome}`}
              title="Editar"
              onClick={() => navegar({ nome: "editarFormulario", formularioId: formulario.id })}
            >
              <Icone nome="editar" />
              <span className="hidden @4xl:inline">Editar</span>
            </Botao>
          </ComPermissao>
          <ComPermissao permissao="formularios:publicar">
            <Botao
              variante="fantasma"
              tamanho="pequeno"
              aria-label={`Duplicar o formulário ${formulario.nome}`}
              title="Duplicar"
              onClick={() => {
                setDuplicando(true);
                setNomeDaCopia("");
                setErrosDaCopia([]);
              }}
            >
              <Icone nome="copiar" />
              <span className="hidden @4xl:inline">Duplicar</span>
            </Botao>
          </ComPermissao>
          <ComPermissao permissao="formularios:organizar">
            <Selecao
              rotulo={`Mover ${formulario.nome} para`}
              ocultarRotulo
              className="w-36"
              value=""
              onChange={(evento) => void mover(evento.target.value)}
            >
              <option value="">Mover para…</option>
              {formulario.pasta_id != null ? <option value="raiz">Raiz (sem pasta)</option> : null}
              {destinos.map((destino) => (
                <option key={destino.id} value={destino.id}>
                  {destino.rotulo}
                </option>
              ))}
            </Selecao>
          </ComPermissao>
          <ComPermissao permissao="formularios:excluir">
            {confirmando ? (
              <Botao variante="perigoSolido" tamanho="pequeno" onClick={() => void excluir()}>
                Confirmar exclusão de {formulario.nome}
              </Botao>
            ) : (
              <Botao
                variante="perigo"
                tamanho="pequeno"
                aria-label={`Excluir o formulário ${formulario.nome}`}
                title="Excluir"
                onClick={() => setConfirmando(true)}
              >
                <Icone nome="lixeira" />
                <span className="hidden @4xl:inline">Excluir</span>
              </Botao>
            )}
          </ComPermissao>
        </div>
      </div>
      {duplicando ? (
        <form
          className="mt-3 flex flex-col gap-3 rounded-controle bg-pedra-100 p-4"
          onSubmit={(evento) => void duplicar(evento)}
        >
          <CampoDeTexto
            autoFocus
            rotulo="Nome da cópia"
            value={nomeDaCopia}
            placeholder={`Em branco: «${formulario.nome} (cópia)»`}
            erros={errosDaCopia}
            dica="A cópia leva a definição atual na versão 1, na mesma pasta. Os registros não são copiados."
            onChange={(evento) => {
              setNomeDaCopia(evento.target.value);
              setErrosDaCopia([]);
            }}
          />
          <div className="flex gap-2">
            <Botao type="submit" variante="primario" carregando={copiando}>
              Criar cópia
            </Botao>
            <Botao onClick={() => setDuplicando(false)}>Cancelar</Botao>
          </div>
        </form>
      ) : null}
    </li>
  );
}
