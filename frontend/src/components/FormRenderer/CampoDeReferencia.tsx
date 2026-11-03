import { useState } from "react";
import type { Campo as CampoDaDefinicao } from "../../api/cliente";
import { dataBrasileira } from "../../lib/formatacao";
import { combinaComBusca } from "../../paginas/filtros";
import { useGavetas } from "../../registros/contexto";
import { Botao, CampoDeBusca, Gaveta, Icone } from "../../ui";
import { Campo } from "./Campo";
import { escolherCelulas, ResumoDeRegistro } from "./ResumoDeRegistro";
import { useOrigemDaReferencia, type Origem } from "./useOrigemDaReferencia";

interface Props {
  campo: CampoDaDefinicao;
  valor: number | null | undefined;
  erros?: string[];
  somenteLeitura?: boolean;
  aoMudar: (valor: number | null) => void;
}

/**
 * Escolhe um registro do formulário de origem (achado pelo nome); o valor é o `id` dele. Mostra
 * os valores que a origem libera, deixa trocar, e (com o provedor de gavetas) criar ou editar a
 * origem ali mesmo, sem sair do preenchimento.
 */
export function CampoDeReferencia({ campo, valor, erros, somenteLeitura, aoMudar }: Props) {
  const gavetas = useGavetas();
  const { estado, recarregar } = useOrigemDaReferencia(campo.formulario);
  const [escolhendo, setEscolhendo] = useState(false);
  const origem = estado.situacao === "pronto" ? estado.origem : null;
  const nomeDaOrigem = origem?.formulario?.nome ?? campo.formulario ?? "origem";
  const selecionada = valor == null ? undefined : origem?.opcoes.find((o) => o.id === valor);

  function criar() {
    const formulario = origem?.formulario;
    if (!gavetas || !formulario) return;
    gavetas.abrir({
      modo: { tipo: "novo", formularioId: formulario.id },
      aoConcluir: (registro) => {
        recarregar();
        aoMudar(registro.id);
      },
    });
  }

  function editar() {
    if (!gavetas || valor == null) return;
    gavetas.abrir({
      modo: { tipo: "editar", registroId: valor },
      // Mesmo id de novo: o formulário de baixo refaz a prévia com os valores atualizados da origem.
      aoConcluir: () => {
        recarregar();
        aoMudar(valor);
      },
    });
  }

  return (
    <Campo id={campo.id} rotulo={campo.rotulo} obrigatorio={campo.obrigatorio} erros={erros}>
      {({ id, "aria-invalid": invalido, "aria-describedby": descricao }) => {
        // O rótulo do campo sozinho esconderia o que o botão faz: o nome é "rótulo + texto da ação".
        const principal = {
          id,
          "aria-invalid": invalido,
          "aria-describedby": descricao,
          "aria-labelledby": `rotulo-${campo.id} acao-${campo.id}`,
        };
        const carregando = estado.situacao === "carregando";
        return (
          <>
            {valor == null ? (
              <div className="flex flex-col gap-3 rounded-controle border border-dashed border-pedra-300 bg-superficie p-3">
                <p className="text-sm text-pedra-600">
                  {textoDoEstado(estado.situacao, origem, campo.formulario)}
                </p>
                {somenteLeitura ? null : (
                  <div className="flex flex-wrap gap-2">
                    <Botao {...principal} disabled={carregando} onClick={() => setEscolhendo(true)}>
                      <span id={`acao-${campo.id}`}>Selecionar registro</span>
                    </Botao>
                    {gavetas ? (
                      <Botao variante="primario" disabled={!origem?.formulario} onClick={criar}>
                        <Icone nome="mais" />
                        Criar {nomeDaOrigem}
                      </Botao>
                    ) : null}
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-controle border border-pedra-300 bg-superficie">
                <div className="flex flex-wrap items-center gap-2 border-b border-pedra-200 px-3 py-2">
                  <Icone nome="elo" className="text-sinal-600" />
                  <span className="font-medium">
                    {nomeDaOrigem} <span className="font-mono tabular-nums">#{valor}</span>
                  </span>
                  {selecionada ? (
                    <span className="font-mono text-xs text-pedra-500 tabular-nums">
                      {dataBrasileira(selecionada.criadoEm.slice(0, 10))}
                    </span>
                  ) : null}
                  {somenteLeitura ? null : (
                    <span className="ml-auto flex flex-wrap gap-1">
                      <Botao
                        {...principal}
                        variante="fantasma"
                        tamanho="pequeno"
                        onClick={() => setEscolhendo(true)}
                      >
                        <span id={`acao-${campo.id}`}>Trocar</span>
                      </Botao>
                      {gavetas ? (
                        <Botao variante="fantasma" tamanho="pequeno" onClick={editar}>
                          <Icone nome="editar" />
                          Editar origem
                        </Botao>
                      ) : null}
                      <Botao
                        variante="fantasma"
                        tamanho="pequeno"
                        aria-label="Remover a referência"
                        onClick={() => aoMudar(null)}
                      >
                        <Icone nome="fechar" />
                      </Botao>
                    </span>
                  )}
                </div>
                <div className="px-3 py-2.5">
                  {selecionada ? (
                    <ResumoDeRegistro celulas={escolherCelulas(selecionada.celulas, 8)} />
                  ) : (
                    <p className="text-sm text-pedra-500">
                      {carregando
                        ? "Carregando os valores…"
                        : "Valores deste registro indisponíveis."}
                    </p>
                  )}
                </div>
              </div>
            )}
            {estado.situacao === "falhou" ? (
              <p className="text-sm text-erro-700">
                Não foi possível carregar os registros de origem.
              </p>
            ) : null}
            {escolhendo && origem ? (
              <ListaDeOrigens
                origem={origem}
                nome={nomeDaOrigem}
                valor={valor ?? null}
                aoEscolher={(id) => {
                  aoMudar(id);
                  setEscolhendo(false);
                }}
                aoCriar={
                  gavetas && origem.formulario
                    ? () => {
                        setEscolhendo(false);
                        criar();
                      }
                    : undefined
                }
                aoFechar={() => setEscolhendo(false)}
              />
            ) : null}
          </>
        );
      }}
    </Campo>
  );
}

function textoDoEstado(
  situacao: "carregando" | "falhou" | "pronto",
  origem: Origem | null,
  formulario: string | null | undefined,
): string {
  if (situacao === "carregando") return "Carregando os registros de origem…";
  if (situacao === "falhou") return "Nenhum registro selecionado.";
  if (origem?.formulario === null) return `O formulário “${formulario}” não existe.`;
  if (origem?.opcoes.length === 0) {
    return `Ainda não há registros em “${formulario}”. Crie um primeiro.`;
  }
  return "Nenhum registro selecionado.";
}

function ListaDeOrigens({
  origem,
  nome,
  valor,
  aoEscolher,
  aoCriar,
  aoFechar,
}: {
  origem: Origem;
  nome: string;
  valor: number | null;
  aoEscolher: (id: number) => void;
  aoCriar?: () => void;
  aoFechar: () => void;
}) {
  const [busca, setBusca] = useState("");
  const visiveis = origem.opcoes.filter((opcao) =>
    combinaComBusca(
      `${opcao.id} ${dataBrasileira(opcao.criadoEm.slice(0, 10))} ${opcao.celulas.map((c) => c.texto).join(" ")}`,
      busca,
    ),
  );

  return (
    <Gaveta
      titulo={`Selecionar ${nome}`}
      subtitulo="Escolha o registro de onde este herda os valores."
      aoFechar={aoFechar}
      fecharAoClicarFora
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <CampoDeBusca
            rotulo="Buscar registro"
            placeholder="Buscar por número, data ou valor"
            className="min-w-48 flex-1"
            valor={busca}
            aoMudar={setBusca}
          />
          {aoCriar ? (
            <Botao variante="primario" onClick={aoCriar}>
              <Icone nome="mais" />
              Criar {nome}
            </Botao>
          ) : null}
        </div>
        {origem.truncado ? (
          <p className="text-sm text-pedra-600">
            Mostrando os {origem.opcoes.length} registros mais recentes.
          </p>
        ) : null}
        {origem.opcoes.length === 0 ? (
          <p className="text-sm text-pedra-600">Ainda não há registros em “{nome}”.</p>
        ) : visiveis.length === 0 ? (
          <p className="text-sm text-pedra-600">Nenhum registro combina com a busca.</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {visiveis.map((opcao) => (
              <li key={opcao.id}>
                <button
                  type="button"
                  aria-pressed={opcao.id === valor}
                  aria-label={`Selecionar registro ${opcao.id}`}
                  onClick={() => aoEscolher(opcao.id)}
                  className={`flex w-full flex-col gap-2 rounded-cartao border bg-superficie p-3.5 text-left shadow-cartao transition-colors duration-(--duracao-rapida) hover:border-pedra-500 ${opcao.id === valor ? "border-sinal-500 ring-2 ring-sinal-500/25" : "border-pedra-300"}`}
                >
                  <span className="flex items-center gap-2">
                    <span className="font-mono font-semibold tabular-nums">#{opcao.id}</span>
                    <span className="font-mono text-xs text-pedra-500 tabular-nums">
                      {dataBrasileira(opcao.criadoEm.slice(0, 10))}
                    </span>
                    {opcao.id === valor ? (
                      <span className="ml-auto text-xs font-medium text-sinal-600">
                        Selecionado
                      </span>
                    ) : null}
                  </span>
                  <ResumoDeRegistro celulas={escolherCelulas(opcao.celulas, 4)} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Gaveta>
  );
}
