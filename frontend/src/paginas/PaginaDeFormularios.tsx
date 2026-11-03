import { useState, type FormEvent } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type ResumoDeFormulario } from "../api/cliente";
import type { Rota } from "../rotas";
import { Aviso, Botao, CampoDeTexto, Cartao, EstadoVazio, Icone, Selo } from "../ui";
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
    <section className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Formulários</h1>
          <p className="mt-0.5 text-sm text-pedra-600">
            Escolha um formulário para preencher, consultar ou editar.
          </p>
        </div>
        <Botao variante="primario" onClick={() => navegar({ nome: "novoFormulario" })}>
          <Icone nome="mais" />
          Novo formulário
        </Botao>
      </div>

      {aviso ? <Falha mensagem={aviso} /> : null}
      {copiado ? (
        <Aviso
          tom="sucesso"
          acoes={
            <Botao
              tamanho="pequeno"
              onClick={() => navegar({ nome: "editarFormulario", formularioId: copiado.id })}
            >
              Editar a cópia
            </Botao>
          }
        >
          «{copiado.nome}» foi criado. Os registros não foram copiados, só a definição atual.
        </Aviso>
      ) : null}
      {carga.situacao === "carregando" ? <Carregando /> : null}
      {carga.situacao === "erro" ? <Falha mensagem={carga.mensagem} /> : null}

      {carga.situacao === "pronto" && carga.dados.length === 0 ? (
        <EstadoVazio
          icone="registros"
          titulo="Nenhum formulário ainda"
          acao={
            <Botao variante="primario" onClick={() => navegar({ nome: "novoFormulario" })}>
              <Icone nome="mais" />
              Criar o primeiro no construtor
            </Botao>
          }
        >
          Um formulário é montado no construtor e depois preenchido quantas vezes for preciso.
        </EstadoVazio>
      ) : null}

      {carga.situacao === "pronto" && carga.dados.length > 0 ? (
        <Cartao>
          <ul className="divide-y divide-pedra-200">
            {carga.dados.map((formulario) => (
              <li key={formulario.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4">
                <div className="mr-auto flex min-w-0 items-center gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-controle bg-pedra-100 text-pedra-600">
                    <Icone nome="registros" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium">{formulario.nome}</p>
                    <p className="mt-0.5 text-sm text-pedra-500">
                      <Selo>v{formulario.versao_atual_numero}</Selo>
                      <span className="sr-only">versão {formulario.versao_atual_numero}</span>
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Botao
                    variante="primario"
                    tamanho="pequeno"
                    aria-label={`Novo registro em ${formulario.nome}`}
                    onClick={() => navegar({ nome: "novoRegistro", formularioId: formulario.id })}
                  >
                    Novo registro
                  </Botao>
                  <Botao
                    tamanho="pequeno"
                    aria-label={`Ver registros de ${formulario.nome}`}
                    onClick={() => navegar({ nome: "registros", formularioId: formulario.id })}
                  >
                    Registros
                  </Botao>
                  <Botao
                    variante="fantasma"
                    tamanho="pequeno"
                    aria-label={`Editar o formulário ${formulario.nome}`}
                    onClick={() =>
                      navegar({ nome: "editarFormulario", formularioId: formulario.id })
                    }
                  >
                    <Icone nome="editar" />
                    Editar
                  </Botao>
                  <Botao
                    variante="fantasma"
                    tamanho="pequeno"
                    aria-label={`Duplicar o formulário ${formulario.nome}`}
                    onClick={() => abrirDuplicacao(formulario)}
                  >
                    <Icone nome="copiar" />
                    Duplicar
                  </Botao>
                  {confirmando === formulario.id ? (
                    <Botao
                      variante="perigoSolido"
                      tamanho="pequeno"
                      onClick={() => void excluir(formulario)}
                    >
                      Confirmar exclusão de {formulario.nome}
                    </Botao>
                  ) : (
                    <Botao
                      variante="perigo"
                      tamanho="pequeno"
                      aria-label={`Excluir o formulário ${formulario.nome}`}
                      onClick={() => setConfirmando(formulario.id)}
                    >
                      <Icone nome="lixeira" />
                      Excluir
                    </Botao>
                  )}
                </div>
                {duplicando === formulario.id ? (
                  <form
                    className="flex basis-full flex-col gap-3 rounded-controle bg-pedra-100 p-4"
                    onSubmit={(evento) => void duplicar(evento, formulario)}
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
                      <Botao onClick={() => setDuplicando(null)}>Cancelar</Botao>
                    </div>
                  </form>
                ) : null}
              </li>
            ))}
          </ul>
        </Cartao>
      ) : null}
    </section>
  );
}
