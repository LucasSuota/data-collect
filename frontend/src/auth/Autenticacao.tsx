import { LogtoProvider, useHandleSignInCallback, useLogto } from "@logto/react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { criarCliente, ErroDaApi, type ClienteApi, type Eu } from "../api/cliente";
import { ApiProvider } from "../api/contexto";
import type { ConfigDoApp } from "../config";
import { useRota } from "../rotas";
import { PaginaDeConvite } from "./PaginaDeConvite";
import { PaginaLegal } from "./PaginaLegal";
import { ContextoDaSessao, criarSessao, escolherEquipe } from "./sessao";
import {
  TelaDeCarregamento,
  TelaDeEntrada,
  TelaDeErro,
  TelaDeTermos,
  TelaSemEquipe,
} from "./telas";

const CHAVE_DA_EQUIPE = "data-collect:equipe";
const CHAVE_DO_DESTINO = "data-collect:destino";
export const CHAVE_DO_CONVITE = "data-collect:convite";

function ler(chave: string, armazenamento: Storage = localStorage): string | null {
  try {
    return armazenamento.getItem(chave);
  } catch {
    return null; // modo privado ou armazenamento bloqueado: o app funciona sem lembrar
  }
}

function gravar(chave: string, valor: string | null, armazenamento: Storage = localStorage) {
  try {
    if (valor === null) armazenamento.removeItem(chave);
    else armazenamento.setItem(chave, valor);
  } catch {
    // idem: lembrar é conveniência, não requisito
  }
}

/**
 * Entrada do app: o login (Logto, OIDC) e a sessão. Só o front cuida de *mostrar* o que a pessoa
 * pode ver; quem barra é o servidor, que valida o token e lê cargo e permissões do banco a cada
 * requisição (AGENTS.md §2.12, §2.13).
 */
export function Autenticacao({ config, children }: { config: ConfigDoApp; children: ReactNode }) {
  const configDoLogto = useMemo(
    () => ({
      endpoint: config.logto.endpoint,
      appId: config.logto.appId,
      resources: [config.logto.resource],
    }),
    [config.logto],
  );
  return (
    <LogtoProvider config={configDoLogto}>
      <Porta config={config}>{children}</Porta>
    </LogtoProvider>
  );
}

function Porta({ config, children }: { config: ConfigDoApp; children: ReactNode }) {
  // O link de convite do servidor é um caminho (`/convite/<token>`); o app roteia por hash.
  if (window.location.pathname.startsWith("/convite/")) {
    const token = window.location.pathname.slice("/convite/".length);
    window.history.replaceState(null, "", `/#/convite/${token}`);
  }
  if (window.location.pathname === "/callback") return <Retorno />;
  return <PortaAutenticada config={config}>{children}</PortaAutenticada>;
}

function Retorno() {
  const { error } = useHandleSignInCallback(() => {
    const destino = ler(CHAVE_DO_DESTINO, sessionStorage) ?? "#/";
    gravar(CHAVE_DO_DESTINO, null, sessionStorage);
    window.location.replace(`/${destino}`);
  });
  if (error) {
    return (
      <TelaDeErro
        mensagem="Não foi possível concluir o login."
        aoTentar={() => window.location.replace("/")}
      />
    );
  }
  return <TelaDeCarregamento />;
}

function PortaAutenticada({ config, children }: { config: ConfigDoApp; children: ReactNode }) {
  const { isAuthenticated, isLoading, signIn, signOut, getAccessToken, clearAccessToken } =
    useLogto();
  const [rota] = useRota();
  // Lida só dentro de callbacks (o cabeçalho X-Equipe de cada chamada), nunca na renderização.
  const equipeAtiva = useRef<number | null>(Number(ler(CHAVE_DA_EQUIPE)) || null);

  // As funções do SDK mudam de identidade a cada render; o cliente guarda só a última.
  const sdk = useRef({ isAuthenticated, getAccessToken, clearAccessToken });
  useEffect(() => {
    sdk.current = { isAuthenticated, getAccessToken, clearAccessToken };
  });

  const cliente = useMemo(
    () =>
      // eslint-disable-next-line react-hooks/refs -- as refs só são lidas dentro das chamadas à API, nunca na renderização
      criarCliente({
        urlBase: config.apiBase,
        // Sem login o SDK não tem token: devolve nulo e a chamada segue sem Authorization (páginas
        // públicas). Não dá para confiar em `isAuthenticated` aqui: a ref dele só atualiza num efeito
        // do pai, depois dos efeitos dos filhos, que já estão pedindo dados.
        obterToken: async () => {
          try {
            return (await sdk.current.getAccessToken(config.logto.resource)) ?? null;
          } catch {
            return null;
          }
        },
        renovarToken: async () => {
          await sdk.current.clearAccessToken();
          return (await sdk.current.getAccessToken(config.logto.resource)) ?? null;
        },
        equipeId: () => equipeAtiva.current,
      }),
    [config, sdk, equipeAtiva],
  );

  const entrar = useCallback(
    (modo?: "signUp") => {
      gravar(CHAVE_DO_DESTINO, window.location.hash || "#/", sessionStorage);
      void signIn({
        redirectUri: `${window.location.origin}/callback`,
        ...(modo ? { interactionMode: modo } : {}),
      });
    },
    [signIn],
  );
  const sair = useCallback(() => {
    gravar(CHAVE_DA_EQUIPE, null);
    void signOut(`${window.location.origin}/`);
  }, [signOut]);

  // Quem já está logado e abre um convite: guarda o token e segue para o início, onde o aceite roda.
  const conviteDaRota = rota.nome === "convite" ? rota.token : null;
  useEffect(() => {
    if (isAuthenticated && conviteDaRota) {
      gravar(CHAVE_DO_CONVITE, conviteDaRota, sessionStorage);
      window.location.replace("/#/");
    }
  }, [isAuthenticated, conviteDaRota]);

  // Páginas públicas: os textos legais precisam abrir antes do login (e no aceite do cadastro).
  if (rota.nome === "termos" || rota.nome === "privacidade") {
    return (
      <ApiProvider cliente={cliente}>
        <PaginaLegal documento={rota.nome} />
      </ApiProvider>
    );
  }
  // `isLoading` também liga a cada busca de token do SDK; só a carga inicial (ainda sem login)
  // troca a tela. Senão a sessão inteira desmontaria e refaria `GET /eu` a cada renovação.
  if (isLoading && !isAuthenticated) return <TelaDeCarregamento />;
  if (!isAuthenticated) {
    if (rota.nome === "convite") {
      return (
        <PaginaDeConvite
          token={rota.token}
          autenticado={false}
          aoCriarConta={() => {
            gravar(CHAVE_DO_CONVITE, rota.token, sessionStorage);
            entrar("signUp");
          }}
          aoEntrar={() => {
            gravar(CHAVE_DO_CONVITE, rota.token, sessionStorage);
            entrar();
          }}
        />
      );
    }
    return <TelaDeEntrada aoEntrar={() => entrar()} />;
  }
  return (
    <ApiProvider cliente={cliente}>
      <SessaoIniciada cliente={cliente} equipeAtiva={equipeAtiva} sair={sair}>
        {children}
      </SessaoIniciada>
    </ApiProvider>
  );
}

type Estado =
  { tipo: "carregando" } | { tipo: "erro"; mensagem: string } | { tipo: "pronto"; eu: Eu };

function SessaoIniciada({
  cliente,
  equipeAtiva,
  sair,
  children,
}: {
  cliente: ClienteApi;
  equipeAtiva: React.RefObject<number | null>;
  sair: () => void;
  children: ReactNode;
}) {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [equipeId, setEquipeId] = useState<number | null>(
    () => Number(ler(CHAVE_DA_EQUIPE)) || null,
  );

  const carregar = useCallback(async () => {
    try {
      let eu = await cliente.eu();
      // Convite guardado antes do login: depois dos termos, a pessoa entra na equipe.
      const convite = ler(CHAVE_DO_CONVITE, sessionStorage);
      if (convite && eu.termos_pendentes.length === 0) {
        gravar(CHAVE_DO_CONVITE, null, sessionStorage);
        await cliente.aceitarConvite(convite);
        eu = await cliente.eu();
      }
      // A equipe vale para as chamadas seguintes já aqui, antes de qualquer tela pedir dados.
      const escolhida = escolherEquipe(eu, equipeAtiva.current);
      // eslint-disable-next-line react-hooks/immutability -- ref compartilhada com o cliente da API
      if (escolhida) equipeAtiva.current = escolhida.id;
      setEstado({ tipo: "pronto", eu });
    } catch (e) {
      setEstado({
        tipo: "erro",
        mensagem: e instanceof ErroDaApi ? e.message : "Não foi possível carregar sua conta.",
      });
    }
  }, [cliente, equipeAtiva]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial da sessão
    void carregar();
  }, [carregar]);

  const trocarEquipe = useCallback(
    (id: number) => {
      // eslint-disable-next-line react-hooks/immutability -- ref compartilhada com o cliente da API
      equipeAtiva.current = id;
      gravar(CHAVE_DA_EQUIPE, String(id));
      setEquipeId(id);
    },
    [equipeAtiva],
  );

  // `sair` muda de identidade a cada render do SDK; a sessão só pode mudar quando mudam os dados,
  // senão toda tela que depende de `pode` refaria suas chamadas a cada busca de token (laço!).
  const sairAtual = useRef(sair);
  useEffect(() => {
    sairAtual.current = sair;
  });
  const sairEstavel = useCallback(() => sairAtual.current(), []);

  const eu = estado.tipo === "pronto" ? estado.eu : null;
  const equipe = eu ? escolherEquipe(eu, equipeId) : null;
  const sessao = useMemo(
    () =>
      eu && equipe
        ? // eslint-disable-next-line react-hooks/refs -- `sairEstavel` só lê a ref ao ser chamado, nunca na renderização
          criarSessao(eu, equipe, { trocarEquipe, recarregar: carregar, sair: sairEstavel })
        : null,
    [eu, equipe, trocarEquipe, carregar, sairEstavel],
  );

  if (estado.tipo === "carregando") return <TelaDeCarregamento />;
  if (estado.tipo === "erro") {
    return (
      <TelaDeErro
        mensagem={estado.mensagem}
        aoTentar={() => {
          setEstado({ tipo: "carregando" });
          void carregar();
        }}
      />
    );
  }
  if (eu && eu.termos_pendentes.length > 0) {
    return <TelaDeTermos eu={eu} aoAceitar={carregar} aoSair={sairEstavel} />;
  }
  if (!equipe || !sessao) return <TelaSemEquipe aoSair={sairEstavel} />;
  return (
    <ContextoDaSessao.Provider key={equipe.id} value={sessao}>
      {children}
    </ContextoDaSessao.Provider>
  );
}
