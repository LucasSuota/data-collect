import { useEffect, useState } from "react";
import type { Pasta, Progresso, RegistroRecente } from "../api/cliente";
import { useApi } from "../api/contexto";
import { useSessao } from "../auth/sessao";
import { ComPermissao } from "../shell/permissoes";
import { SeletorDeFormulario } from "../shell/SeletorDeFormulario";
import type { Rota } from "../rotas";
import { Botao, Esqueleto, Icone, SeloDeCargo, SeloDeEstado } from "../ui";
import { passosDoChecklist, type EstadoDaEquipe } from "./primeirosPassos";
import { Tour } from "./Tour";

export function dataRelativa(iso: string, agora = new Date()): string {
  const minutos = Math.round((agora.getTime() - new Date(iso).getTime()) / 60_000);
  if (minutos < 1) return "agora";
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `há ${horas} h`;
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function LinhaDeRegistro({ r }: { r: RegistroRecente }) {
  return (
    <a
      href={`#/registros/${r.id}`}
      className="flex min-h-14 items-center justify-between gap-3 rounded-cartao border border-pedra-200 bg-superficie px-4 py-3 shadow-cartao hover:border-sinal-300"
    >
      <span className="min-w-0">
        <span className="block truncate font-semibold">{r.formulario}</span>
        <span className="block truncate font-mono text-xs text-pedra-600">
          #{r.id}
          {r.destaque?.valor
            ? ` · ${r.destaque.valor}${r.destaque.unidade ? ` ${r.destaque.unidade}` : ""}`
            : ""}{" "}
          · {dataRelativa(r.atualizado_em)}
        </span>
      </span>
      <SeloDeEstado estado={r.estado} />
    </a>
  );
}

export function PaginaInicio({ navegar }: { navegar: (rota: Rota) => void }) {
  const api = useApi();
  const sessao = useSessao();
  const [recentes, setRecentes] = useState<RegistroRecente[] | null>(null);
  const [pastas, setPastas] = useState<Pasta[]>([]);
  const [estado, setEstado] = useState<EstadoDaEquipe | null>(null);
  const [progresso, setProgresso] = useState<Progresso | null>(null);
  const [escolhendo, setEscolhendo] = useState(false);
  const { pode } = sessao;

  useEffect(() => {
    let ativo = true;
    const registros = pode("registros:ver") ? api.registrosRecentes(5) : Promise.resolve([]);
    const formularios = pode("formularios:ver") ? api.listarFormularios() : Promise.resolve([]);
    const membros = pode("equipe:ver") ? api.listarMembros() : Promise.resolve(null);
    void Promise.all([registros, formularios, membros]).then(
      ([r, f, m]) => {
        if (!ativo) return;
        setRecentes(r);
        setEstado({
          formularios: f.length,
          registros: r.length,
          pessoas: m ? m.filter((x) => x.ativo).length : 2,
        });
      },
      () => ativo && setRecentes([]),
    );
    if (pode("formularios:ver"))
      void api.listarPastas().then(
        (p) => ativo && setPastas(p),
        () => undefined,
      );
    void api.progresso().then(
      (p) => ativo && setProgresso(p),
      () => undefined,
    );
    return () => {
      ativo = false;
    };
  }, [api, pode]);

  const raiz = pastas.filter((p) => p.pasta_pai_id === null);
  const passos = estado ? passosDoChecklist(estado, pode) : [];
  const pendentes = passos.filter((p) => !p.feito);

  function salvarProgresso(novo: Progresso) {
    setProgresso(novo);
    void api.salvarProgresso(novo).catch(() => undefined); // o passeio é conveniência
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold sm:text-3xl">
            Olá, {sessao.eu.pessoa.nome.split(" ")[0]}
          </h1>
          <div className="mt-1.5 flex items-center gap-2 text-sm text-pedra-600">
            <SeloDeCargo nome={sessao.equipe.cargo.nome} />
            <span>{sessao.equipe.nome}</span>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:max-w-xl">
        <ComPermissao permissao="registros:criar" bloqueado="Novo registro">
          <Botao
            variante="primario"
            className="min-h-20 flex-col items-start justify-between !px-4 !py-3 text-left text-base"
            onClick={() => setEscolhendo(true)}
          >
            <Icone nome="mais" tamanho={20} />
            Novo registro
          </Botao>
        </ComPermissao>
        <ComPermissao permissao="formularios:publicar" bloqueado="Criar formulário">
          <Botao
            className="min-h-20 flex-col items-start justify-between !px-4 !py-3 text-left text-base"
            onClick={() => navegar({ nome: "novoFormulario" })}
          >
            <Icone nome="documento" tamanho={20} />
            Criar formulário
          </Botao>
        </ComPermissao>
      </div>

      {pendentes.length > 0 && !progresso?.checklist_dispensado ? (
        <section
          aria-labelledby="primeiros"
          className="rounded-cartao border border-sinal-300 bg-sinal-100/40 p-4"
        >
          <div className="flex items-center justify-between gap-2">
            <h2 id="primeiros" className="text-base font-bold">
              Primeiros passos
            </h2>
            <button
              type="button"
              className="min-h-11 px-2 text-sm text-pedra-600 underline"
              onClick={() =>
                salvarProgresso({
                  tour_concluido: progresso?.tour_concluido ?? true,
                  passo: progresso?.passo ?? 0,
                  checklist_dispensado: true,
                })
              }
            >
              Dispensar
            </button>
          </div>
          <ul className="mt-2 flex flex-col gap-1">
            {passos.map((p) => (
              <li key={p.id}>
                <a href={p.href} className="flex min-h-11 items-center gap-3 text-sm">
                  <span
                    className={`grid size-5 place-items-center rounded-full border ${p.feito ? "border-sucesso-700 bg-sucesso-700 text-superficie" : "border-pedra-400"}`}
                  >
                    {p.feito ? <Icone nome="ok" tamanho={12} /> : null}
                  </span>
                  <span className={p.feito ? "text-pedra-500 line-through" : "font-medium"}>
                    {p.rotulo}
                  </span>
                  <span className="sr-only">{p.feito ? "(feito)" : "(pendente)"}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {pode("registros:ver") ? (
        <section aria-labelledby="recentes" className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <h2 id="recentes" className="text-lg font-bold">
              Seus registros recentes
            </h2>
            <a href="#/registros" className="text-sm font-semibold text-sinal-500">
              Ver todos
            </a>
          </div>
          {recentes === null ? (
            <div role="status" aria-label="Carregando" className="flex flex-col gap-2">
              <Esqueleto className="h-16 rounded-cartao" />
              <Esqueleto className="h-16 rounded-cartao" />
              <Esqueleto className="h-16 rounded-cartao" />
            </div>
          ) : recentes.length === 0 ? (
            <p className="rounded-cartao border border-dashed border-pedra-300 p-5 text-sm text-pedra-600">
              Nenhum registro ainda. Quando a equipe preencher o primeiro, ele aparece aqui.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {recentes.map((r) => (
                <li key={r.id}>
                  <LinhaDeRegistro r={r} />
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {raiz.length > 0 ? (
        <section aria-labelledby="pastas" className="flex flex-col gap-3">
          <h2 id="pastas" className="text-lg font-bold">
            Pastas
          </h2>
          <ul className="flex flex-wrap gap-2">
            {raiz.map((p) => (
              <li key={p.id}>
                <a
                  href={`#/pastas/${p.id}`}
                  className="inline-flex min-h-11 items-center gap-2 rounded-cartao bg-pedra-100 px-4 text-sm font-medium hover:bg-pedra-200"
                >
                  <Icone nome="pasta" tamanho={16} />
                  {p.nome}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {escolhendo ? (
        <SeletorDeFormulario
          aoFechar={() => setEscolhendo(false)}
          aoEscolher={(formularioId) => navegar({ nome: "novoRegistro", formularioId })}
        />
      ) : null}
      {progresso && !progresso.tour_concluido ? (
        <Tour
          passoInicial={progresso.passo}
          aoAvancar={(passo) => salvarProgresso({ ...progresso, passo })}
          aoTerminar={() => salvarProgresso({ ...progresso, tour_concluido: true })}
        />
      ) : null}
    </div>
  );
}
