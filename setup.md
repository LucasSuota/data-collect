# Setup: instalar e usar o data-collect

Guia prático para subir o app na sua máquina (ou num servidor) e dar os primeiros passos. Para a visão geral do projeto, veja o [README](README.md); para escopo e regras, o [AGENTS.md](AGENTS.md).

- [1. O que você precisa](#1-o-que-você-precisa)
- [2. Instalação (Docker)](#2-instalação-docker)
- [3. Primeiro acesso](#3-primeiro-acesso)
- [4. Usando o app](#4-usando-o-app)
- [5. Linha de comando (CLI)](#5-linha-de-comando-cli)
- [6. Desenvolvimento do código](#6-desenvolvimento-do-código)
- [7. Produção](#7-produção)
- [8. Backup e restauração](#8-backup-e-restauração)
- [9. Problemas comuns](#9-problemas-comuns)

---

## 1. O que você precisa

Para **apenas rodar o app**:

| Item | Observação |
|---|---|
| Docker com Compose v2 (`docker compose`) | Docker Desktop no macOS/Windows, ou Docker Engine no Linux |
| Node.js 22.12 ou mais novo e `npm` | A interface roda fora do compose (`npm run dev`); não há proxy que a sirva |
| Portas `5173`, `8000`, `3001`, `3002`, `5433` e `8025` livres | Front (Vite), API, login e console do Logto, Postgres e Mailpit, todas no `127.0.0.1` |
| ~3 GB de RAM livres para os contêineres | Cada serviço tem limite de memória no compose |

Para **mexer no código** (seção 6) você também precisa de:

| Item | Versão |
|---|---|
| Python | 3.12 ou mais novo |
| [`uv`](https://docs.astral.sh/uv) | gerenciador de dependências do backend |
| Node.js e `npm` | Node 22.12 ou mais novo (front) |

Não é preciso instalar PostgreSQL, Logto nem servidor de e-mail: tudo sobe dentro do `docker compose`.

---

## 2. Instalação (Docker)

### 2.1. Clonar e configurar o `.env`

```bash
git clone <url-do-repositorio> data-collect
cd data-collect
cp .env.example .env
```

Edite o `.env`. Em desenvolvimento, só estes campos precisam de atenção:

| Variável | O que colocar |
|---|---|
| `POSTGRES_PASSWORD` | Uma senha para o dono do banco (o compose **recusa subir** sem ela) |
| `FORMS_APP_PASSWORD` | Outra senha, do papel `forms_app` que a API usa (também obrigatória) |
| `FORMS_ADMIN_EMAIL` | **Seu e-mail.** É quem vira o primeiro administrador |
| `FORMS_EQUIPE_INICIAL` | Nome da primeira equipe (padrão: `Minha equipe`) |

Os demais valores já funcionam em desenvolvimento: `APP_URL=http://localhost:5173`, `AUTH_URL=http://localhost:3001`, `API_URL=http://localhost:8000` e o e-mail de teste vai para o Mailpit. Não há proxy nem certificado em desenvolvimento.

> O `.env` **nunca** vai para o git. Ele já está no `.gitignore`.

> **IA é opcional.** Sem `FORMS_CHAVE_MESTRA` e sem chave de LLM o app funciona inteiro; só o gerador de formulários, o resumo e o chatbot ficam indisponíveis (a seção 4.7 explica como ligar).

### 2.2. Subir tudo

```bash
docker compose up -d --build
```

A primeira subida demora alguns minutos (build das imagens e provisionamento do Logto). Para acompanhar:

```bash
docker compose ps                 # todos devem ficar "running"/"healthy"; logto-setup termina com "exited (0)"
docker compose logs -f api
```

O que sobe:

| Serviço | Papel |
|---|---|
| `postgres` | PostgreSQL 16 com `pgvector` (em desenvolvimento também em `127.0.0.1:5433`) |
| `logto` | Login (OIDC): e-mail e senha, verificação e recuperação de senha |
| `logto-setup` | Configura o Logto sozinho e termina; roda em toda subida, sem estragar nada |
| `api` | Backend FastAPI (as migrações do banco são aplicadas na subida) |
| `backup` | `pg_dump` diário, com retenção de 14 dias |
| `mailpit` | Só em desenvolvimento: caixa de e-mail de teste em <http://localhost:8025> |

**A interface não está no compose.** Com a pilha no ar, publique a configuração que o `logto-setup` gerou (traz o id do aplicativo desta instalação) e suba o Vite:

```bash
docker run --rm -v data-collect_config:/config alpine cat /config/frontend-config.json > frontend/public/config.json
cd frontend && npm ci && npm run dev    # http://localhost:5173
```

O `frontend/public/config.json` é ignorado pelo git. Em vez dele, dá para usar as variáveis `VITE_*` (seção 6.2).

### 2.3. Pegar o link do primeiro administrador

Na primeira subida de uma instalação vazia, a API cria a equipe e **escreve no log o link de convite** do administrador (ele aparece uma única vez; o banco guarda só o hash):

```bash
docker compose logs api | grep convite
# Primeiro administrador: abra /convite/<token> no app para criar a conta.
```

O link completo é `http://localhost:5173/convite/<token>` (suba a interface antes: seção 6.2, `npm run dev`).

---

## 3. Primeiro acesso

1. Abra o link do convite (`http://localhost:5173/convite/<token>`).
2. Crie sua conta: e-mail, senha (mínimo de 10 caracteres) e marque o aceite dos **Termos de Uso** e da **Política de Privacidade**.
3. O Logto envia um e-mail de verificação. Em desenvolvimento ele chega no Mailpit: <http://localhost:8025>. Clique no link.
4. Pronto: você entra como **Administrador** da equipe, e um passeio rápido mostra as telas principais (dá para pular e rever depois).

Quem não foi convidado até consegue criar conta no Logto, mas **não entra em equipe nenhuma**: o app responde 403. O acesso é só por convite.

---

## 4. Usando o app

### 4.1. Criar o primeiro formulário

Em **Formulários**:

- **Começar com um exemplo:** importa modelos prontos (corpo de prova de concreto, inspeção de obra e a cadeia `ensaio_umidade` → `proctor` → `densidade_insitu`). É o jeito mais rápido de ver o app funcionando.
- **Criar formulário:** abre o construtor.

No construtor, arraste os tipos de campo da paleta para a lista (também funciona por teclado, toque e pelos botões "mover para cima/baixo"):

| Tipo | Para quê |
|---|---|
| Texto, Número (com unidade e casas decimais), Data, Seleção, Sim/não | Campos de entrada |
| Calculado | Resultado de uma fórmula sobre outros campos |
| Seção | Só agrupa visualmente |
| Referência | Aponta para um registro de **outro formulário** |
| Localização | Latitude e longitude (no celular, "Usar minha localização") |

Não há campo de foto nem anexo: o produto não faz upload de arquivo.

Use **Validar** para ver todos os erros da definição de uma vez e **Publicar versão N** quando estiver pronto. Cada publicação cria uma **versão imutável**; editar depois significa montar um rascunho da próxima versão. Registros antigos continuam presos à versão em que nasceram e nunca quebram.

### 4.2. Fórmulas (campos calculados)

Funções: `se`, `min`, `max`, `media`, `soma`, `dias`, e a constante `pi`. Exemplo (resistência de um corpo de prova):

```
carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)
```

Regras que valem a pena saber:

- **Vazio propaga:** se um campo usado na fórmula está vazio, o resultado fica vazio (sem erro).
- **Erro de cálculo** (como divisão por zero) aparece no próprio campo e não impede de salvar o registro.
- Datas aceitam `data ± dias(n)`; a diferença entre duas datas dá o número de dias.
- Texto, seleção, seção e localização não entram em fórmulas.
- Quem calcula é sempre o servidor. O que aparece enquanto você digita é só uma prévia.

O guia completo está em [ajuda/formulas.md](ajuda/formulas.md) (também disponível na Central de ajuda dentro do app).

### 4.3. Preencher e consultar registros

1. Toque em **Novo registro** (o botão **+**), escolha o formulário e preencha. Campos calculados mostram o estado: **Conforme**, **Não conforme**, **Erro no cálculo** ou **Aguardando dados**.
2. Em **Registros**, veja os cartões (no celular) ou a tabela (telas largas), filtre por estado ou por campo e abra um registro para editar.
3. Se duas pessoas editam o mesmo registro ao mesmo tempo, quem salva depois recebe um aviso (409) dizendo quem alterou e quando, para não sobrescrever o trabalho do outro.
4. Cada alteração fica no **histórico** do registro (para quem tem essa permissão).

### 4.4. Relação entre formulários

Um formulário pode depender de outro: um campo do tipo **Referência** aponta para um registro do formulário de origem, e a origem escolhe quais campos **compartilha**. Nas fórmulas eles aparecem como `<referência>__<campo>` (por exemplo, `ensaio__umidade`).

- Ao preencher, você escolhe o registro de origem numa lista com busca, ou cria/edita a origem numa gaveta sem sair da tela.
- Editar a origem recalcula os dependentes automaticamente.
- O **mapa de vínculos** (`#/mapa`) mostra quem aponta para quem e permite criar vínculos (exige a permissão de publicar formulários).

### 4.5. Exportar para o Excel

Na listagem de um formulário, use **Exportar**. O CSV sai pronto para o Excel em português (UTF-8 com BOM, separador `;`, vírgula decimal), respeitando os filtros da tela e as casas decimais de cada campo. Campo calculado com erro sai como `ERRO: <mensagem>`.

### 4.6. Equipe, cargos e convites

Em **Equipe** (permissões `equipe:*`):

- **Convidar:** informe o e-mail e o cargo. O convite vale 7 dias e o link chega por e-mail (em desenvolvimento, no Mailpit).
- **Cargos de partida:** Administrador, Gestor, Engenheiro, Técnico e Visualizador. Todos são editáveis, e há 17 permissões ao todo.
- **Desativar** uma pessoa tira o acesso na hora e mantém o nome e os registros dela.
- Sempre existe pelo menos um Administrador ativo: o último não pode ser removido nem rebaixado.

O que o seu cargo não permite some da tela ou aparece bloqueado com a explicação. Isso é só conveniência: o servidor sempre confere a permissão.

### 4.7. IA (opcional)

A IA vem **desligada por padrão** em cada equipe.

1. No `.env`, gere e preencha a chave-mestra que cifra as chaves de IA no banco:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Cole em `FORMS_CHAVE_MESTRA` e **guarde essa chave fora do backup do banco**.
2. Reinicie a API: `docker compose up -d api`.
3. Como administrador, abra as configurações de IA da equipe, leia o aviso (para onde os dados vão e qual provedor), aceite e informe o provedor (Anthropic ou qualquer API compatível com OpenAI, como Ollama, vLLM, OpenRouter ou Groq), o modelo e a chave. Há um botão de testar a conexão.
4. Com a IA ligada: **Criar com IA** no construtor, resumo de registros e o chatbot.

A IA nunca calcula: o código calcula e confere todo número que o texto citar. Campos com `"ia": false` na definição nunca vão para a IA. Detalhes em [ajuda/privacidade-e-ia.md](ajuda/privacidade-e-ia.md).

### 4.8. Instalar como app (PWA)

No celular, abra o endereço do app no navegador e use "Adicionar à tela inicial". O PWA guarda só os arquivos estáticos: **não há uso offline de dados**, então é preciso estar conectado para preencher.

### 4.9. Seus dados (LGPD)

No **Perfil** você baixa seus dados ("Baixar meus dados") ou exclui sua conta. A autoria dos registros vira anônima e o trabalho da equipe permanece. Quem é o único Administrador de uma equipe com outras pessoas precisa antes passar o cargo adiante.

---

## 5. Linha de comando (CLI)

A CLI é para quem **administra o servidor**; ela não é um atalho para driblar permissões. Dentro do compose:

```bash
docker compose exec api forms --help
docker compose exec api forms migrar
docker compose exec api forms criar-equipe "Outra equipe" --email pessoa@exemplo.com
```

Os comandos que mexem em dados exigem `--equipe <id>` e `--usuario <id>` (ou as variáveis `FORMS_EQUIPE` e `FORMS_USUARIO`):

```bash
docker compose exec api forms --equipe 1 --usuario 1 importar-template templates/corpo_de_prova.json
docker compose exec api forms --equipe 1 --usuario 1 listar
docker compose exec api forms --equipe 1 --usuario 1 listar corpo_de_prova
docker compose exec -T api forms --equipe 1 --usuario 1 exportar corpo_de_prova > registros.csv   # CSV sai na entrada padrão; o redirecionamento grava no seu computador
docker compose exec -T api forms --equipe 1 --usuario 1 criar-registro corpo_de_prova --dados - < dados.json
docker compose exec api forms --equipe 1 --usuario 1 reindexar-ia
```

O `importar-sqlite` (que migra o `forms.db` da versão antiga) lê um arquivo do disco do contêiner, então o arquivo precisa estar lá. Uma forma é copiá-lo antes:

```bash
docker compose cp forms.db api:/tmp/forms.db
docker compose exec api forms --equipe 1 --usuario 1 importar-sqlite /tmp/forms.db
```

| Comando | O que faz |
|---|---|
| `migrar` | Aplica as migrações pendentes do banco |
| `criar-equipe` | Cria uma equipe e o convite do primeiro administrador |
| `importar-template` | Cria formulários a partir de arquivos JSON de `templates/` |
| `importar-sqlite` | Importa o `forms.db` da versão anterior para uma equipe vazia |
| `reindexar-ia` | Reindexa registros e definições para o assistente |
| `listar` | Lista formulários, ou os registros de um formulário |
| `criar-registro` | Cria um registro a partir de um JSON |
| `exportar` | Exporta os registros em CSV |

---

## 6. Desenvolvimento do código

### 6.1. Backend

```bash
uv sync                               # instala as dependências do backend
docker compose up -d postgres         # os testes usam Postgres real em 127.0.0.1:5433
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Por padrão os testes procuram o banco `forms_test` com o usuário e a senha `forms`. Se o seu `.env` usa outra senha, aponte para o seu banco com `FORMS_TEST_DSN`:

```bash
FORMS_TEST_DSN="postgresql://forms:<sua-senha>@127.0.0.1:5433/forms_test" uv run pytest
```

Nenhum teste faz chamada de rede nem precisa de chave de API: o LLM e o Logto são sempre substituídos por falsos.

### 6.2. Frontend

Com a pilha no ar (`docker compose up -d`), em outro terminal:

```bash
cd frontend
npm ci
npm run dev                           # http://localhost:5173
```

O Vite chama a API usando `VITE_API_URL`, `VITE_LOGTO_ENDPOINT`, `VITE_LOGTO_APP_ID` e `VITE_LOGTO_RESOURCE`. No compose de desenvolvimento o `logto-setup` já libera `http://localhost:5173` como origem permitida.

Antes de abrir um PR do front:

```bash
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

Se a API mudar o contrato, regenere os tipos TypeScript (eles são gerados do OpenAPI, nunca escritos à mão): `npm run api:tipos`.

### 6.3. Testes ponta a ponta (Playwright)

Contra a pilha completa no ar, em viewport de celular e de desktop:

```bash
cd frontend
npm run e2e:instalar                  # uma vez: baixa o Chromium
npm run e2e
```

### 6.4. Ferramentas úteis em desenvolvimento

| O que | Onde |
|---|---|
| Caixa de e-mail de teste (verificação e convites) | <http://localhost:8025> |
| Console administrativo do Logto | <http://localhost:3002> |
| Login (Logto) | <http://localhost:3001> |
| API | <http://localhost:8000> |
| Postgres | `127.0.0.1:5433` (porta configurável em `POSTGRES_PORTA`) |
| Swagger da API (`/docs`) | só em desenvolvimento; fechado em produção |

---

## 7. Produção

Em produção use **só o arquivo principal** (o `docker-compose.override.yml` abre Postgres, Mailpit e console do Logto no localhost, e não deve ir junto):

```bash
docker compose -f docker-compose.yml up -d --build
```

Antes de subir, ajuste o `.env`:

| Variável | O que colocar |
|---|---|
| `APP_URL`, `AUTH_URL`, `API_URL` | Endereços públicos do front, do login e da API (com `https://`) |
| `SMTP_*` | Seu servidor de e-mail real (o Mailpit não existe em produção) |
| `POSTGRES_PASSWORD`, `FORMS_APP_PASSWORD` | Senhas fortes e únicas |
| `FORMS_CHAVE_MESTRA` | Chave Fernet (só se for usar IA), guardada **fora** do backup |

> **Atenção: a produção ainda não está pronta.** O repositório não tem proxy: nada serve o front, termina o HTTPS nem limita requisições por IP, e o compose principal não publica porta nenhuma. Antes de expor o app, coloque na frente um proxy reverso com HTTPS (front estático, API, login, limite de taxa, CSP e HSTS). A decisão está em aberto (AGENTS.md §4.1).

Lembretes importantes:

- **Não há proteção contra DDoS volumétrico**: por decisão do projeto, não existe serviço de borda (CDN/WAF) na frente. Sem proxy, também não há limite de requisições por IP.
- Os textos de `legal/` (Termos e Política) são rascunhos e **precisam de revisão jurídica** antes de produção. Preencha também o controlador e o encarregado (DPO) em `legal/privacidade.md`.
- A lista completa de verificação (segredos, `fail2ban`, retenção, plano de incidente) está em [docker/OPERACAO.md](docker/OPERACAO.md).

---

## 8. Backup e restauração

O serviço `backup` grava um `pg_dump` diário (do banco do app e do Logto) no volume `backups`, mantendo 14 dias (`BACKUP_RETENCAO_DIAS`).

```bash
docker compose exec backup ls /backups        # forms-AAAA-MM-DD.dump e logto-AAAA-MM-DD.dump
```

Para restaurar, copie o arquivo desejado para fora do volume e alimente o `pg_restore`:

```bash
docker compose cp backup:/backups/forms-AAAA-MM-DD.dump ./forms.dump
docker compose exec -T postgres pg_restore -U forms -d forms --clean < forms.dump
```

A chave-mestra (`FORMS_CHAVE_MESTRA`) **não** vai no backup. Sem ela, as chaves de IA cadastradas ficam ilegíveis e precisam ser cadastradas de novo.

---

## 9. Problemas comuns

| Sintoma | Causa provável e solução |
|---|---|
| `docker compose up` falha com "defina POSTGRES_PASSWORD no .env" | Faltou preencher `POSTGRES_PASSWORD` ou `FORMS_APP_PASSWORD` no `.env` |
| Porta `5173`, `8000`, `3001` ou outra já em uso | Pare o outro serviço. A `5173` é fixa no Vite de propósito (CORS e redirecionamento do login); a `5433` do Postgres muda com `POSTGRES_PORTA` |
| `grep convite` não mostra nada | O convite só é escrito na **primeira** subida de uma instalação vazia, com `FORMS_ADMIN_EMAIL` preenchido. Depois disso, crie outra equipe com `forms criar-equipe` (seção 5) ou convide pela tela Equipe |
| Tela de login do app fica em skeleton, ou "O app não está configurado" | Confira `frontend/.env.local` (`VITE_API_URL`, `VITE_LOGTO_ENDPOINT`, `VITE_LOGTO_APP_ID`, `VITE_LOGTO_RESOURCE`) e se o Logto responde em <http://localhost:3001>. O id do aplicativo está em `docker run --rm -v data-collect_config:/config alpine cat /config/frontend-config.json` |
| O e-mail de verificação não chega | Em desenvolvimento ele não sai da máquina: abra o Mailpit em <http://localhost:8025> |
| Mudei a senha no `.env` e o banco recusa | O `.env` só vale na criação do volume. Troque também no banco (`ALTER ROLE ...`) ou, **se puder perder os dados**, apague os volumes com `docker compose down -v` |
| Quero recomeçar do zero (perde tudo) | `docker compose down -v && docker compose up -d --build` |
| `uv run pytest` não conecta | Suba o Postgres (`docker compose up -d postgres`) e confira a senha com `FORMS_TEST_DSN` (seção 6.1) |
| Erro 401 com `token_expirado` na API | O token dura 10 minutos; o app renova sozinho. Em chamadas manuais (`curl`), pegue um token novo |
| Erro 403 "termos pendentes" | Os Termos ou a Política mudaram de versão: aceite de novo na tela que aparece |
| Reportar um erro | Anexe o cabeçalho `X-Request-Id` da resposta; os logs não têm dado pessoal, e esse identificador é como se acha a requisição |

Mais ajuda dentro do próprio app, na **Central de ajuda**, ou direto nos guias em [ajuda/](ajuda/).
