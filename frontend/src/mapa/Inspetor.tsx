import type { TipoDeCampo } from "../api/cliente";
import type { Rota } from "../rotas";
import { Botao, Cartao, Conformidade, Icone } from "../ui";
import type { DetalheDoNo } from "./detalhe";
import { idDoNoDeFormulario, idDoNoDeRegistro } from "./grafo";

const NOME_DO_TIPO: Record<TipoDeCampo, string> = {
  texto: "Texto",
  numero: "Número",
  data: "Data",
  selecao: "Seleção",
  sim_nao: "Sim/Não",
  calculado: "Calculado",
  secao: "Seção",
  referencia: "Referência",
  localizacao: "Localização",
  foto: "Foto",
};

interface Props {
  detalhe: DetalheDoNo | null;
  aoFechar: () => void;
  aoSelecionar: (noId: string) => void;
  navegar: (rota: Rota) => void;
}

/** O painel ao lado do mapa: tudo do nó selecionado, com os valores completos e as ações. */
export function Inspetor({ detalhe, aoFechar, aoSelecionar, navegar }: Props) {
  if (detalhe === null) return null;

  return (
    <Cartao
      className="relative flex max-h-full flex-col gap-5 overflow-y-auto p-4 shadow-elevada"
      aria-label="Detalhes do cartão selecionado"
    >
      <Botao
        variante="fantasma"
        tamanho="pequeno"
        aria-label="Fechar os detalhes"
        className="absolute top-3 right-3"
        onClick={aoFechar}
      >
        <Icone nome="fechar" />
      </Botao>
      {detalhe.tipo === "formulario" ? (
        <DoFormulario detalhe={detalhe} aoSelecionar={aoSelecionar} navegar={navegar} />
      ) : (
        <DoRegistro detalhe={detalhe} aoSelecionar={aoSelecionar} navegar={navegar} />
      )}
    </Cartao>
  );
}

type Detalhado<T extends DetalheDoNo["tipo"]> = Extract<DetalheDoNo, { tipo: T }>;

function DoFormulario({
  detalhe,
  aoSelecionar,
  navegar,
}: {
  detalhe: Detalhado<"formulario">;
  aoSelecionar: Props["aoSelecionar"];
  navegar: Props["navegar"];
}) {
  const { formulario, recebeDe, usadoPor } = detalhe;
  const campos = formulario.definicao.campos.filter((campo) => campo.tipo !== "secao");
  return (
    <>
      <Titulo
        icone="registros"
        titulo={formulario.nome}
        detalhe={`Versão ${formulario.versao ?? "?"} · ${formulario.totalDeRegistros} registro${formulario.totalDeRegistros === 1 ? "" : "s"}`}
      />
      <div className="flex flex-wrap gap-1.5">
        <Botao
          variante="primario"
          tamanho="pequeno"
          onClick={() => navegar({ nome: "novoRegistro", formularioId: formulario.id })}
        >
          Novo registro
        </Botao>
        <Botao
          tamanho="pequeno"
          onClick={() => navegar({ nome: "registros", formularioId: formulario.id })}
        >
          Registros
        </Botao>
        <Botao
          variante="fantasma"
          tamanho="pequeno"
          onClick={() => navegar({ nome: "editarFormulario", formularioId: formulario.id })}
        >
          <Icone nome="editar" />
          Editar
        </Botao>
      </div>

      <Secao titulo="Recebe de">
        {recebeDe.length === 0 ? (
          <Vazio>Não depende de nenhum formulário.</Vazio>
        ) : (
          recebeDe.map(({ campo, origem }) => (
            <Vizinho
              key={`${campo}-${origem.id}`}
              texto={origem.nome}
              via={campo}
              aoClicar={() => aoSelecionar(idDoNoDeFormulario(origem.id))}
            />
          ))
        )}
      </Secao>
      <Secao titulo="Usado por">
        {usadoPor.length === 0 ? (
          <Vazio>Nenhum formulário depende deste.</Vazio>
        ) : (
          usadoPor.map((usuario) => (
            <Vizinho
              key={usuario.id}
              texto={usuario.nome}
              aoClicar={() => aoSelecionar(idDoNoDeFormulario(usuario.id))}
            />
          ))
        )}
      </Secao>
      <Secao titulo={`Campos (${campos.length})`}>
        <ul className="flex flex-col divide-y divide-pedra-200 text-sm">
          {campos.map((campo) => (
            <li key={campo.id} className="flex items-center gap-2 py-1.5">
              {campo.compartilhado ? (
                <Icone
                  nome="elo"
                  tamanho={13}
                  className="shrink-0 text-sinal-600"
                  aria-label="Compartilhado"
                  role="img"
                />
              ) : null}
              <span className="min-w-0 flex-1 truncate">{campo.rotulo}</span>
              <span className="shrink-0 text-xs text-pedra-500">
                {NOME_DO_TIPO[campo.tipo]}
                {campo.unidade ? ` · ${campo.unidade}` : ""}
              </span>
            </li>
          ))}
        </ul>
      </Secao>
    </>
  );
}

function DoRegistro({
  detalhe,
  aoSelecionar,
  navegar,
}: {
  detalhe: Detalhado<"registro">;
  aoSelecionar: Props["aoSelecionar"];
  navegar: Props["navegar"];
}) {
  const { registro, formulario, origens, dependentes } = detalhe;
  return (
    <>
      <Titulo
        icone="pasta"
        titulo={`${formulario.nome} #${registro.id}`}
        detalhe={formulario.nome}
      />
      <div className="flex flex-wrap gap-1.5">
        <Botao
          variante="primario"
          tamanho="pequeno"
          onClick={() => navegar({ nome: "registro", registroId: registro.id })}
        >
          <Icone nome="abrir" />
          Abrir registro
        </Botao>
      </div>

      <Secao titulo="Origem dos valores">
        {origens.length === 0 ? (
          <Vazio>Este registro não aponta para outro.</Vazio>
        ) : (
          origens.map(({ rotulo, registro: origem }) => (
            <Vizinho
              key={`${rotulo}-${origem.id}`}
              texto={`Registro #${origem.id}`}
              via={rotulo}
              aoClicar={() => aoSelecionar(idDoNoDeRegistro(origem.id))}
            />
          ))
        )}
      </Secao>
      <Secao titulo="Usado por">
        {dependentes.length === 0 ? (
          <Vazio>Nenhum registro aponta para este.</Vazio>
        ) : (
          dependentes.map(({ rotulo, registro: usuario }) => (
            <Vizinho
              key={`${rotulo}-${usuario.id}`}
              texto={`Registro #${usuario.id}`}
              via={rotulo}
              aoClicar={() => aoSelecionar(idDoNoDeRegistro(usuario.id))}
            />
          ))
        )}
      </Secao>
      <Secao titulo="Valores">
        <dl className="flex flex-col divide-y divide-pedra-200 text-sm">
          {registro.celulas.map((celula) => (
            <div key={celula.id} className="flex items-center gap-2 py-1.5">
              <dt className="flex min-w-0 flex-1 items-center gap-1.5 text-pedra-600">
                {celula.compartilhado ? (
                  <Icone
                    nome="elo"
                    tamanho={13}
                    className="shrink-0 text-sinal-600"
                    aria-label="Compartilhado"
                    role="img"
                  />
                ) : null}
                <span className="truncate">{celula.rotulo}</span>
              </dt>
              <dd className="shrink-0 text-right font-mono tabular-nums">
                {celula.conforme !== null ? (
                  <Conformidade conforme={celula.conforme} texto={celula.texto} />
                ) : (
                  <>
                    {celula.texto === "" ? "—" : celula.texto}
                    {celula.unidade ? (
                      <span className="ml-1 text-xs text-pedra-500">{celula.unidade}</span>
                    ) : null}
                  </>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </Secao>
    </>
  );
}

function Titulo({
  icone,
  titulo,
  detalhe,
}: {
  icone: "registros" | "pasta";
  titulo: string;
  detalhe: string;
}) {
  return (
    <div className="flex items-center gap-3 pr-9">
      <span className="grid size-10 shrink-0 place-items-center rounded-controle bg-pedra-900 text-superficie">
        <Icone nome={icone} tamanho={18} />
      </span>
      <div className="min-w-0">
        <h2 className="truncate text-base font-semibold">{titulo}</h2>
        <p className="truncate font-mono text-xs text-pedra-500 tabular-nums">{detalhe}</p>
      </div>
    </div>
  );
}

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className="text-xs font-semibold tracking-wide text-pedra-500 uppercase">{titulo}</h3>
      {children}
    </section>
  );
}

const Vazio = ({ children }: { children: React.ReactNode }) => (
  <p className="text-sm text-pedra-500">{children}</p>
);

function Vizinho({ texto, via, aoClicar }: { texto: string; via?: string; aoClicar: () => void }) {
  return (
    <button
      type="button"
      onClick={aoClicar}
      className="flex items-center gap-2 rounded-controle border border-pedra-200 px-2.5 py-1.5 text-left text-sm hover:border-pedra-400 hover:bg-pedra-50"
    >
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{texto}</span>
        {via ? <span className="block truncate text-xs text-pedra-500">via {via}</span> : null}
      </span>
      <Icone nome="seta" tamanho={13} className="shrink-0 text-pedra-400" />
    </button>
  );
}
