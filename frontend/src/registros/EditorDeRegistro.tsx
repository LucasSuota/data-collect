import { useContext, useEffect, useState } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type Historico, type Registro } from "../api/cliente";
import { ContextoDaSessao } from "../auth/sessao";
import { FormRenderer } from "../components/FormRenderer";
import type { ErrosPorCampo, Valores } from "../components/FormRenderer";
import {
  calculadosDoRegistro,
  valoresDoRegistro,
} from "../components/FormRenderer/valoresDoRegistro";
import { Falha, mensagemDe } from "../paginas/Estado";
import { Aviso, Botao, Cartao, Icone } from "../ui";
import { Bloqueado } from "../shell/permissoes";
import type { RegistroCarregado } from "./useRegistroCarregado";

interface Props {
  carregado: RegistroCarregado;
  aoSalvar: (registro: Registro) => void;
  aoCancelar: () => void;
  /** Sem isto o botão de excluir não aparece (a gaveta de edição não exclui). */
  aoExcluir?: () => void;
  /** Título e largura de página; na gaveta, o título é da própria gaveta. */
  comoPagina?: boolean;
}

/** O formulário de um registro novo ou existente, com validação e cálculo do servidor. */
export function EditorDeRegistro({
  carregado,
  aoSalvar,
  aoCancelar,
  aoExcluir,
  comoPagina = false,
}: Props) {
  const cliente = useApi();
  // Sem sessão (componente isolado nos testes) tudo fica liberado: a conveniência da tela nunca
  // substitui o servidor, que confere a permissão em toda requisição (AGENTS.md §3.3).
  const sessao = useContext(ContextoDaSessao);
  const { registro, definicao } = carregado;
  const pode = (permissao: string) => sessao?.pode(permissao) ?? true;
  const podeEditar =
    registro === null ||
    pode("registros:editar_todos") ||
    (pode("registros:editar_proprios") &&
      (sessao === null || registro.criado_por?.id === sessao.eu.pessoa.id));
  const [conflito, setConflito] = useState<string | null>(null);
  const [valores, setValores] = useState<Valores>(() =>
    registro ? valoresDoRegistro(definicao, registro.dados) : {},
  );
  const [erros, setErros] = useState<ErrosPorCampo>({});
  const [falhaGeral, setFalhaGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [confirmandoExclusao, setConfirmandoExclusao] = useState(false);

  const idsDosCampos = new Set(definicao.campos.map((campo) => campo.id));
  const errosSemCampo = Object.entries(erros).filter(([campo]) => !idsDosCampos.has(campo));

  function tratar(erro: unknown) {
    if (
      erro instanceof ErroDaApi &&
      erro.status === 409 &&
      erro.codigo === "revisao_desatualizada"
    ) {
      // Outra pessoa salvou antes: a mensagem do servidor diz quem e quando.
      setConflito(erro.message);
      setErros({});
      setFalhaGeral(null);
    } else if (erro instanceof ErroDaApi && erro.status === 422) {
      setErros(erro.mensagensPorCampo());
      setFalhaGeral(erro.erros.length === 0 ? erro.message : null);
    } else {
      setErros({});
      setFalhaGeral(mensagemDe(erro));
    }
  }

  async function salvar(evento: React.FormEvent) {
    evento.preventDefault();
    // A gaveta é um portal: sem isto o envio subiria pela árvore do React até o formulário de baixo.
    evento.stopPropagation();
    setSalvando(true);
    setErros({});
    setFalhaGeral(null);
    setConflito(null);
    try {
      const salvo = registro
        ? await cliente.atualizarRegistro(registro.id, valores, registro.revisao)
        : await cliente.criarRegistro(carregado.formularioId, carregado.versaoId, valores);
      aoSalvar(salvo);
    } catch (erro) {
      tratar(erro);
    } finally {
      setSalvando(false);
    }
  }

  async function excluir() {
    if (!registro) return;
    try {
      await cliente.excluirRegistro(registro.id);
      aoExcluir?.();
    } catch (erro) {
      // 409: outro registro o referencia; a mensagem do servidor diz quais.
      setFalhaGeral(mensagemDe(erro));
      setConfirmandoExclusao(false);
    }
  }

  return (
    <form
      onSubmit={(e) => void salvar(e)}
      className={`flex flex-col gap-5 ${comoPagina ? "max-w-2xl" : ""}`}
      noValidate
    >
      {comoPagina ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Voltar"
            onClick={aoCancelar}
            className="grid size-11 place-items-center rounded-controle hover:bg-pedra-100"
          >
            <Icone nome="voltar" tamanho={20} />
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-extrabold">{carregado.nomeDoFormulario}</h1>
            <p className="text-sm text-pedra-600">
              {registro ? `Registro #${registro.id}` : "Novo registro"} · versão{" "}
              {carregado.numeroDaVersao}
            </p>
          </div>
        </div>
      ) : null}

      {conflito ? (
        <Aviso
          tom="erro"
          acoes={
            <Botao tamanho="pequeno" onClick={() => window.location.reload()}>
              Recarregar registro
            </Botao>
          }
        >
          {conflito} Recarregue para ver a versão mais recente antes de salvar.
        </Aviso>
      ) : null}
      {!podeEditar ? (
        <Aviso tom="info">
          Seu cargo só consulta este registro: ele só deixa editar os que você mesmo criou.
        </Aviso>
      ) : null}
      {falhaGeral ? <Falha mensagem={falhaGeral} /> : null}
      {errosSemCampo.length > 0 ? (
        <Falha
          mensagem={errosSemCampo
            .map(([campo, mensagens]) => `${campo}: ${mensagens.join(" ")}`)
            .join(" · ")}
        />
      ) : null}

      <Cartao className="p-6">
        <FormRenderer
          definicao={definicao}
          valores={valores}
          aoMudar={setValores}
          erros={erros}
          calculadosSalvos={registro ? calculadosDoRegistro(definicao, registro.dados) : undefined}
          somenteLeitura={!podeEditar}
        />
      </Cartao>

      {registro && pode("historico:ver") ? <HistoricoDoRegistro registroId={registro.id} /> : null}

      {/* Barra de salvar fixa no celular, ao alcance do polegar (AGENTS.md §2.17). */}
      <div
        className={
          comoPagina
            ? "fixed inset-x-0 bottom-0 z-30 flex gap-2 border-t border-pedra-200 bg-superficie p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:static sm:z-auto sm:border-0 sm:bg-transparent sm:p-0"
            : "flex gap-2"
        }
      >
        <Botao onClick={aoCancelar}>{podeEditar ? "Cancelar" : "Voltar"}</Botao>
        {podeEditar ? (
          <Botao
            type="submit"
            variante="primario"
            className="flex-1 sm:flex-none"
            carregando={salvando}
          >
            {salvando ? "Salvando…" : "Salvar registro"}
          </Botao>
        ) : null}
        {registro && aoExcluir && !pode("registros:excluir") ? (
          <span className="ml-auto hidden sm:block">
            <Bloqueado permissao="registros:excluir">Excluir registro</Bloqueado>
          </span>
        ) : null}
        {registro && aoExcluir && pode("registros:excluir") ? (
          confirmandoExclusao ? (
            <Botao variante="perigoSolido" className="ml-auto" onClick={() => void excluir()}>
              Confirmar exclusão
            </Botao>
          ) : (
            <Botao
              variante="perigo"
              className="ml-auto"
              onClick={() => setConfirmandoExclusao(true)}
            >
              <Icone nome="lixeira" />
              Excluir registro
            </Botao>
          )
        ) : null}
      </div>
    </form>
  );
}

/** Quem alterou o quê e quando (`historico:ver`); só carrega quando a pessoa abre. */
function HistoricoDoRegistro({ registroId }: { registroId: number }) {
  const cliente = useApi();
  const [aberto, setAberto] = useState(false);
  const [itens, setItens] = useState<Historico[] | null>(null);

  useEffect(() => {
    if (!aberto || itens !== null) return;
    let ativo = true;
    void cliente.historicoDoRegistro(registroId).then(
      (h) => ativo && setItens(h),
      () => ativo && setItens([]),
    );
    return () => {
      ativo = false;
    };
  }, [aberto, itens, cliente, registroId]);

  return (
    <details
      onToggle={(e) => setAberto(e.currentTarget.open)}
      className="rounded-cartao border border-pedra-200 bg-superficie px-4 py-2"
    >
      <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold">
        <Icone nome="historico" /> Histórico de alterações
      </summary>
      {itens === null ? (
        <p className="py-2 text-sm text-pedra-600">Carregando…</p>
      ) : itens.length === 0 ? (
        <p className="py-2 text-sm text-pedra-600">Nenhuma alteração registrada.</p>
      ) : (
        <ul className="flex flex-col gap-1 py-2 text-sm">
          {itens.map((h) => (
            <li key={h.id}>
              <span className="font-medium">{h.pessoa ?? "Pessoa removida"}</span> · {h.acao} ·{" "}
              <span className="text-pedra-600">{new Date(h.quando).toLocaleString("pt-BR")}</span>
              {h.motivo ? <span className="block text-xs text-pedra-600">{h.motivo}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
