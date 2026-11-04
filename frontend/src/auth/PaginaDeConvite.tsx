import { Botao } from "../ui";
import { MolduraDeEntrada } from "./telas";

/** Quem abre o link de convite sem estar logado cria a conta (ou entra) e volta para aceitar. */
export function PaginaDeConvite({
  autenticado,
  aoCriarConta,
  aoEntrar,
}: {
  token: string;
  autenticado: boolean;
  aoCriarConta: () => void;
  aoEntrar: () => void;
}) {
  return (
    <MolduraDeEntrada
      titulo="Você foi convidado"
      subtitulo="Crie sua conta com o e-mail do convite para entrar na equipe."
    >
      <Botao variante="primario" onClick={aoCriarConta}>
        Criar minha conta
      </Botao>
      {!autenticado ? (
        <Botao variante="secundario" onClick={aoEntrar}>
          Já tenho conta: entrar
        </Botao>
      ) : null}
      <p className="text-sm text-pedra-600">
        Ao criar a conta você aceita os{" "}
        <a href="#/termos" className="text-sinal-500 underline underline-offset-2">
          Termos de Uso
        </a>{" "}
        e a{" "}
        <a href="#/privacidade" className="text-sinal-500 underline underline-offset-2">
          Política de Privacidade
        </a>
        .
      </p>
    </MolduraDeEntrada>
  );
}
