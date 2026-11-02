import type { ReactNode } from "react";
import type { Esquemas, TipoDeCampo } from "../api/cliente";
import { EditorDeFormula } from "./EditorDeFormula";
import type { CampoEmEdicao, ErroNoCampo } from "./estado";

type Catalogo = Esquemas["CatalogoSaida"];

interface Props {
  campo: CampoEmEdicao;
  todosOsCampos: CampoEmEdicao[];
  catalogo: Catalogo;
  /** Nomes dos formulários que podem ser origem de uma referência. */
  formulariosDeOrigem: string[];
  erros: ErroNoCampo[];
  aoMudar: (mudancas: Partial<CampoEmEdicao>) => void;
}

const CAMPOS_USAVEIS_EM_FORMULA: TipoDeCampo[] = ["numero", "data", "sim_nao", "calculado"];
const CLASSE = "rounded border border-slate-300 px-2 py-1.5 aria-[invalid=true]:border-red-500";

/**
 * Edita as propriedades de um campo. Só mostra as que o catálogo diz que o tipo aceita
 * (`GET /catalogo`): assim o painel nunca fica dessincronizado do servidor.
 */
export function PainelDePropriedades({
  campo,
  todosOsCampos,
  catalogo,
  formulariosDeOrigem,
  erros,
  aoMudar,
}: Props) {
  const aceitas = catalogo.tipos.find((tipo) => tipo.id === campo.tipo)?.propriedades ?? [];
  const aceita = (propriedade: string) => aceitas.includes(propriedade);
  const errosDe = (propriedade: string) => erros.filter((e) => e.propriedade === propriedade);
  const erroDaFormula = errosDe("formula")[0];

  return (
    <section aria-label="Propriedades do campo" className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Propriedades</h2>

      {errosDe("").map((erro) => (
        <p key={erro.mensagem} role="alert" className="text-sm text-red-700">
          {erro.mensagem}
        </p>
      ))}

      <Texto
        chave={campo.chave}
        nome="rotulo"
        rotulo="Rótulo"
        valor={campo.rotulo}
        erros={errosDe("rotulo")}
        aoMudar={(rotulo) => aoMudar({ rotulo })}
      />
      <Texto
        chave={campo.chave}
        nome="id"
        rotulo="Identificador (id)"
        valor={campo.id}
        erros={errosDe("id")}
        aoMudar={(id) => aoMudar({ id })}
        ajuda="Letras sem acento, números e _. É o nome do campo nas fórmulas."
      />

      <Moldura id={`tipo-${campo.chave}`} rotulo="Tipo" erros={errosDe("tipo")}>
        {(props) => (
          <select
            {...props}
            className={CLASSE}
            value={campo.tipo}
            onChange={(e) => aoMudar({ tipo: e.target.value as TipoDeCampo })}
          >
            {catalogo.tipos.map((tipo) => (
              <option key={tipo.id} value={tipo.id}>
                {tipo.rotulo}
              </option>
            ))}
          </select>
        )}
      </Moldura>

      {aceita("obrigatorio") ? (
        <Caixa
          rotulo="Obrigatório"
          marcado={campo.obrigatorio}
          aoMudar={(obrigatorio) => aoMudar({ obrigatorio })}
        />
      ) : null}
      {aceita("unidade") ? (
        <Texto
          chave={campo.chave}
          nome="unidade"
          rotulo="Unidade"
          valor={campo.unidade}
          erros={errosDe("unidade")}
          aoMudar={(unidade) => aoMudar({ unidade })}
        />
      ) : null}
      {aceita("casas_decimais") ? (
        <Texto
          chave={campo.chave}
          nome="casas"
          rotulo="Casas decimais"
          valor={campo.casasDecimais}
          erros={errosDe("casas_decimais")}
          aoMudar={(casasDecimais) => aoMudar({ casasDecimais })}
          ajuda="Só arredonda a exibição e o CSV; o valor guardado mantém a precisão total."
        />
      ) : null}
      {aceita("opcoes") ? (
        <Moldura
          id={`opcoes-${campo.chave}`}
          rotulo="Opções (uma por linha)"
          erros={errosDe("opcoes")}
        >
          {(props) => (
            <textarea
              {...props}
              rows={4}
              className={CLASSE}
              value={campo.opcoes}
              onChange={(e) => aoMudar({ opcoes: e.target.value })}
            />
          )}
        </Moldura>
      ) : null}
      {aceita("maximo") ? (
        <Texto
          chave={campo.chave}
          nome="maximo"
          rotulo="Máximo de fotos"
          valor={campo.maximo}
          erros={errosDe("maximo")}
          aoMudar={(maximo) => aoMudar({ maximo })}
        />
      ) : null}
      {aceita("formulario") ? (
        <Moldura
          id={`origem-${campo.chave}`}
          rotulo="Formulário de origem"
          erros={errosDe("formulario")}
        >
          {(props) => (
            <select
              {...props}
              className={CLASSE}
              value={campo.formulario}
              onChange={(e) => aoMudar({ formulario: e.target.value })}
            >
              <option value="">— escolha —</option>
              {formulariosDeOrigem.map((nome) => (
                <option key={nome} value={nome}>
                  {nome}
                </option>
              ))}
            </select>
          )}
        </Moldura>
      ) : null}
      {aceita("formula") ? (
        <EditorDeFormula
          id={`formula-${campo.chave}`}
          rotulo="Fórmula"
          valor={campo.formula}
          aoMudar={(formula) => aoMudar({ formula })}
          funcoes={catalogo.funcoes}
          constantes={catalogo.constantes.map((constante) => constante.nome)}
          campos={todosOsCampos
            .filter(
              (outro) =>
                outro.chave !== campo.chave && CAMPOS_USAVEIS_EM_FORMULA.includes(outro.tipo),
            )
            .map((outro) => ({ id: outro.id, rotulo: outro.rotulo }))}
          erro={
            erroDaFormula
              ? { mensagem: erroDaFormula.mensagem, posicao: erroDaFormula.posicao }
              : undefined
          }
        />
      ) : null}
      {aceita("compartilhado") ? (
        <Caixa
          rotulo="Compartilhado com formulários dependentes"
          marcado={campo.compartilhado}
          aoMudar={(compartilhado) => aoMudar({ compartilhado })}
        />
      ) : null}
      {errosDe("compartilhado").map((erro) => (
        <p key={erro.mensagem} role="alert" className="text-sm text-red-700">
          {erro.mensagem}
        </p>
      ))}
    </section>
  );
}

/**
 * Moldura de um controle do painel: o rótulo contém só o rótulo, e a ajuda e os erros ficam
 * fora dele, ligados ao controle por `aria-describedby` (senão virariam parte do nome do campo).
 */
function Moldura({
  id,
  rotulo,
  erros,
  ajuda,
  children,
}: {
  id: string;
  rotulo: string;
  erros: ErroNoCampo[];
  ajuda?: string;
  children: (propsDoControle: {
    id: string;
    "aria-invalid": boolean;
    "aria-describedby": string | undefined;
  }) => ReactNode;
}) {
  const idDaAjuda = `${id}-ajuda`;
  const idDosErros = `${id}-erros`;
  const descricao = [ajuda ? idDaAjuda : null, erros.length > 0 ? idDosErros : null].filter(
    Boolean,
  );
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {rotulo}
      </label>
      {children({
        id,
        "aria-invalid": erros.length > 0,
        "aria-describedby": descricao.length > 0 ? descricao.join(" ") : undefined,
      })}
      {ajuda ? (
        <span id={idDaAjuda} className="text-xs text-slate-500">
          {ajuda}
        </span>
      ) : null}
      {erros.length > 0 ? (
        <ul id={idDosErros} role="alert" className="text-sm text-red-700">
          {erros.map((erro) => (
            <li key={erro.mensagem}>{erro.mensagem}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function Texto({
  chave,
  nome,
  rotulo,
  valor,
  erros,
  aoMudar,
  ajuda,
}: {
  chave: string;
  nome: string;
  rotulo: string;
  valor: string;
  erros: ErroNoCampo[];
  aoMudar: (valor: string) => void;
  ajuda?: string;
}) {
  return (
    <Moldura id={`${nome}-${chave}`} rotulo={rotulo} erros={erros} ajuda={ajuda}>
      {(props) => (
        <input
          {...props}
          type="text"
          className={CLASSE}
          value={valor}
          onChange={(e) => aoMudar(e.target.value)}
        />
      )}
    </Moldura>
  );
}

function Caixa({
  rotulo,
  marcado,
  aoMudar,
}: {
  rotulo: string;
  marcado: boolean;
  aoMudar: (marcado: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm font-medium">
      <input type="checkbox" checked={marcado} onChange={(e) => aoMudar(e.target.checked)} />
      {rotulo}
    </label>
  );
}
