import { useState } from "react";
import { useApi } from "../api/contexto";
import { useSessao } from "../auth/sessao";
import { baixarArquivo } from "../lib/formatacao";
import { mensagemDoErro } from "../lib/erros";
import { Avatar } from "../shell/Avatar";
import { Aviso, Botao, Icone, SeloDeCargo, type NomeDoIcone } from "../ui";

function Atalho({ href, icone, texto }: { href: string; icone: NomeDoIcone; texto: string }) {
  return (
    <a
      href={href}
      className="flex min-h-12 items-center justify-between rounded-cartao border border-pedra-200 bg-superficie px-4 text-sm font-semibold shadow-cartao"
    >
      <span className="inline-flex items-center gap-2.5">
        <Icone nome={icone} /> {texto}
      </span>
      <Icone nome="seta" className="text-pedra-400" />
    </a>
  );
}

/** Perfil, atalhos que a barra de baixo não comporta e os direitos do titular (LGPD, §2.15). */
export function PaginaDePerfil() {
  const api = useApi();
  const { eu, equipe, pode, trocarEquipe, sair } = useSessao();
  const [mensagem, setMensagem] = useState<{ tom: "erro" | "sucesso"; texto: string } | null>(null);
  const [confirmando, setConfirmando] = useState(false);

  async function exportar() {
    try {
      baixarArquivo(await api.exportarMeusDados());
      setMensagem({ tom: "sucesso", texto: "Seus dados foram baixados." });
    } catch (e) {
      setMensagem({ tom: "erro", texto: mensagemDoErro(e) });
    }
  }

  async function excluirConta() {
    try {
      await api.excluirMinhaConta();
      sair();
    } catch (e) {
      setConfirmando(false);
      setMensagem({ tom: "erro", texto: mensagemDoErro(e) });
    }
  }

  return (
    <div className="flex max-w-xl flex-col gap-5">
      <header className="flex items-center gap-4">
        <Avatar nome={eu.pessoa.nome} tamanho={56} escuro />
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-extrabold">{eu.pessoa.nome}</h1>
          <p className="truncate text-sm text-pedra-600">{eu.pessoa.email}</p>
          <div className="mt-1 flex items-center gap-2 text-sm">
            <SeloDeCargo nome={equipe.cargo.nome} />{" "}
            <span className="text-pedra-600">{equipe.nome}</span>
          </div>
        </div>
      </header>

      {eu.equipes.length > 1 ? (
        <label className="flex flex-col gap-1 text-sm font-medium">
          Equipe ativa
          <select
            value={equipe.id}
            onChange={(e) => trocarEquipe(Number(e.target.value))}
            className="min-h-11 rounded-controle border border-pedra-300 bg-superficie px-3"
          >
            {eu.equipes.map((e) => (
              <option key={e.id} value={e.id}>
                {e.nome}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <nav aria-label="Mais" className="flex flex-col gap-2">
        {pode("ia:assistente") ? (
          <Atalho href="#/chat" icone="conversa" texto="Assistente" />
        ) : null}
        {pode("cargos:editar") ? (
          <Atalho href="#/cargos" icone="escudo" texto="Cargos e permissões" />
        ) : null}
        {pode("cargos:editar") ? (
          <Atalho href="#/ia" icone="brilho" texto="Inteligência artificial" />
        ) : null}
        {pode("formularios:publicar") ? (
          <Atalho href="#/exemplos" icone="documento" texto="Galeria de exemplos" />
        ) : null}
        <Atalho href="#/ajuda" icone="ajuda" texto="Central de ajuda" />
        <Atalho href="#/termos" icone="documento" texto="Termos de Uso" />
        <Atalho href="#/privacidade" icone="cadeado" texto="Política de Privacidade" />
      </nav>

      {mensagem ? <Aviso tom={mensagem.tom}>{mensagem.texto}</Aviso> : null}

      <section
        aria-labelledby="meus-dados"
        className="flex flex-col gap-3 rounded-cartao border border-pedra-200 bg-superficie p-4"
      >
        <h2 id="meus-dados" className="font-bold">
          Seus dados (LGPD)
        </h2>
        <p className="text-sm text-pedra-600">
          Você pode baixar o que guardamos sobre você ou apagar a sua conta. O trabalho da equipe
          fica, sem o seu nome.
        </p>
        <div className="flex flex-wrap gap-2">
          <Botao onClick={() => void exportar()}>
            <Icone nome="baixar" /> Baixar meus dados
          </Botao>
          {confirmando ? (
            <>
              <Botao variante="perigoSolido" onClick={() => void excluirConta()}>
                Confirmar exclusão
              </Botao>
              <Botao variante="fantasma" onClick={() => setConfirmando(false)}>
                Cancelar
              </Botao>
            </>
          ) : (
            <Botao variante="perigo" onClick={() => setConfirmando(true)}>
              Excluir minha conta
            </Botao>
          )}
        </div>
      </section>

      <Botao onClick={sair}>
        <Icone nome="sair" /> Sair
      </Botao>
    </div>
  );
}
