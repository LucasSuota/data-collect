# Escrever fórmulas

Um campo **calculado** tem uma fórmula escrita com os identificadores dos outros campos. Exemplo do corpo de prova:

```
carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)
```

## O que dá para usar

- Operadores: `+ - * / **`, parênteses, comparações (`== != < <= > >=`) e `and`, `or`, `not`.
- Funções: `se(condição, a, b)`, `min(...)`, `max(...)`, `media(...)`, `soma(...)` e `dias(n)`.
- A constante `pi`.

## Regras importantes

- **Vazio propaga:** se qualquer campo usado está vazio, o resultado fica vazio. Assim uma média parcial nunca vira um "conforme" falso.
- `se(d == 0, 0, x / d)` só calcula o ramo escolhido, então não dá divisão por zero.
- Datas: `data + dias(28)` e `data - data` (resulta em número de dias).
- **Tipos são conferidos ao publicar:** `data * 2` ou `data + data` são recusados com o trecho sublinhado.
- Ciclos (um campo que depende dele mesmo, direta ou indiretamente) são recusados.

## Editor

Digite e use o autocomplete de campos e funções, ou monte a fórmula arrastando **blocos**. A mensagem "Fórmula válida · resultado: número" vem do servidor.
