# Vínculos entre formulários

Um formulário pode **depender de outro**. Exemplo: o formulário *Proctor* depende de *Ensaio de umidade*, e *Densidade in situ* depende de *Proctor*.

## Como funciona

- O dependente tem um campo do tipo **Referência** apontando para o formulário de origem.
- A origem decide, campo a campo, o que **compartilha**. Os campos compartilhados aparecem nas fórmulas do dependente como `<referência>__<campo>` (por exemplo, `ensaio__umidade`).
- Ao preencher, você escolhe o registro de origem (ou cria/edita um na hora, numa gaveta). Vários registros do dependente podem apontar para o mesmo da origem.
- Se você edita o registro de origem, os dependentes são **recalculados** automaticamente.

## Mapa de vínculos

A tela **Mapa de vínculos** mostra quem depende de quem. Para criar um vínculo, toque na porta direita da origem e depois na porta esquerda do dependente. O vínculo entra no **rascunho** do dependente e vale quando você publicar a versão.

## Regras

- Ciclos entre formulários são recusados.
- Um formulário só pode ser excluído se ninguém depende dele e se ele não tem registros.
- Enquanto houver dependentes, a origem não pode remover um campo compartilhado nem mudar o tipo dele.
