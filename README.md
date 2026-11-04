# data-collect

Aplicação **web** (mobile-first) para **montar formulários por definição JSON**, preenchê-los e guardar os registros em PostgreSQL, em **equipes** com **cargos e permissões**, auto-hospedada com `docker compose`. Serve para inspeção de obra, ensaios de laboratório, checklists ou qualquer cadastro.

Os campos calculados usam fórmulas avaliadas por um avaliador próprio sobre `ast`, sem `eval`. Princípio central: **a IA nunca calcula, só busca e redige.** Quem calcula e valida é código determinístico.

O projeto é um monorepo: backend Python, interface web e a infraestrutura de implantação. O contexto completo (escopo, arquitetura, regras) está em [AGENTS.md](AGENTS.md), que é a fonte da verdade. O design de referência da interface é [frontend/data-collect-design-pattern.pdf](frontend/data-collect-design-pattern.pdf).

## Estado atual

Implementados e testados: o núcleo (fórmulas, validação, repositório, serviço), a API com autenticação e permissões por cargo, equipes e convites, histórico e concorrência otimista, LGPD, a CLI de operação, os módulos de IA (`ia/` e `rag/`), o `frontend/` e a infraestrutura (`docker-compose.yml`, `docker/`).

**Verificado à mão:** a pilha inteira sobe com `docker compose`, o `logto-setup` provisiona o Logto real e a API valida um token real dele (token de 10 minutos, `iss` e `aud` conferidos), o limite de requisições do proxy responde 429 e o backup é restaurável.
**Ainda não verificado:** nenhuma chamada a um LLM real foi feita (os testes usam um cliente falso), e os textos legais (`legal/`) precisam de revisão jurídica antes de produção.

## O que o sistema faz

- **Formulário é dado, não código.** A definição é um JSON versionado. Cada registro aponta para a versão com que nasceu, então evoluir um formulário nunca quebra o histórico. Versões publicadas são imutáveis; a próxima versão é montada num **rascunho** compartilhado pela equipe.
- **Tipos de campo:** texto, número (com unidade e `casas_decimais`), data, seleção, sim/não, calculado, seção (só visual), referência a outro formulário e localização. **Não há fotos nem anexos.**
- **Servidor é a fonte da verdade.** Valida, recalcula e confere a permissão sempre; o front mostra prévia e esconde o que o cargo não pode fazer, mas não decide nada.
- **Equipes, cargos e permissões.** 17 permissões, cargos editáveis, acesso por convite, isolamento entre equipes (recurso de outra equipe é 404) e Row Level Security no Postgres como defesa em profundidade.
- **Relação entre formulários.** Um formulário pode depender de outro por referência a um registro (ex.: `insitu` depende de `proctor`, que depende de `ensaio`). A origem escolhe quais campos compartilha; editar a origem recalcula os dependentes em cascata. O **mapa de vínculos** mostra e cria esses vínculos.
- **Registros:** criar, editar com controle de revisão (dois editores simultâneos geram 409 com a explicação), histórico de alterações, filtros por estado de conformidade, e exportação CSV pronta para o Excel em português.
- **Localização:** coordenadas validadas por faixa, com "Usar minha localização" no celular.
- **IA opcional, qualquer provedor:** Anthropic ou API compatível com OpenAI (Ollama, vLLM, OpenRouter, Groq…), configurado por equipe, desligado por padrão, com aviso e aceite. Gerador de formulários, resumo de registros conferido contra o banco e um **chatbot** sobre o app e sobre os dados, que usa ferramentas determinísticas (nunca gera SQL) e confere todo número que cita.
- **Primeiros passos:** passeio inicial, checklist marcado pelo estado real da equipe, galeria de exemplos e central de ajuda.
- **PWA instalável**, sem uso offline de dados: o service worker guarda só arquivos estáticos.

## Como subir tudo

Requer Docker. Em desenvolvimento:

```bash
cp .env.example .env     # preencha as senhas e FORMS_ADMIN_EMAIL
docker compose up -d --build
docker compose logs api | grep convite   # link do primeiro administrador
```

Abra `https://localhost` (o certificado é de uma CA interna do Caddy; aceite o aviso do navegador) e use o link de convite. O e-mail de verificação chega no Mailpit, em `http://localhost:8025`.

O que sobe:

| Serviço | Papel |
|---|---|
| `postgres` | PostgreSQL 16 com `pgvector` (rede interna; no desenvolvimento também em `127.0.0.1:5433`) |
| `logto` | Identidade (OIDC) auto-hospedada: e-mail e senha, verificação e recuperação |
| `logto-setup` | Provisiona o Logto como código e de forma idempotente (`python -m forms.provisionar_logto`) e escreve a configuração da API e do front |
| `api` | FastAPI, roda como usuário sem privilégios e conecta no banco como `forms_app` (sem `BYPASSRLS`) |
| `web` | Caddy: HTTPS, cabeçalhos de segurança, limite de taxa e de corpo, serve o front e `/api` |
| `backup` | `pg_dump` diário com retenção (volume `backups`) |
| `mailpit` | Só em desenvolvimento (`docker-compose.override.yml`): caixa de e-mail de teste |

**Só o proxy publica portas** (80 e 443). Em produção suba só o arquivo principal (`docker compose -f docker-compose.yml up -d`) e preencha o `.env` conforme o [.env.example](.env.example): `APP_HOST` e `AUTH_HOST` com dois nomes do seu domínio, SMTP real, `ACME_EMAIL`, `FORMS_CHAVE_MESTRA` (cifra a chave de IA de cada equipe; **guarde-a fora do backup do banco**).

Mapa de dados, retenção, `fail2ban`, rotação de segredos, plano de resposta a incidente e a lista para ir à produção: [docker/OPERACAO.md](docker/OPERACAO.md).

### Backup e restauração

```bash
docker compose exec backup ls /backups                       # forms-AAAA-MM-DD.dump e logto-AAAA-MM-DD.dump
docker compose exec -T postgres pg_restore -U forms -d forms --clean < forms-AAAA-MM-DD.dump
```

### Desenvolvimento do código

```bash
uv sync && cp .env.example .env
uv run pytest                                  # Postgres real em 127.0.0.1:5433 (docker compose up -d postgres)
uv run ruff check . && uv run ruff format --check .

cd frontend && npm ci
npm run dev                                    # http://localhost:5173 (a API libera CORS só para essa origem)
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
npm run e2e                                    # Playwright contra a pilha no ar (celular e desktop)
```

No `npm run dev` o front lê `VITE_API_URL`, `VITE_LOGTO_ENDPOINT`, `VITE_LOGTO_APP_ID` e `VITE_LOGTO_RESOURCE` (no compose ele lê `/config.json`, escrito pelo `logto-setup`).

## Exemplo de definição

Trecho do template de demonstração (controle de corpos de prova de concreto):

```json
{
  "campos": [
    {"id": "fck_mpa", "tipo": "numero", "rotulo": "fck especificado", "unidade": "MPa", "obrigatorio": true},
    {"id": "diametro_mm", "tipo": "numero", "rotulo": "Diâmetro", "unidade": "mm", "obrigatorio": true},
    {"id": "data_moldagem", "tipo": "data", "rotulo": "Data de moldagem", "obrigatorio": true},
    {"id": "carga_kn", "tipo": "numero", "rotulo": "Carga de ruptura", "unidade": "kN"},
    {"id": "ruptura_28d", "tipo": "calculado", "rotulo": "Ruptura aos 28 dias",
     "formula": "data_moldagem + dias(28)"},
    {"id": "resistencia_mpa", "tipo": "calculado", "rotulo": "Resistência", "unidade": "MPa", "casas_decimais": 1,
     "formula": "carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)"},
    {"id": "conforme", "tipo": "calculado", "rotulo": "Conforme?",
     "formula": "resistencia_mpa >= fck_mpa"}
  ]
}
```

Um campo calculado sempre chega ao front como `{"valor": ..., "erro": ...}`, para o erro de uma fórmula aparecer no campo sem derrubar o registro.

## Como as fórmulas funcionam

- **Segurança:** o texto é lido com `ast.parse` e percorrido com uma lista de permissão de nós. Nunca `eval`, `exec` nem `compile`. Atributos, subscripts, lambdas e imports são rejeitados.
- **Funções:** `se`, `min`, `max`, `media`, `soma`, `dias` e a constante `pi`.
- **Números:** sempre `Decimal`, nunca `float`. Na API e no banco, número vai como string (`"25.50"`) para não perder precisão no JavaScript.
- **Vazio propaga:** se um operando está vazio, o resultado é vazio, sem erro. Assim uma média parcial nunca vira um "conforme" falso.
- **Tipos checados ao publicar:** `data * 2`, `data + data` ou `se` com ramos de tipos diferentes são rejeitados antes de qualquer registro existir. Datas aceitam `data ± dias(n)`, `data − data` (resulta em dias) e comparações entre datas.
- **Dependências:** a ordem de cálculo vem do grafo de dependências. Ciclo entre campos, ou entre formulários, é rejeitado ao publicar, citando os envolvidos.
- **Erros de execução** (divisão por zero) ficam no campo; erros de definição impedem a publicação, com mensagem localizada pelo `id` do campo.

## Arquitetura

```
frontend/      React + TypeScript + Vite + Tailwind (+ Playwright em e2e/)
src/forms/     backend Python
  models.py  tipos_campo.py  formulas.py  validacao.py  exportacao.py
  banco.py  repositorio*.py  migracoes/*.sql
  servico.py (+ servico_*.py)  permissoes.py  segredos.py  legal.py  ajuda.py
  api.py (+ api_*.py)  auth.py  logto.py  provisionar_logto.py  cli.py
  rag/  ia/                                  (opcionais; achados pelo nome em api_extensoes.py)
templates/     corpo_de_prova.json  inspecao_obra.json
ajuda/ legal/ docs/   guias, textos legais e procedimentos em Markdown
docker/        Dockerfiles, Caddyfile, backup, init do Postgres
tests/
```

Resumo de cada pasta com código: [src/forms/README.md](src/forms/README.md), [frontend/README.md](frontend/README.md) e [templates/README.md](templates/README.md).

A dependência sempre aponta para baixo:

```
api.py / cli.py  →  servico.py  →  validacao.py, formulas.py, tipos_campo.py, segredos.py
                                →  repositorio.py  →  psycopg  →  PostgreSQL
```

- Regra de negócio fica em `servico.py` e abaixo; `api.py` e `cli.py` são camadas finas.
- Só os módulos `repositorio*.py` falam SQL, sempre parametrizado (a regra `S608` do `ruff` e um teste de varredura garantem). Sem ORM.
- Pydantic só na borda da API. O domínio usa `dataclasses`.
- Os módulos opcionais (`rag/`, `ia/`) dependem do núcleo, nunca o contrário.

## API

O contrato é o OpenAPI gerado pelo FastAPI (`/docs`, só em desenvolvimento); os tipos TypeScript do front são gerados dele. Toda chamada leva `Authorization: Bearer <token do Logto>` e, quando a pessoa está em mais de uma equipe, `X-Equipe`. Erros têm formato uniforme (`{"detalhe": "...", "erros": [{"campo": "...", "mensagem": "..."}], "codigo": "..."}`) com mensagens em português.

| Área | Endpoints |
|---|---|
| Identidade | `GET /eu`, `GET /eu/exportar`, `DELETE /eu` (LGPD), `GET`/`PUT /eu/onboarding`, `GET`/`POST /consentimentos`, `GET /legal` |
| Equipe | `GET`/`PUT /equipe`, `GET /membros`, `PUT /membros/{id}/cargo`, `POST /membros/{id}/desativar`, `GET`/`POST /convites`, `POST /convites/{token}/aceitar`, `GET`/`POST /cargos`, `PUT`/`DELETE /cargos/{id}`, `GET /catalogo/permissoes` |
| Formulários e versões | `POST /formularios`, `POST /formularios/lote`, `GET /formularios`, `GET`/`DELETE /formularios/{id}`, `POST /formularios/{id}/duplicar`, `POST`/`GET /formularios/{id}/versoes`, `GET`/`PUT`/`DELETE /formularios/{id}/rascunho` e `POST .../rascunho/publicar` |
| Construtor | `POST /definicoes/validar`, `POST /definicoes/previa`, `GET /catalogo` |
| Pastas | `POST`/`GET /pastas`, `PUT`/`DELETE /pastas/{id}`, `PUT /formularios/{id}/pasta` |
| Registros | `POST /formularios/{id}/registros`, `GET`/`PUT`/`DELETE /registros/{id}` (o `PUT` exige a `revisao` lida), `GET /registros/{id}/historico`, `GET /registros/recentes` |
| Consulta | `GET /formularios/{id}/registros` (versão, filtros, `meus`, paginação), `.../contagens` (por estado), `.../exportar` (CSV), `GET /busca` |
| Início e ajuda | `GET /notificacoes`, `GET /templates`, `POST /templates/importar`, `GET /ajuda` |
| IA (opcional) | `GET`/`PUT /ia` (configuração da equipe), `POST /ia/testar`, `POST /ia/reindexar`, `GET /ia/uso`, `POST /definicoes/gerar`, `POST /formularios/{id}/resumo`, `POST /chat` (SSE) e `GET`/`DELETE /chat/conversas` |

## Segurança

- **Rede:** só o proxy publica portas, com HTTPS e HSTS; API, Postgres e Logto ficam na rede interna.
- **Autenticação:** JWT do Logto validado em todo endpoint (assinatura pelo JWKS, `iss`, `aud`, `exp`), token de 10 minutos com refresh rotativo. Cargo e permissões vêm **do banco a cada requisição**, nunca do token nem do front.
- **Isolamento:** todo acesso filtra por `grupo_id`; testes de vazamento percorrem todas as rotas que recebem id. RLS no Postgres com um papel sem `BYPASSRLS`.
- **Segredos:** senha é do Logto (hash); token de convite só como hash SHA-256; chave de LLM cifrada com Fernet e nunca devolvida.
- **Limites:** taxa por IP no proxy (600 por minuto na API, 60 no login), corpo de no máximo 1 MB (413), limites por pessoa e por equipe nos endpoints caros (429 com `Retry-After`), timeouts contra conexão lenta e limites de CPU e memória por contêiner. Para bloquear reincidentes no servidor, use o `fail2ban` lendo o log do Caddy. **Não cobre DDoS volumétrico**: por decisão, não há serviço de borda na frente.
- **LGPD:** aceite versionado dos Termos e da Política, exportação e exclusão dos dados da pessoa, IA desligada por padrão, campos com `"ia": false` nunca vão ao índice nem ao prompt, e logs sem e-mail, valores de campo, corpo, query string nem token (uma linha por requisição com o molde da rota e um `X-Request-Id`).
- **IA:** a saída do LLM é dado não confiável (validada antes de aparecer) e o conteúdo de registro é entrada não confiável (prompt injection). O LLM nunca gera SQL.
- Exportação CSV neutraliza injeção de fórmula em células de texto; o front renderiza Markdown sem HTML cru.

## Qualidade

- **TDD** no núcleo, com `formulas.py` e `validacao.py` primeiro e mais fundo. O LLM é sempre substituído por um cliente falso nos testes, que nunca fazem chamada de rede. O Logto real nunca é usado nos testes: o token de teste é assinado com chaves geradas no próprio teste.
- **CI** (GitHub Actions): `ruff`, `pytest` contra um PostgreSQL com `pgvector` (Linux), build das imagens, validação do Caddyfile e o job do front (tipos gerados do OpenAPI, lint, formatação, typecheck, testes e build).
- **Agentes** (`agents/`): o `orchestrator` recebe toda tarefa, confere o escopo e aciona `issue-creator`, `issue-planner`, `issue-coder`, `issue-reviewer`, `doc-writer` e `git-manager`. O `doc-writer` mantém um `README.md` de resumo em cada pasta com código.
- **`AI_NOTES.md`** registra os erros reais da IA durante a construção.

## Próximos passos (fora do escopo atual)

- Grupo repetível (tabela de linhas) e visibilidade condicional.
- Consulta espacial (distância, raio) e mapas sobre as coordenadas.
- Renomear formulário e migrar um registro para outra versão.
- Filtro por número e por data na listagem.
- Fórmulas com campos de texto e seleção; função que ignora vazios (`media_preenchidos`).
- Modo offline com sincronização de dados e edição simultânea em tempo real.
- Notificação por push ou e-mail, SSO corporativo (SAML), criação de equipes por autoatendimento e escopo de cargo por pasta.
- Serviço de borda (CDN, WAF) para mitigar ataque volumétrico: hoje o produto é totalmente local.
- Fotos e anexos foram **removidos do produto** por decisão do autor.
