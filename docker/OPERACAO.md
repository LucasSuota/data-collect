# Operação, segurança e LGPD

Guia de quem **administra o servidor** do data-collect (não é conteúdo para quem usa o app). Complementa o [AGENTS.md](../AGENTS.md) (§2.15 e §12) e o [README](../README.md).

> Os textos em `legal/` são rascunhos e **precisam de revisão jurídica** antes de produção. Este documento descreve o que o sistema faz hoje, não substitui a política de privacidade.

## 1. Mapa de dados

Onde há dado pessoal, quem o vê e de onde ele sai.

| Onde | O que guarda | Observação |
|---|---|---|
| Logto (banco `logto`) | E-mail e **hash** da senha, verificação, sessões | O app **nunca** vê a senha. Credenciais e conta ficam só aqui |
| `usuarios` | `logto_sub`, nome, e-mail, último acesso | Nome vem do Logto; sem ele, vale a parte local do e-mail |
| `membros_grupo`, `cargos` | Quem está em qual equipe e com qual cargo | Isolamento por `grupo_id` (e Row Level Security) |
| `convites` | E-mail convidado, cargo, **hash** do token | O token em claro só existe na tela de quem convida e no link enviado |
| `consentimentos` | Pessoa, documento, versão e data do aceite | Sem IP |
| `registros` (`dados`) | O que as pessoas preenchem | Pode conter dado pessoal de terceiros, conforme o formulário. É da equipe |
| `historico_registro` | Valores anteriores, quem alterou e quando | Acompanha o registro |
| `documentos_ia`, `conversas_ia`, `mensagens_ia`, `uso_ia`, `config_ia_grupo` | Índice de texto, conversas do chat e a chave de LLM da equipe (**cifrada**) | Só existem se a equipe ligou a IA. Campo com `"ia": false` e `localizacao` nunca entram |
| `notificacoes`, progresso do passeio | Avisos dentro do app | Sem e-mail nem push |
| Backups (`pg_dump`) | Cópia de tudo acima | Sem a chave-mestra (§4) |

**Para onde os dados saem:** para lugar nenhum, por padrão. Com a IA ligada, trechos de formulários e registros vão ao provedor que a **equipe** configurou (o aviso e o aceite ficam registrados). O e-mail de verificação sai pelo SMTP configurado.

## 2. Retenção

| Dado | Quanto tempo |
|---|---|
| Backups | 14 dias (`BACKUP_RETENCAO_DIAS`) |
| Logs da API | Sem dado pessoal; guarde o tempo que sua operação exigir |
| Conversas do chat | Até a pessoa apagar (`DELETE /chat/conversas/{id}`) |
| Convite não aceito | Expira em 7 dias; o administrador pode revogar |
| Conta da pessoa | Até ela pedir a exclusão (`DELETE /eu`) |
| Registros e histórico | Enquanto a equipe os mantiver; ficam no banco até serem excluídos |

Ao excluir a conta, o Logto e o app removem a pessoa e a **autoria** dos registros vira anônima (as chaves estrangeiras ficam nulas): o trabalho da equipe permanece. A exclusão é bloqueada se a pessoa for a única administradora de uma equipe com outras pessoas.

## 3. Direitos do titular

- **Acesso e portabilidade:** `GET /eu/exportar` (perfil, consentimentos, equipes e autoria), também pelo botão "Baixar meus dados" no Perfil.
- **Exclusão:** `DELETE /eu`, pelo Perfil.
- **Aceite e reaceite:** os Termos e a Política têm versão (`legal/*.md`); mudou a versão, a pessoa aceita de novo antes de continuar.
- **Encarregado (DPO):** preencha o controlador e o contato do encarregado em `legal/privacidade.md` antes de produção.

## 4. Segredos

| Segredo | Onde fica | Cuidado |
|---|---|---|
| `POSTGRES_PASSWORD`, `FORMS_APP_PASSWORD` | `.env` (fora do git) | A API usa `forms_app`, sem `BYPASSRLS` e sem DDL; as migrações usam o dono |
| `FORMS_CHAVE_MESTRA` | `.env` | Cifra a chave de LLM de cada equipe. **Guarde-a fora do backup**: com ela perdida, as chaves cadastradas ficam ilegíveis (cadastre de novo) |
| `LOGTO_M2M_SECRET` | Volume `config` (escrito pelo `logto-setup`, só a API lê) | Vale como senha da Management API |
| Chave de LLM da equipe | Banco, cifrada | Nunca é devolvida pela API |

Para trocar uma senha do `.env`, atualize o `.env` **e** o papel no banco (`ALTER ROLE`): o `.env` só vale na criação do volume.

## 5. Logs

O app grava uma linha por requisição em `forms.acesso`: identificador, método, **molde da rota** (nunca o caminho real), status e duração. Não há e-mail, valor de campo, corpo, query string, token nem IP. O log de acesso do uvicorn fica **desligado** (`--no-access-log`) porque imprimiria o caminho real, inclusive o token do convite. O identificador volta no cabeçalho `X-Request-Id`: peça-o a quem relatar um problema.

## 6. Proteção contra abuso

O que o app faz sozinho: limite por pessoa e por equipe nos endpoints caros (429 com `Retry-After`), corpo de no máximo 1 MB (a API confere e responde 413), timeouts do uvicorn contra conexão lenta e limites de CPU e memória por contêiner.

**Hoje não há proxy na frente** (o Caddy foi removido; AGENTS.md §4.1). Isso significa, enquanto não houver outro: sem limite de requisições e de conexões **por IP**, sem bloqueio de reincidentes (`fail2ban`), sem HTTPS e sem os cabeçalhos de segurança do front (CSP, HSTS). A API continua mandando os dela. Por isso o compose **não publica porta nenhuma** fora do desenvolvimento, e **não expõe o app na internet** nesse estado.

**Não cobre DDoS volumétrico:** sem CDN nem WAF na frente (decisão do projeto), banda e conexões saturadas na sua rede não se resolvem aqui.

## 7. Backup e restauração

```bash
docker compose exec backup ls /backups     # forms-AAAA-MM-DD.dump e logto-AAAA-MM-DD.dump
docker compose exec -T postgres pg_restore -U forms -d forms --clean < forms-AAAA-MM-DD.dump
```

Teste a restauração num banco vazio **antes** de precisar dela (o procedimento foi exercitado: o dump restaura as 25 tabelas). Copie os dumps para fora da máquina; **não** guarde a `FORMS_CHAVE_MESTRA` junto.

## 8. Plano de resposta a incidente

1. **Contenha.** Se houver suspeita de acesso indevido: desative a pessoa (`/equipe`, "Desativar acesso", vale na hora) ou revogue o convite; se for a máquina, `docker compose stop api` tira o app do ar sem apagar dados.
2. **Preserve.** Faça um `pg_dump` extra e guarde os logs (`forms.acesso`, Logto) antes de mexer.
3. **Entenda.** Use o histórico de alterações dos registros (quem, o quê, quando) e os identificadores de requisição para reconstruir o que aconteceu.
4. **Troque o que vazou.** Senhas do `.env`, `FORMS_CHAVE_MESTRA` (e recadastre as chaves de IA), segredo M2M do Logto (apague o aplicativo `data-collect-api` no console do Logto e suba de novo: o `logto-setup` recria), e peça às pessoas que redefinam a senha.
5. **Comunique.** Havendo risco ou dano relevante a titulares, a LGPD (art. 48) exige avisar a ANPD e as pessoas afetadas em prazo razoável: acione o encarregado. Registre data, escopo, dados envolvidos e medidas.
6. **Corrija e registre.** Faça o teste que teria pegado o problema e anote o erro em `AI_NOTES.md` se a origem foi um erro da IA.

## 9. Antes de ir para produção

- [ ] Revisão jurídica dos Termos e da Política, com controlador e encarregado preenchidos
- [ ] Um proxy reverso com HTTPS na frente (serve o front, encaminha a API e o login, limita taxa por IP e manda CSP e HSTS): **pendente**, não há um no repositório
- [ ] `.env` com senhas fortes, `FORMS_CHAVE_MESTRA` e SMTP reais; `APP_URL`, `AUTH_URL` e `API_URL` com os endereços públicos
- [ ] Só `docker-compose.yml` (sem o `override`): Mailpit e as portas de desenvolvimento ficam de fora
- [ ] Backup copiado para fora da máquina e restauração testada
- [ ] Decidir se o `fail2ban` entra com o novo proxy (ele precisa do IP, que é dado pessoal, e isso exige a política)
