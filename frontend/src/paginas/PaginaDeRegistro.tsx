import type { Rota } from "../rotas";
import { EditorDeRegistro } from "../registros/EditorDeRegistro";
import type { ModoDoRegistro } from "../registros/contexto";
import { chaveDoModo, useRegistroCarregado } from "../registros/useRegistroCarregado";
import { EsqueletoDoFormulario } from "./esqueletos";
import { Falha } from "./Estado";

export type { ModoDoRegistro };

interface Props {
  modo: ModoDoRegistro;
  navegar: (rota: Rota) => void;
}

/** Preenche um registro novo ou edita um existente com a definição da versão em que ele nasceu. */
export function PaginaDeRegistro({ modo, navegar }: Props) {
  const carga = useRegistroCarregado(modo);

  if (carga.situacao === "carregando") return <EsqueletoDoFormulario />;
  if (carga.situacao === "erro") return <Falha mensagem={carga.mensagem} />;
  const { formularioId } = carga.dados;
  const voltar = () => navegar({ nome: "registros", formularioId });
  return (
    <EditorDeRegistro
      // Outro registro é outro formulário em branco: a chave reinicia o estado dos campos.
      key={chaveDoModo(modo)}
      carregado={carga.dados}
      aoSalvar={voltar}
      aoCancelar={voltar}
      aoExcluir={voltar}
      comoPagina
    />
  );
}
