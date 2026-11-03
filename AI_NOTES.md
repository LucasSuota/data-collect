# Notas sobre erros reais da IA

Registro honesto dos erros que a IA cometeu durante a construção: lógica errada, API inventada, teste que passa pelo motivo errado, número alucinado. Faz parte da defesa do projeto.

## Modelo de entrada

### AAAA-MM-DD — título curto
- **Pedido:** o que foi solicitado.
- **O que a IA fez de errado:**
- **Como foi detectado:**
- **Correção:**

## Entradas

### 2026-11-02 — conexão SQLite da API quebrava com requisições em paralelo, e nenhum teste via
- **Pedido:** construir a API (`obter_conexao` como dependência com `yield`, endpoints síncronos) com testes de API.
- **O que a IA fez de errado:** abriu a conexão com `sqlite3.connect(caminho)` num gerador de dependência síncrono. O FastAPI roda a dependência e o endpoint no pool de threads, possivelmente em threads diferentes, e o `sqlite3` recusa o uso entre threads. Todos os testes usavam o `TestClient` de uma requisição por vez, em que as duas etapas caem na mesma thread, então a suíte inteira passava.
- **Como foi detectado:** o autor clicou em **Editar** no front e viu "Não foi possível conectar à API". O construtor faz 3 requisições em paralelo; o log do servidor mostrou `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
- **Correção:** `check_same_thread=False` em `abrir_conexao`, comentado (cada requisição tem a sua conexão, usada por uma etapa de cada vez). Teste de regressão novo (`tests/test_api_concorrencia.py`) com 60 requisições simultâneas no mesmo loop de eventos (`httpx.ASGITransport`), visto falhar (500) antes e passar depois. Lição: teste de API sequencial não cobre concorrência; o que o front faz em paralelo precisa de teste em paralelo.

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

