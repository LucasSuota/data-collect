import { useState } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type Definicao, type Registro } from "../api/cliente";
import { FormRenderer } from "../components/FormRenderer";
import type { ErrosPorCampo, Valores } from "../components/FormRenderer";
import {
  calculadosDoRegistro,
  valoresDoRegistro,
} from "../components/FormRenderer/valoresDoRegistro";
import type { Rota } from "../rotas";
import { Botao, Cartao, Icone } from "../ui";
import { EsqueletoDoFormulario } from "./esqueletos";
import { Falha, mensagemDe, useCarga } from "./Estado";

export type ModoDoRegistro =
  { tipo: "novo"; formularioId: number } | { tipo: "editar"; registroId: number };

interface Props {
  modo: ModoDoRegistro;
  navegar: (rota: Rota) => void;
}

interface Carregado {
  formularioId: number;
  versaoId: number;
  numeroDaVersao: number;
  nomeDoFormulario: string;
  definicao: Definicao;
  registro: Registro | null;
}

/** Preenche um registro novo ou edita um existente com a definição da versão em que ele nasceu. */
export function PaginaDeRegistro({ modo, navegar }: Props) {
  const cliente = useApi();
  const chave = modo.tipo === "novo" ? `novo-${modo.formularioId}` : `editar-${modo.registroId}`;

  const carga = useCarga<Carregado>(async () => {
    if (modo.tipo === "novo") {
      // Registro novo: sempre a versão ATUAL, e é o `versao_id` dela que vai no POST.
      const formulario = await cliente.obterFormulario(modo.formularioId);
      return {
        formularioId: formulario.id,
        versaoId: formulario.versao_atual.id,
        numeroDaVersao: formulario.versao_atual.numero,
        nomeDoFormulario: formulario.nome,
        definicao: formulario.versao_atual.definicao,
        registro: null,
      };
    }
    // Registro existente: a definição é a da VERSÃO DELE, não a atual.
    const registro = await cliente.obterRegistro(modo.registroId);
    const [formulario, versao] = await Promise.all([
      cliente.obterFormulario(registro.formulario_id),
      cliente.obterVersao(registro.formulario_id, registro.versao_id),
    ]);
    return {
      formularioId: registro.formulario_id,
      versaoId: versao.id,
      numeroDaVersao: versao.numero,
      nomeDoFormulario: formulario.nome,
      definicao: versao.definicao,
      registro,
    };
  }, [cliente, chave]);

  if (carga.situacao === "carregando") return <EsqueletoDoFormulario />;
  if (carga.situacao === "erro") return <Falha mensagem={carga.mensagem} />;
  return <Formulario key={chave} carregado={carga.dados} navegar={navegar} />;
}

function Formulario({ carregado, navegar }: { carregado: Carregado; navegar: Props["navegar"] }) {
  const cliente = useApi();
  const { registro, definicao } = carregado;
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
    if (erro instanceof ErroDaApi && erro.status === 422) {
      setErros(erro.mensagensPorCampo());
      setFalhaGeral(erro.erros.length === 0 ? erro.message : null);
    } else {
      setErros({});
      setFalhaGeral(mensagemDe(erro));
    }
  }

  async function salvar(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    setErros({});
    setFalhaGeral(null);
    try {
      if (registro) {
        await cliente.atualizarRegistro(registro.id, valores);
      } else {
        await cliente.criarRegistro(carregado.formularioId, carregado.versaoId, valores);
      }
      navegar({ nome: "registros", formularioId: carregado.formularioId });
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
      navegar({ nome: "registros", formularioId: carregado.formularioId });
    } catch (erro) {
      // 409: outro registro o referencia; a mensagem do servidor diz quais.
      setFalhaGeral(mensagemDe(erro));
      setConfirmandoExclusao(false);
    }
  }

  return (
    <form onSubmit={(e) => void salvar(e)} className="flex max-w-2xl flex-col gap-5" noValidate>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {registro ? `Registro ${registro.id}` : "Novo registro"} · {carregado.nomeDoFormulario}
        </h1>
        <p className="mt-0.5 text-sm text-pedra-600">
          Versão {carregado.numeroDaVersao} do formulário
        </p>
      </div>

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
        />
      </Cartao>

      <div className="flex flex-wrap gap-2">
        <Botao type="submit" variante="primario" carregando={salvando}>
          {salvando ? "Salvando…" : "Salvar"}
        </Botao>
        <Botao onClick={() => navegar({ nome: "registros", formularioId: carregado.formularioId })}>
          Cancelar
        </Botao>
        {registro ? (
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
