# Rubrica de anotação

Versão 3, 01/11/2026.

Escrita antes da anotação (ADR-09). Esta versão em português é a oficial: é a que vai para a planilha e para o LLM rotulador. A versão em inglês (`annotation_rubric.en.md`) é uma tradução para leitura; se as duas divergirem, vale esta.
As listas de valores vivem em `src/govbr_classifier/taxonomy.yaml`; este arquivo diz como decidir.
As seções marcadas **(só anotação humana)** não vão para o LLM rotulador. Todo o resto é entregue a ele palavra por palavra.

## Geral

- Anote o que o texto diz, não o que você imagina que a pessoa quis dizer. Ironia evidente no próprio texto conta como o que ele diz (ver "Sarcasmo").
- Primeiro decida o `ood_manual`. Se for `nao`, anote os quatro atributos. Se for outro valor, deixe os quatro atributos vazios.
- Sempre escolha o melhor rótulo, mesmo na dúvida.
- Ênfase não muda rótulo: "péssimooo", "PÉSSIMO" e "péssimo!!!" são o mesmo texto. Caixa alta, letras repetidas e pontuação repetida indicam intensidade, e intensidade não é rotulada.
- Emoji junto com palavras é ignorado. Emoji sozinho é tratado em `ood_manual`.

## ood_manual

O LLM rotulador também decide este campo. Os nomes são os mesmos do `OodReason` da API, para comparar a anotação com os guards sem tabela de tradução.

- `nao`: o texto é em português e fala do app gov.br ou dos serviços dele. É o caso normal.
- `language`: o texto está predominantemente em outra língua. Português com algumas palavras estrangeiras ("app top, very good") continua `nao`.
- `low_text_quality`: não há palavra legível. Só emoji, só pontuação, ou sequência sem sentido ("asdfgh", "kkkkkk" sozinho). Texto curto com palavra de verdade, como "ok", "bom" ou "ruim", **não** é `low_text_quality`: ele é anotado normalmente (ver "Textos curtos").
- `off_domain`: o texto não fala do app nem de um serviço dele. Por exemplo, opinião sobre o governo sem referência ao app, reclamação sobre outro aplicativo, propaganda.

## tema (multi-label)

- Marque todo tema que o texto sustenta. "Não consigo entrar e o app está lento" é `login_autenticacao` e `lentidao`.
- **Um tema só é marcado quando o texto reclama dele, ou pede uma melhoria nele.** Citar um tema num elogio não basta: "atendimento ótimo" é `nenhum`. Em "atendimento ótimo, mas a CNH digital não abre", o elogio é ignorado e o tema é `servico_nao_carrega`.
- Três valores de escape, para quando nenhum tema da lista se aplica. Pergunte nesta ordem:
  1. Há reclamação? Se não: `nenhum` ("ótimo app", "obrigado, resolveu", "ok").
  2. A reclamação tem um assunto identificável? Se não: `nao_especificado` ("péssimo", "horrível", "lixo", "não funciona" ou "nada funciona" sem dizer o quê).
  3. O assunto existe, mas não está na lista: `outro`. Escreva o assunto na nota.
- `outro`, `nenhum` e `nao_especificado` nunca se combinam entre si nem com outros temas.
- Pedido de funcionalidade nova, fora da lista, sem reclamação ("ótimo app, poderia ter modo escuro"), é `nenhum`. Pedido de melhoria num tema da lista ("melhorem o login") recebe esse tema.
- `servico_nao_carrega` precisa de um serviço ou tela nomeados, ou de um erro de carregamento ("a CNH digital não abre", "dá erro ao carregar"). "Não funciona" sozinho é `nao_especificado`.
- Mantenha `nao_especificado` e `outro` separados: `outro` alimenta o alarme de tema novo, e uma reclamação sem assunto arquivada ali pareceria um tema desconhecido.
- `nao_especificado` é um rótulo sobre o texto, não sobre a sua dúvida. Não o use como saída quando não consegue decidir.
- **`nao_especificado` vale só para o tema.** `bloqueio`, `tipo` e `acionabilidade` são anotados normalmente. "Não funciona" costuma ser `tipo = bug`; "péssimo" costuma ser `tipo = insatisfacao_geral`; o `bloqueio` costuma ser `nao_da_para_saber`.
- **Obrigatoriedade não é tema.** "Me obrigam a...", "é obrigatório...", "sou obrigado a..." são anotados pelo mecanismo que o texto cita: "me obrigam a fazer reconhecimento facial" é `verificacao_identidade`; "obrigam a usar o app para tudo e ele não abre" é `servico_nao_carrega`. Sem mecanismo citado, a própria obrigação é o assunto: o tema é `outro`, com "obrigatoriedade" na nota.
- "Obrigado" como agradecimento não é obrigação. "Sou obrigado a + verbo" é.

## tipo (um valor só)

- `bug`: algo falha no app ou num serviço digital. Lentidão, travamento, erro, tela que não carrega e login que não funciona são falhas.
- `pedido_funcionalidade`: pede algo novo ou diferente.
- `insatisfacao_geral`: descontentamento sem falha do app e sem pedido. Reclamação de atendimento humano (central, 0800, agência) entra aqui, porque não é falha do software.
- `nenhum`: não há problema nem pedido.
- **Precedência**, quando o texto tem mais de um: `bug`, depois `pedido_funcionalidade`, depois `insatisfacao_geral`. "Trava toda hora, coloquem modo escuro" é `bug`. "App horrível, deveriam colocar modo escuro" é `pedido_funcionalidade`.

## bloqueio

- `sim`: o texto diz, ou deixa claro, que a tarefa não pôde ser concluída.
- `nao`: o texto diz que a tarefa foi concluída apesar do problema, ou não relata problema nenhum (`tipo = nenhum`).
- `nao_da_para_saber`: o texto não diz. Na dúvida entre este e outro valor, escolha este.

## acionabilidade

`sim` se o texto cita pelo menos um destes:

1. o serviço, a funcionalidade ou o canal (por exemplo "CNH digital", "carteira de trabalho", "modo escuro", "0800");
2. a etapa em que falhou (por exemplo "ao tirar a selfie");
3. uma mensagem de erro;
4. o aparelho ou o sistema operacional.

Caso contrário, `nao`. Com `tipo = nenhum`, a acionabilidade é sempre `nao`: não há o que corrigir.

## Regras de consistência

- `tipo = nenhum` exige `tema = nenhum`, `bloqueio = nao` e `acionabilidade = nao`.
- `tema = nenhum` aceita `tipo` igual a `nenhum` ou `pedido_funcionalidade`.
- `tema = outro` exige o assunto na nota.
- `ood_manual` diferente de `nao` exige os quatro atributos vazios.

## Casos especiais

- **Textos curtos.** "Ok", "bom", "top" e "show" não têm reclamação: `tema = nenhum`, `tipo = nenhum`, `bloqueio = nao`, `acionabilidade = nao`. "Ruim" e "péssimo" são reclamação sem assunto: `nao_especificado`, `insatisfacao_geral`, `nao_da_para_saber`, `nao`.
- **Texto cortado.** A coleta corta o texto em 500 caracteres. Anote só o que está visível e não complete o final. Se a parte cortada poderia mudar a resposta, use o valor mais cauteloso (`nao_da_para_saber` no bloqueio).
- **Sarcasmo.** Quando a ironia é evidente no próprio texto ("parabéns, travou de novo na hora de assinar"), anote o sentido real: é reclamação de travamento. Quando é ambígua, anote a leitura literal.

## Exemplos trabalhados

Todos os exemplos são sintéticos. Nenhum vem do conjunto de dados, para não vazar itens que podem cair no piloto ou no teste.

| # | Texto | ood_manual | tema | tipo | bloqueio | acion. |
|---|---|---|---|---|---|---|
| 1 | "não consigo entrar, pede a senha de novo e o app trava" | nao | login_autenticacao, travamento | bug | sim | sim |
| 2 | "atendimento ótimo, me ajudaram rápido" | nao | nenhum | nenhum | nao | nao |
| 3 | "atendimento ótimo, mas a CNH digital não abre" | nao | servico_nao_carrega | bug | sim | sim |
| 4 | "péssimooooo" | nao | nao_especificado | insatisfacao_geral | nao_da_para_saber | nao |
| 5 | "NÃO FUNCIONA" | nao | nao_especificado | bug | nao_da_para_saber | nao |
| 6 | "ok" | nao | nenhum | nenhum | nao | nao |
| 7 | (dois emojis de polegar para cima, sem texto) | low_text_quality | | | | |
| 8 | "very bad app, can't login" | language | | | | |
| 9 | "esse governo é uma vergonha" | off_domain | | | | |
| 10 | "ótimo app, poderia ter modo escuro" | nao | nenhum | pedido_funcionalidade | nao | sim |
| 11 | "app horrível, deveriam colocar modo escuro" | nao | nao_especificado | pedido_funcionalidade | nao_da_para_saber | sim |
| 12 | "me obrigam a fazer reconhecimento facial e a selfie nunca valida" | nao | verificacao_identidade | bug | sim | sim |
| 13 | "é obrigatório usar o app pra tudo, absurdo" | nao | outro (nota: obrigatoriedade) | insatisfacao_geral | nao_da_para_saber | nao |
| 14 | "obrigado, resolveu meu problema" | nao | nenhum | nenhum | nao | nao |
| 15 | "parabéns, travou de novo bem na hora de assinar" | nao | travamento | bug | sim | sim |
| 16 | texto longo, cortado: conta que a carteira de trabalho não carrega e termina em "aí tentei de novo e" | nao | servico_nao_carrega | bug | nao_da_para_saber | sim |
| 17 | "demora uns cinco minutos pra abrir qualquer coisa" | nao | lentidao | bug | nao_da_para_saber | nao |
| 18 | "liguei no 0800 três vezes e ninguém resolve meu problema" | nao | atendimento | insatisfacao_geral | sim | sim |

## Caixa obrigatoriedade (só anotação humana)

Marque quando o texto diz que a pessoa é obrigada a usar o app ou um mecanismo dele ("me obrigam", "é obrigatório", "sou obrigado a", "colocam a gente para fazer..."). Nos exemplos, a caixa vai marcada no 12 e no 13. A caixa não é rótulo e não muda nenhum atributo. Ela serve para juntar exemplos; no piloto ela não mede frequência. Com `ood_manual` diferente de `nao`, ela fica vazia.

## Dúvida (só anotação humana)

A coluna `duvida` registra a incerteza; ela nunca substitui um rótulo. Marque uma categoria, a principal, e explique em `nota_duvida`. Em branco quando não há dúvida. A nota do tema `outro` também vai em `nota_duvida`, sem marcar `duvida`.

| Categoria | Quando usar |
|---|---|
| `ood` | não está claro se o texto é `off_domain`, `language` ou `low_text_quality` |
| `tema_limite` | entre dois temas, ou entre um tema e um valor de escape |
| `tipo` | entre dois valores de tipo, mesmo com a precedência |
| `bloqueio` | o texto sugere, mas não deixa claro, se a tarefa foi concluída |
| `acionabilidade` | não está claro se o que foi citado conta como serviço, etapa, erro ou aparelho |
| `cortado` | a parte cortada poderia mudar a resposta (no exemplo 16, marque esta) |
| `enfase` | não está claro se a ênfase muda a leitura |
| `sarcasmo` | a ironia é ambígua e você anotou a leitura literal |
| `obrigatoriedade` | não está claro se há obrigação, ou qual mecanismo ela cita |
| `outro_caso` | qualquer outra coisa; descreva |

## Verificações de concordância (só anotação humana)

- **Piloto:** os 50 itens são reanotados pelo menos três semanas depois, sem olhar a primeira passada, para medir a concordância da anotadora consigo mesma. Eles nunca entram no teste.
- **Conjunto final:** uma semana depois de terminar, reanotar 10% aleatórios sem olhar a primeira passada.
- Reportar o kappa de Cohen entre os rótulos do LLM e os humanos, por atributo, incluindo `ood_manual`. Esse kappa é o teto do projeto.

## Questões em aberto (só anotação humana)

Registre aqui todo caso que a rubrica não cobriu, com a decisão e a data.

- 01/11/2026: reclamações sem assunto ("péssimo", "não funciona" sozinho) recebem o valor `nao_especificado` no tema, e não `outro` (revisão do ADR-05). Só o tema muda; os outros atributos são anotados normalmente.
- 01/11/2026: obrigatoriedade ("me obrigam a...") não é rótulo. Anota-se pelo mecanismo citado; sem mecanismo, `outro` com nota. Pode virar rótulo se o teste anotado tiver pelo menos 30 casos (ADR-07); ela aparece em 1.674 textos únicos (0,52%), então só com amostragem direcionada.
- 01/11/2026 (versão 3): `skip` substituído por `ood_manual`, que o LLM também decide; tema só com reclamação ou pedido; precedência do tipo; atendimento humano é `insatisfacao_geral`; regras de consistência; casos especiais; categorias de dúvida; 18 exemplos sintéticos. A versão em português passa a ser a oficial.
- 01/11/2026: "kkkkkk" sozinho é `low_text_quality` na rubrica, mas o guard da API classifica (o texto tem letras). A diferença é esperada e serve para medir o guard.
