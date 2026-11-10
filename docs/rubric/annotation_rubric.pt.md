# Rubrica de anotação

Versão 4, 09/11/2026.

Escrita antes da anotação (ADR-09) e revisada depois do piloto de 50 itens. Esta versão em português é a oficial: é a que vai para a planilha e para o LLM rotulador. A versão em inglês (`annotation_rubric.en.md`) é uma tradução para leitura; se as duas divergirem, vale esta.
As listas de valores vivem em `src/govbr_classifier/taxonomy.yaml`; este arquivo diz como decidir.
As seções marcadas **(só anotação humana)** não vão para o LLM rotulador. Todo o resto é entregue a ele palavra por palavra.

## Geral

- Anote o que o texto diz, não o que você imagina que a pessoa quis dizer. Ironia evidente no próprio texto conta como o que ele diz (ver "Sarcasmo").
- Primeiro decida o `ood_manual`. Se for `nao`, anote os quatro atributos. Se for outro valor, deixe os quatro atributos vazios.
- Sempre escolha o melhor rótulo, mesmo na dúvida.
- Ênfase não muda rótulo: "péssimooo", "PÉSSIMO" e "péssimo!!!" são o mesmo texto. Caixa alta, letras repetidas e pontuação repetida indicam intensidade, e intensidade não é rotulada. Palavrão censurado com símbolos ("porc@ria", "b@#ta") conta como a palavra que substitui.
- Emoji junto com palavras é ignorado. Emoji sozinho é tratado em `ood_manual`.

## ood_manual

O LLM rotulador também decide este campo. Os nomes são os mesmos do `OodReason` da API, para comparar a anotação com os guards sem tabela de tradução.

- `nao`: o texto é em português e fala do app gov.br ou dos serviços dele. É o caso normal.
- `language`: o texto está predominantemente em outra língua. Português com algumas palavras estrangeiras ("app top, very good") continua `nao`.
- `low_text_quality`: não há palavra legível. Só emoji, só pontuação, só símbolos, ou sequência sem sentido ("asdfgh", "kkkkkk" sozinho). Texto curto com palavra de verdade, como "ok", "bom" ou "ruim", **não** é `low_text_quality`: ele é anotado normalmente (ver "Textos curtos").
- `off_domain`: o texto não fala do app nem de um serviço dele. Por exemplo, opinião sobre o governo sem referência ao app, reclamação sobre outro aplicativo, propaganda. Crítica ao país ou ao governo dentro de uma reclamação sobre o app continua `nao`.

## tema (multi-label)

### Quando marcar um tema

- **Um tema só é marcado quando o texto reclama dele, ou pede uma melhoria nele.** Citar um tema num elogio não basta: "atendimento ótimo" é `nenhum`. Em "atendimento ótimo, mas a CNH digital não abre", o elogio é ignorado e o tema é `servico_nao_carrega`.
- **Vários temas ou um só.** Marque mais de um quando o texto relata problemas distintos, somados ("o código não chega **e** a biometria está inválida": `login_autenticacao` e `verificacao_identidade`). Quando um problema causa o outro ("não consigo entrar **porque** o rosto não passa"), marque só o mecanismo que falhou: `verificacao_identidade`. Teste: as duas caixas se aplicam, ou estou escolhendo entre elas? Se estou escolhendo, marco a melhor e registro a dúvida.

### Os três valores de escape

Pergunte nesta ordem:

1. **Há reclamação?** Se não: `nenhum` ("ótimo app", "obrigado, resolveu", "ok", "ainda nem testei"). Qualquer coisa negativa no texto, inclusive um xingamento, já é reclamação.
2. **A reclamação tem um assunto identificável?** Complete a frase "a reclamação é sobre ___". Se só cabem adjetivos ou verbos de falha ("péssimo", "horrível", "lixo", "não funciona", "nada funciona"), não há assunto: `nao_especificado`.
3. **O assunto está na lista?** Se cabe um substantivo que nomeia uma parte ou um aspecto do app, mas nenhuma caixa serve ("navegação", "meus dados", "compatibilidade com o celular", "prazo do órgão"), o tema é `outro`, e o assunto vai na coluna `assunto_outro`.

- `outro`, `nenhum` e `nao_especificado` nunca se combinam entre si nem com outros temas. Quando o texto tem um problema da lista e outro assunto distinto fora dela, o tema da lista vence; o assunto de fora pode ir em `assunto_outro`, para registro. Quando um causa o outro, aplique o "porque": celular antigo incompatível que impede a verificação em duas etapas é `outro` (compatibilidade), porque a causa é uma só.
- Mantenha `nao_especificado` e `outro` separados: `outro` alimenta o alarme de tema novo, e uma reclamação sem assunto arquivada ali pareceria um tema desconhecido.
- `nao_especificado` é um rótulo sobre o texto, não sobre a sua dúvida. Não o use como saída quando não consegue decidir.
- **`nao_especificado` vale só para o tema.** `bloqueio`, `tipo` e `acionabilidade` são anotados normalmente.
- Pedido de funcionalidade nova, fora da lista, sem reclamação ("ótimo app, poderia ter modo escuro"), é `nenhum`. Pedido de melhoria num tema da lista ("melhorem o login") recebe esse tema.

### Fronteiras entre temas

- **`login_autenticacao` × `verificacao_identidade`.** Login responde "você tem a chave desta conta?": senha, código por SMS ou e-mail, recuperar a senha, conta bloqueada, "CPF já cadastrado". Verificação responde "você é mesmo esta pessoa?": reconhecimento facial, selfie, captura de rosto, biometria, prova de vida, validação de documentos. Rosto, selfie e biometria são sempre `verificacao_identidade`, mesmo quando a pessoa estava tentando entrar.
- **"Acessar" e "entrar".** "Não consigo acessar" ou "não consigo entrar", sem objeto, é `login_autenticacao`: no gov.br, a porta de entrada é a conta. "Acessar X" (um serviço) recebe o tema de X. "Difícil acessar tudo", como julgamento sobre achar as coisas no app, é `outro` (navegação).
- **`servico_nao_carrega`** precisa de um serviço ou tela nomeados, ou de um erro de carregamento ("a CNH digital não abre", "dá erro ao carregar"). "Não funciona" sozinho é `nao_especificado`.
- **"Foto".** O verbo decide. Rosto, selfie, "validar a foto": `verificacao_identidade`. Anexar, enviar, "onde coloco a foto", campo que não aparece: `servico_nao_carrega`.
- **Lentidão.** `lentidao` é o app ou uma tela lentos ("muito lento", "demora pra abrir"). Quando a demora é de um passo específico ("pra recuperar a senha demora muito", "muito devagar para reconhecer"), marque o mecanismo **e** `lentidao`: assim `lentidao` conta toda reclamação de velocidade. Prazo do órgão ("o pedido demora 60 dias pra ser aprovado") não é lentidão do app: é `outro` (prazo do órgão).
- **Código de erro sem explicação** ("erro 403"). O resto do texto decide o tema. Sem contexto nenhum, `nao_especificado`. A acionabilidade é `sim`, porque uma mensagem de erro é um dos critérios.
- **Obrigatoriedade não é tema.** "Me obrigam a...", "é obrigatório...", "sou obrigado a..." são anotados pelo mecanismo que o texto cita: "me obrigam a fazer reconhecimento facial" é `verificacao_identidade`. Sem mecanismo citado, a própria obrigação é o assunto: `outro`, com "obrigatoriedade" em `assunto_outro`. "Obrigado" como agradecimento não é obrigação.

## tipo (um valor só)

- `bug`: o texto **relata um evento**: algo deveria acontecer no app ou num serviço digital e não aconteceu. Lentidão, travamento, erro, tela que não carrega, login que não entra, rosto que não valida e "não consigo usar" são falhas, mesmo quando o relato é vago.
- `insatisfacao_geral`: o texto **faz um julgamento**, sem relatar uma falha nem pedir algo: "péssimo", "complicado", "uma porcaria". Entram aqui também:
  - reclamação de atendimento humano (central, 0800, agência), porque não é falha do software;
  - **barreira por regra**: o app funciona como foi programado, mas uma regra impede a pessoa (documento exigido, idade, nível da conta, celular sem suporte).
- `pedido_funcionalidade`: pede algo novo ou diferente.
- `nenhum`: não há problema nem pedido.
- Pergunta-guia entre `bug` e `insatisfacao_geral`: um desenvolvedor saberia o que consertar? Se algo quebrou, é `bug`.
- **Precedência**, quando o texto tem mais de um: `bug`, depois `pedido_funcionalidade`, depois `insatisfacao_geral`. "Trava toda hora, coloquem modo escuro" é `bug`. "App horrível, deveriam colocar modo escuro" é `pedido_funcionalidade`.

## bloqueio

- `sim`: o texto diz, ou deixa claro, que a tarefa não pôde ser concluída. Uma mensagem de erro que impede seguir conta como `sim`.
- `nao`: o texto diz que a tarefa foi concluída apesar do problema, ou não relata problema nenhum (`tipo = nenhum`).
- `nao_da_para_saber`: o texto não diz. "Nem sempre funciona" e "demora muito" ficam aqui, porque não dizem se a pessoa acabou conseguindo. Na dúvida entre este e outro valor, escolha este.

## acionabilidade

`sim` se o texto cita pelo menos um destes:

1. o serviço, a funcionalidade ou o canal (por exemplo "CNH digital", "carteira de trabalho", "minha conta", "recuperar a senha", "modo escuro", "0800");
2. a etapa em que falhou (por exemplo "ao tirar a selfie", "captura de rosto");
3. uma mensagem ou código de erro;
4. o aparelho ou o sistema operacional (inclusive "celular antigo").

Caso contrário, `nao`. "Acessar" ou "navegação" sozinhos não nomeiam nada específico. Com `tipo = nenhum`, a acionabilidade é sempre `nao`: não há o que corrigir.

## Regras de consistência

- `tipo = nenhum` exige `tema = nenhum`, `bloqueio = nao` e `acionabilidade = nao`.
- `tema = nenhum` aceita `tipo` igual a `nenhum` ou `pedido_funcionalidade`.
- `tema = outro` exige `assunto_outro` preenchido.
- `ood_manual` diferente de `nao` exige os quatro atributos vazios.

## Casos especiais

- **Textos curtos.** "Ok", "bom", "top" e "show" não têm reclamação: `tema = nenhum`, `tipo = nenhum`, `bloqueio = nao`, `acionabilidade = nao`. "Ruim", "péssimo" e um xingamento sozinho são reclamação sem assunto: `nao_especificado`, `insatisfacao_geral`, `nao_da_para_saber`, `nao`.
- **Texto cortado.** A coleta corta o texto em 500 caracteres. Anote só o que está visível e não complete o final. Se a parte cortada poderia mudar a resposta, use o valor mais cauteloso (`nao_da_para_saber` no bloqueio).
- **Sarcasmo.** Quando a ironia é evidente no próprio texto ("parabéns, travou de novo na hora de assinar"), anote o sentido real: é reclamação de travamento. Quando é ambígua, anote a leitura literal.

## Exemplos trabalhados

Todos os exemplos são sintéticos. Nenhum vem do conjunto de dados, para não vazar itens que podem cair na amostra ou no teste.

| # | Texto | ood_manual | tema | assunto_outro | tipo | bloqueio | acion. |
|---|---|---|---|---|---|---|---|
| 1 | "não consigo entrar, pede a senha de novo e o app trava" | nao | login_autenticacao, travamento | | bug | sim | sim |
| 2 | "atendimento ótimo, me ajudaram rápido" | nao | nenhum | | nenhum | nao | nao |
| 3 | "atendimento ótimo, mas a CNH digital não abre" | nao | servico_nao_carrega | | bug | sim | sim |
| 4 | "péssimooooo" | nao | nao_especificado | | insatisfacao_geral | nao_da_para_saber | nao |
| 5 | "NÃO FUNCIONA" | nao | nao_especificado | | bug | nao_da_para_saber | nao |
| 6 | "ok" | nao | nenhum | | nenhum | nao | nao |
| 7 | (dois emojis de polegar para cima, sem texto) | low_text_quality | | | | | |
| 8 | "very bad app, can't login" | language | | | | | |
| 9 | "esse governo é uma vergonha" | off_domain | | | | | |
| 10 | "ótimo app, poderia ter modo escuro" | nao | nenhum | | pedido_funcionalidade | nao | sim |
| 11 | "app horrível, deveriam colocar modo escuro" | nao | nao_especificado | | pedido_funcionalidade | nao_da_para_saber | sim |
| 12 | "me obrigam a fazer reconhecimento facial e a selfie nunca valida" | nao | verificacao_identidade | | bug | sim | sim |
| 13 | "é obrigatório usar o app pra tudo, absurdo" | nao | outro | obrigatoriedade | insatisfacao_geral | nao_da_para_saber | nao |
| 14 | "obrigado, resolveu meu problema" | nao | nenhum | | nenhum | nao | nao |
| 15 | "parabéns, travou de novo bem na hora de assinar" | nao | travamento | | bug | sim | sim |
| 16 | texto longo, cortado: conta que a carteira de trabalho não carrega e termina em "aí tentei de novo e" | nao | servico_nao_carrega | | bug | nao_da_para_saber | sim |
| 17 | "demora uns cinco minutos pra abrir qualquer coisa" | nao | lentidao | | bug | nao_da_para_saber | nao |
| 18 | "liguei no 0800 três vezes e ninguém resolve meu problema" | nao | atendimento | | insatisfacao_geral | sim | sim |
| 19 | "não consigo acessar faz uma semana" | nao | login_autenticacao | | bug | sim | nao |
| 20 | "pra recuperar a senha demora demais" | nao | login_autenticacao, lentidao | | bug | nao_da_para_saber | sim |
| 21 | "o código não chega e a biometria dá inválida" | nao | login_autenticacao, verificacao_identidade | | bug | sim | sim |
| 22 | "não aparece onde anexar a foto do documento no pedido" | nao | servico_nao_carrega | | bug | sim | sim |
| 23 | "muito complicada a navegação" | nao | outro | navegação | insatisfacao_geral | nao_da_para_saber | nao |
| 24 | "não roda no meu celular porque é antigo, tenho que trocar de telefone" | nao | outro | compatibilidade com o celular | insatisfacao_geral | sim | sim |
| 25 | "pede a carteira de motorista e eu não tenho" | nao | verificacao_identidade | | insatisfacao_geral | sim | sim |
| 26 | "só aparece erro 500" | nao | nao_especificado | | bug | sim | sim |
| 27 | "o pedido de restituição demora meses pra ser analisado" | nao | outro | prazo do órgão | insatisfacao_geral | nao_da_para_saber | sim |

## Caixa obrigatoriedade (só anotação humana)

Marque quando o texto diz que a pessoa é obrigada a usar o app ou um mecanismo dele, de forma explícita ("me obrigam", "é obrigatório", "sou obrigado a", "colocam a gente para fazer...") ou implícita ("meus apps só entram por ele", "tenho que trocar de telefone para ter acesso"). Nos exemplos, a caixa vai marcada no 12, no 13 e no 24. A caixa não é rótulo e não muda nenhum atributo. Com `ood_manual` diferente de `nao`, ela fica vazia.

## Dúvida (só anotação humana)

A coluna `duvida` registra a incerteza; ela nunca substitui um rótulo. Marque uma categoria, a principal, e explique em `nota_duvida`. Em branco quando não há dúvida. Vale a dúvida que sobrou depois de aplicar a rubrica, não a do primeiro instante. O assunto do tema `outro` vai em `assunto_outro`, nunca em `nota_duvida`.

| Categoria | Quando usar |
|---|---|
| `ood` | não está claro se o texto é `off_domain`, `language` ou `low_text_quality` |
| `tema_limite` | entre dois temas, ou entre um tema e um valor de escape, depois de aplicar as fronteiras acima |
| `tipo` | entre dois valores de tipo, mesmo com a pergunta-guia e a precedência |
| `bloqueio` | o texto sugere, mas não deixa claro, se a tarefa foi concluída |
| `acionabilidade` | não está claro se o que foi citado conta como serviço, etapa, erro ou aparelho |
| `cortado` | a parte cortada poderia mudar a resposta (no exemplo 16, marque esta) |
| `enfase` | não está claro se a ênfase muda a leitura |
| `sarcasmo` | a ironia é ambígua e você anotou a leitura literal |
| `obrigatoriedade` | não está claro se há obrigação, ou qual mecanismo ela cita |
| `outro_caso` | qualquer outra coisa; descreva |

## Verificações de concordância (só anotação humana)

- **Piloto:** os 50 itens são reanotados com esta versão a partir de 29/11/2026, sem olhar a primeira passada. A concordância da anotadora consigo mesma é medida só nos itens cuja regra não mudou da v3 para a v4; nos itens que caíram em regras novas (p007, p013, p017, p025, p033, p039), a diferença mede o efeito da mudança. Os 50 nunca entram no teste.
- **Conjunto final:** uma semana depois de terminar, reanotar 10% aleatórios sem olhar a primeira passada.
- Reportar o kappa de Cohen entre os rótulos do LLM e os humanos, por atributo, incluindo `ood_manual`. Esse kappa é o teto do projeto.

## Questões em aberto (só anotação humana)

Registre aqui todo caso que a rubrica não cobriu, com a decisão e a data.

- 01/11/2026: reclamações sem assunto ("péssimo", "não funciona" sozinho) recebem o valor `nao_especificado` no tema, e não `outro` (revisão do ADR-05).
- 01/11/2026: obrigatoriedade não é rótulo. Anota-se pelo mecanismo citado; sem mecanismo, `outro`. Pode virar rótulo se o teste anotado tiver pelo menos 30 casos (ADR-07); ela aparece em 1.674 textos únicos (0,52%), então só com amostragem direcionada.
- 01/11/2026: "kkkkkk" sozinho é `low_text_quality` na rubrica, mas o guard da API classifica (o texto tem letras). A diferença é esperada e serve para medir o guard.
- 09/11/2026 (versão 4, depois do piloto): teste "a reclamação é sobre ___" para os escapes; regra do "porque × e"; fronteira entre login e verificação; "acessar" sem objeto é login; demora de um passo marca o mecanismo e `lentidao`; prazo do órgão é `outro`; "foto" decidida pelo verbo; código de erro sem contexto é `nao_especificado` com acionabilidade `sim`; `bug` é relato de evento e `insatisfacao_geral` é julgamento; barreira por regra é `insatisfacao_geral`; obrigatoriedade implícita marca a caixa; coluna `assunto_outro`; 27 exemplos sintéticos.
- 09/11/2026: novos temas (navegação, compatibilidade) e a exclusividade do `outro` são decisões da taxonomia, não da rubrica. A coluna `assunto_outro` junta os assuntos na amostra final; um tema só nasce se aparecer o bastante (pelo menos 30 casos no teste, ADR-07).
