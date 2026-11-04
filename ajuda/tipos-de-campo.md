# Tipos de campo

| Tipo | Para que serve |
|---|---|
| Texto | Qualquer texto livre. |
| Número | Valores com unidade (kN, mm, MPa…). Aceita vírgula ou ponto ao digitar. |
| Data | Uma data. Em fórmulas, aceita `data + dias(28)` e diferença entre datas. |
| Seleção | Uma opção de uma lista fixa. |
| Sim ou não | Verdadeiro ou falso. |
| Calculado | Resultado de uma fórmula. Ninguém digita: o servidor calcula. |
| Referência | Aponta para um registro de **outro formulário** (ver "Vínculos"). |
| Localização | Latitude e longitude. No celular, o botão **Usar minha localização** preenche sozinho. |
| Seção | Só visual: agrupa campos. |

## Propriedades úteis

- **Obrigatório:** o registro só salva com este campo preenchido.
- **Casas decimais:** quantas casas aparecem na tela e na exportação. O valor guardado e os cálculos mantêm a precisão total.
- **Compartilhar com formulários dependentes:** libera o valor deste campo para fórmulas de quem aponta para este formulário.
- **Não enviar para a IA:** o valor deste campo nunca vai ao assistente nem a nenhum provedor de IA (use em dados pessoais, como CPF).
