# Exportar para o Excel

Em **Registros**, o botão **Exportar CSV** baixa uma planilha com os mesmos filtros da lista.

## Formato

- Codificação UTF-8 com BOM, separador `;` e vírgula decimal: abre direto no Excel em português.
- O cabeçalho é `Rótulo (unidade)`.
- Números saem arredondados pelas **casas decimais** do campo.
- Campo calculado com erro sai como `ERRO: <mensagem>`; campo vazio sai vazio.
- A localização sai como `latitude / longitude`.

## Segurança

Células de texto que começam com `=`, `+`, `-` ou `@` recebem um apóstrofo na frente, para a planilha não executá-las como fórmula.

Se o botão aparece bloqueado, o seu cargo não tem a permissão de exportar.
