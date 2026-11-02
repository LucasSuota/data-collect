# empacotamento

> Gera o instalador do sistema atual (macOS `.dmg`, Windows NSIS, Linux AppImage).

## Responsabilidade
Rodar os três passos do AGENTS.md §4.1 em ordem. Não tem regra de negócio: só monta e executa os comandos.

## O que tem aqui
| Arquivo | Papel |
|---|---|
| `empacotar.py` | Roda os passos 1, 2 e 3 (ou só um, com `--passo`); a montagem dos comandos é função pura e testada |
| `../desktop/electron-builder.yml` | Configuração do passo 3 (alvos de cada sistema e onde está o backend) |
| `dist/`, `build/`, `instaladores/` | **Gerados** e não versionados (`.gitignore`) |

## Os três passos
1. **Front:** `npm ci` e `npm run build` em `frontend/`.
2. **Backend:** PyInstaller (`--onedir`) gera `dist/forms-backend/` a partir de `src/forms/app.py`, já com o `frontend/dist` dentro (`frontend_dist`), porque é o backend que serve o front na mesma origem.
3. **Instalador:** `npm run build` em `desktop/` e `electron-builder`, que põe o backend em `resources/backend/` e grava o instalador em `instaladores/`.

```bash
uv sync --group empacotamento
uv run python empacotamento/empacotar.py            # os três passos
uv run python empacotamento/empacotar.py --passo backend
```

## Como se conecta
- **Depende de:** `src/forms/app.py` (entrada do backend), `frontend/` e `desktop/`.
- **É usado por:** o workflow `.github/workflows/instalador.yml`.
- **Dependências só de build** (não vão para o app): `PyInstaller` (gera o executável do backend, que o usuário final não precisa ter Python para rodar) e `electron-builder` (monta o instalador de cada sistema).

## Decisões que moldam este código
- **O PyInstaller não faz compilação cruzada:** cada instalador é gerado no próprio sistema, por isso o CI roda numa matriz com Windows, macOS e Linux.
- `--onedir`, não `--onefile`: o `onefile` cria um processo extra (o *bootloader*) que o Electron não conseguiria encerrar junto com o backend.
- O uvicorn escolhe loops e protocolos por import dinâmico, que o PyInstaller não enxerga: `--collect-submodules uvicorn`.
- Os dados do usuário (banco e fotos) ficam na pasta de dados do sistema (`platformdirs`), nunca dentro do pacote; reinstalar ou atualizar o app não os apaga.

## Primeira abertura (sem assinatura nem notarização)
Assinatura de código e notarização estão **fora do escopo** (AGENTS.md §2.9), então o sistema avisa na primeira abertura:
- **macOS:** “não é possível abrir porque o desenvolvedor não pode ser verificado”. Clique com o botão direito no app, **Abrir**, e confirme (ou *Ajustes do Sistema > Privacidade e Segurança > Abrir mesmo assim*).
- **Windows:** o SmartScreen mostra “O Windows protegeu seu computador”. Clique em **Mais informações** e **Executar assim mesmo**.
- **Linux:** o AppImage precisa de permissão de execução: `chmod +x Construtor*.AppImage`.

## Checklist manual (o instalador em si não é testado automaticamente)
1. Instalar e abrir o app.
2. Importar ou criar um formulário e criar um registro (com um campo calculado e uma foto).
3. Exportar um CSV e conferir o diálogo nativo de salvar.
4. Fechar, abrir de novo e conferir que o registro continua lá.
5. Matar o processo do backend com a janela aberta e conferir a mensagem de erro em português.

## Cuidados
- O build do macOS gera o app para a arquitetura da máquina (arm64 ou x64); para o outro é preciso outra máquina.
- Os binários gerados são grandes (~300 MB descompactados); nunca os commite.
