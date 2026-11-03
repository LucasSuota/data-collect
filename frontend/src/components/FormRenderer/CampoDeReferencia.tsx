import { useEffect, useState } from "react";
import { useApi } from "../../api/contexto";
import type { Campo as CampoDaDefinicao } from "../../api/cliente";
import { Campo, CLASSE_DO_CONTROLE } from "./Campo";

interface Opcao {
  id: number;
  rotulo: string;
}

type Estado =
  { situacao: "carregando" } | { situacao: "pronto"; opcoes: Opcao[] } | { situacao: "falhou" };

interface Props {
  campo: CampoDaDefinicao;
  valor: number | null | undefined;
  erros?: string[];
  somenteLeitura?: boolean;
  aoMudar: (valor: number | null) => void;
}

const LIMITE_DE_OPCOES = 200;

/** Escolhe um registro do formulário de origem (resolvido pelo nome); o valor é o `id` dele. */
export function CampoDeReferencia({ campo, valor, erros, somenteLeitura, aoMudar }: Props) {
  const cliente = useApi();
  const [estado, setEstado] = useState<Estado>({ situacao: "carregando" });

  useEffect(() => {
    let cancelado = false;
    async function carregar() {
      const nome = (campo.formulario ?? "").trim().toLowerCase();
      const formularios = await cliente.listarFormularios();
      const origem = formularios.find((f) => f.nome.trim().toLowerCase() === nome);
      if (!origem) return [];
      const pagina = await cliente.listarRegistros(origem.id, { limite: LIMITE_DE_OPCOES });
      return pagina.itens.map((registro) => ({
        id: registro.id,
        rotulo: `Registro ${registro.id} — ${registro.criado_em.slice(0, 10)}`,
      }));
    }
    carregar().then(
      (opcoes) => !cancelado && setEstado({ situacao: "pronto", opcoes }),
      () => !cancelado && setEstado({ situacao: "falhou" }),
    );
    return () => {
      cancelado = true;
    };
  }, [cliente, campo.formulario]);

  const opcoes = estado.situacao === "pronto" ? estado.opcoes : [];
  // O registro já escolhido precisa aparecer mesmo que a lista ainda não o traga.
  const todas =
    valor != null && !opcoes.some((o) => o.id === valor)
      ? [{ id: valor, rotulo: `Registro ${valor}` }, ...opcoes]
      : opcoes;

  return (
    <Campo id={campo.id} rotulo={campo.rotulo} obrigatorio={campo.obrigatorio} erros={erros}>
      {(propsDoControle) => (
        <>
          <select
            {...propsDoControle}
            className={CLASSE_DO_CONTROLE}
            disabled={somenteLeitura || estado.situacao === "carregando"}
            value={valor ?? ""}
            onChange={(evento) =>
              aoMudar(evento.target.value === "" ? null : Number(evento.target.value))
            }
          >
            <option value="">
              {estado.situacao === "carregando" ? "Carregando…" : "— nenhum —"}
            </option>
            {todas.map((opcao) => (
              <option key={opcao.id} value={opcao.id}>
                {opcao.rotulo}
              </option>
            ))}
          </select>
          {estado.situacao === "falhou" ? (
            <p className="text-sm text-erro-700">
              Não foi possível carregar os registros de origem.
            </p>
          ) : null}
          {estado.situacao === "pronto" && opcoes.length === 0 ? (
            <p className="text-sm text-pedra-500">
              Ainda não há registros em “{campo.formulario}”. Crie um primeiro.
            </p>
          ) : null}
        </>
      )}
    </Campo>
  );
}
