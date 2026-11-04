import { useState, type ReactNode } from "react";
import { ErroDaApi, type Eu } from "../api/cliente";
import { useApi } from "../api/contexto";
import { Aviso, Botao, Esqueleto, Icone, Marca } from "../ui";

/** Moldura das telas de antes do login: marca, título e um cartão no polegar. */
export function MolduraDeEntrada({
  titulo,
  subtitulo,
  children,
  rodape,
}: {
  titulo: string;
  subtitulo?: string;
  children?: ReactNode;
  rodape?: ReactNode;
}) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-6 px-4 py-8">
      <Marca className="text-xl" />
      <div className="mt-6 flex flex-col gap-2">
        <h1 className="text-4xl font-extrabold">{titulo}</h1>
        {subtitulo ? <p className="text-pedra-600">{subtitulo}</p> : null}
      </div>
      {children ? (
        <div className="flex flex-col gap-4 rounded-cartao border border-pedra-200 bg-superficie p-5 shadow-cartao">
          {children}
        </div>
      ) : null}
      {rodape ? (
        <p className="mt-auto flex items-start gap-2 pt-8 text-sm text-pedra-600">{rodape}</p>
      ) : null}
    </main>
  );
}

/** O esqueleto da tela que vai aparecer, para a página não "pular" quando a sessão chega. */
export function TelaDeCarregamento() {
  return (
    <div
      role="status"
      aria-label="Carregando"
      className="mx-auto flex max-w-md flex-col gap-4 px-4 py-8"
    >
      <Esqueleto className="h-6 w-40" />
      <Esqueleto className="mt-6 h-10 w-56" />
      <Esqueleto className="h-4 w-72" />
      <Esqueleto className="mt-4 h-48 w-full rounded-cartao" />
    </div>
  );
}

export function TelaDeEntrada({ aoEntrar }: { aoEntrar: () => void }) {
  return (
    <MolduraDeEntrada
      titulo="Entrar"
      subtitulo="Use o e-mail do convite que você recebeu."
      rodape={
        <>
          <Icone nome="cadeado" className="mt-0.5 shrink-0" />
          <span>
            O acesso é por convite. Se ainda não recebeu o seu, peça ao administrador da sua equipe.
          </span>
        </>
      }
    >
      <Botao variante="primario" className="w-full" onClick={aoEntrar}>
        Entrar com e-mail e senha
      </Botao>
      <p className="text-center text-sm text-pedra-600">
        Você vai para a tela segura de login e volta para cá.{" "}
        <a href="#/termos" className="text-sinal-500 underline underline-offset-2">
          Termos
        </a>{" "}
        e{" "}
        <a href="#/privacidade" className="text-sinal-500 underline underline-offset-2">
          Privacidade
        </a>
        .
      </p>
    </MolduraDeEntrada>
  );
}

export function TelaDeErro({ mensagem, aoTentar }: { mensagem: string; aoTentar: () => void }) {
  return (
    <MolduraDeEntrada titulo="Algo deu errado">
      <Aviso tom="erro">{mensagem}</Aviso>
      <Botao onClick={aoTentar}>Tentar de novo</Botao>
    </MolduraDeEntrada>
  );
}

const NOMES_DOS_DOCUMENTOS: Record<string, { rotulo: string; href: string }> = {
  termos: { rotulo: "Termos de Uso", href: "#/termos" },
  privacidade: { rotulo: "Política de Privacidade", href: "#/privacidade" },
};

/** Aceite (ou reaceite, quando a versão do documento mudou) antes de continuar (AGENTS.md §2.15). */
export function TelaDeTermos({
  eu,
  aoAceitar,
  aoSair,
}: {
  eu: Eu;
  aoAceitar: () => Promise<void>;
  aoSair: () => void;
}) {
  const api = useApi();
  const [aceito, setAceito] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    try {
      await api.aceitarTermos(eu.termos_pendentes);
      await aoAceitar();
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Não foi possível registrar o aceite.");
      setEnviando(false);
    }
  }

  return (
    <MolduraDeEntrada
      titulo="Antes de continuar"
      subtitulo="Para usar o data-collect, leia e aceite os documentos abaixo."
    >
      <ul className="flex flex-col gap-2">
        {eu.termos_pendentes.map((id) => {
          const documento = NOMES_DOS_DOCUMENTOS[id];
          return (
            <li key={id}>
              <a
                href={documento?.href ?? "#/termos"}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sinal-500 underline underline-offset-2"
              >
                {documento?.rotulo ?? id}
                <Icone nome="abrir" tamanho={14} />
              </a>
            </li>
          );
        })}
      </ul>
      <label className="flex min-h-11 items-start gap-3 text-sm">
        <input
          type="checkbox"
          checked={aceito}
          onChange={(e) => setAceito(e.target.checked)}
          className="mt-0.5 size-5 accent-sinal-500"
        />
        <span>Li e aceito os documentos acima.</span>
      </label>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <Botao
        variante="primario"
        disabled={!aceito}
        carregando={enviando}
        onClick={() => void confirmar()}
      >
        Continuar
      </Botao>
      <Botao variante="fantasma" onClick={aoSair}>
        Sair
      </Botao>
    </MolduraDeEntrada>
  );
}

export function TelaSemEquipe({ aoSair }: { aoSair: () => void }) {
  return (
    <MolduraDeEntrada
      titulo="Você ainda não está em uma equipe"
      subtitulo="O acesso é por convite: abra o link que a pessoa administradora da sua equipe enviou."
    >
      <Botao onClick={aoSair}>Sair</Botao>
    </MolduraDeEntrada>
  );
}
