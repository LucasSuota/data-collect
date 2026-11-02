# Notas sobre erros reais da IA

Registro honesto dos erros que a IA cometeu durante a construção: lógica errada, API inventada, teste que passa pelo motivo errado, número alucinado. Faz parte da defesa do projeto.

## Modelo de entrada

### AAAA-MM-DD — título curto
- **Pedido:** o que foi solicitado.
- **O que a IA fez de errado:**
- **Como foi detectado:**
- **Correção:**

## Entradas

### 2026-11-02 — arquivo de teste existente sobrescrito
- **Pedido:** acrescentar testes da nova rota `#/construtor/ia` ao front.
- **O que a IA fez de errado:** criou `frontend/src/rotas.test.ts` com `Write`/`write_text` sem checar se o arquivo já existia, e apagou os testes de rota que estavam lá (ida e volta de todas as rotas, a raiz e os caminhos inexistentes).
- **Como foi detectado:** `git status` mostrava `M frontend/src/rotas.test.ts` (modificado) quando se esperava um arquivo novo (`??`), e a contagem de testes ficou menor do que a soma esperada.
- **Correção:** `git checkout HEAD -- frontend/src/rotas.test.ts` e só então acrescentar os casos novos na tabela existente. Regra: antes de criar um arquivo de teste, `ls`/`git status` para ver se ele já existe.

### 2026-11-02 — teste que esperava o resultado errado do BM25
- **Pedido:** testar que, sem os embeddings da consulta, a busca híbrida cai no BM25 puro.
- **O que a IA fez de errado:** escreveu a expectativa à mão (`== [RUPTURA]`) supondo que só um trecho casaria com "corpos de prova aos 28 dias", mas "dias" também aparece no trecho da cura.
- **Como foi detectado:** o teste falhou na primeira execução (fase red).
- **Correção:** a expectativa passou a comparar com `IndiceBm25(...).buscar(...)` direto (mesmas pontuações), que é o que o teste realmente quer afirmar.

### 2026-11-02 — `sed` falho engolido por `&&` deixou um arquivo sem criar
- **Pedido:** criar `ia/extensao.py` e corrigir um comentário de lint em `api.py`.
- **O que a IA fez de errado:** encadeou `sed ... && cat > arquivo <<EOF`; o `sed` falhou (BSD sed no macOS não aceita o padrão com quebra de linha) e o arquivo nunca foi escrito, além de o heredoc ter uma linha de placeholder inútil.
- **Como foi detectado:** a saída trazia o erro do `sed` e o `ls` seguinte não mostrava `extensao.py`.
- **Correção:** o arquivo foi criado com a ferramenta de escrita, sem placeholder, e o ajuste do `api.py` foi feito com a ferramenta de edição.

### 2026-11-02 — conexão do SQLite usada em outra thread, escondida pelo TestClient
- **Pedido:** implementar a API (`obter_conexao` como dependência do FastAPI) com testes.
- **O que a IA fez de errado:** abriu o `sqlite3.connect` com o padrão (`check_same_thread=True`). O FastAPI executa a dependência (geradora, síncrona) numa thread do pool e usa e fecha a conexão em outras; o `sqlite3` levanta `ProgrammingError`. A suíte inteira passava porque o `TestClient` roda tudo numa thread só, e os `curl` manuais também passaram, porque o resultado depende de qual thread do pool pega a requisição.
- **Como foi detectado:** só ao rodar o app de verdade (Electron), pela saída do backend: dezenas de `ProgrammingError`, também no servidor de desenvolvimento. A primeira versão do teste de regressão passou sem a correção por outro motivo: depois do `join`, o id da thread foi reaproveitado e o `sqlite3` não percebeu a troca.
- **Correção:** `check_same_thread=False` (cada conexão serve a uma única requisição, em sequência) e um teste que mantém a thread que abriu viva enquanto outra usa e fecha a conexão; ele falha sem a correção. Lição: teste da API com `TestClient` não prova nada sobre threads, e é preciso rodar o app real.

