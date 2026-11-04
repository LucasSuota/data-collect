import { useState } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type Registro } from "../api/cliente";
import { FormRenderer } from "../components/FormRenderer";
import type { ErrosPorCampo, Valores } from "../components/FormRenderer";
import {
  calculadosDoRegistro,
  valoresDoRegistro,
} from "../components/FormRenderer/valoresDoRegistro";
import { Falha, mensagemDe } from "../paginas/Estado";
import { Botao, Cartao, Icone } from "../ui";
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
    // A gaveta é um portal: sem isto o envio subiria pela árvore do React até o formulário de baixo.
    evento.stopPropagation();
    setSalvando(true);
    setErros({});
    setFalhaGeral(null);
    try {
      const salvo = registro
        ? await cliente.atualizarRegistro(registro.id, valores)
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
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {registro ? `Registro ${registro.id}` : "Novo registro"} · {carregado.nomeDoFormulario}
          </h1>
          <p className="mt-0.5 text-sm text-pedra-600">
            Versão {carregado.numeroDaVersao} do formulário
          </p>
        </div>
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
        />
      </Cartao>

      <div className="flex flex-wrap gap-2">
        <Botao type="submit" variante="primario" carregando={salvando}>
          {salvando ? "Salvando…" : "Salvar"}
        </Botao>
        <Botao onClick={aoCancelar}>Cancelar</Botao>
        {registro && aoExcluir ? (
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
