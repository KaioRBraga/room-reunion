# Registro de bugs encontrados e corrigidos

Histórico dos problemas reais encontrados durante o desenvolvimento (não cobre
decisões de design/UX, só bugs com causa raiz e correção). Cada item nasceu de
um relato testado e reproduzido antes da correção.

## 1. Modal travado atrás do backdrop no modo escuro (cliques não funcionam)

**Data**: 2026-06-22

**Sintoma relatado**: ao abrir o modal de edição de sala no mapa (clicar num
pin), nada dentro do modal respondia a clique - campos, checkboxes e botões
("Salvar", "Fechar" etc.) pareciam travados, mesmo sendo admin. O modal
aparecia visualmente normal, só não reagia a clique.

**Causa raiz**: a animação de entrada adicionada em
`app/static/css/app.css` (`.container-fluid { animation: rr-fade-in 0.35s
ease both; }`) usava `animation-fill-mode: both`. Mesmo a animação
terminando em `opacity: 1` (visualmente idêntico ao estado normal,
sem nenhum `transform` envolvido), o `fill-mode: both` mantém o elemento
permanentemente "sob efeito de uma animação de opacity" - e isso, por si só,
cria um novo *contexto de empilhamento* CSS para esse elemento, **mesmo sem
nenhuma mudança visual perceptível**.

Como `.container-fluid` é ancestral dos modais do Bootstrap
(`position: fixed`) em todas as páginas (`app/templates/base.html`), esse
novo contexto de empilhamento passou a conter o `.modal` dentro de si. O
`.modal-backdrop` (criado pelo Bootstrap como filho direto de `<body>`, fora
desse contexto) ficou, na prática, acima do modal inteiro na ordem de
empilhamento real - apesar do `.modal` declarar `z-index: 1055` contra os
`1050` do backdrop, essa comparação só vale *dentro* do mesmo contexto de
empilhamento. O backdrop passou a interceptar todos os cliques, embora o
modal continuasse sendo renderizado visualmente por cima.

**Diagnóstico**: reproduzido com Playwright (Chromium automatizado) clicando
de fato nos elementos do modal - o erro real do Playwright (`<div
class="modal-backdrop fade show"> intercepts pointer events`) confirmou a
interceptação. A primeira hipótese (um `transform: translateY(0)` residual)
foi descartada por bisecção: comentando blocos do CSS um a um até isolar a
regra mínima que reproduzia o problema, sobrou exatamente a animação de
opacidade com `fill-mode: both` - mesmo sem nenhum `transform`.

**Correção**: removido o `fill-mode: both`, mantendo `animation: rr-fade-in
0.35s ease;` (fill-mode padrão `none`). Sem ele, a animação deixa de afetar o
elemento assim que termina, eliminando o contexto de empilhamento residual.
Validado de ponta a ponta: editar nome da sala, marcar equipamento e salvar
funcionando, sem reaparecer em nenhuma outra página/modal testada
(calendário, mapa, relatórios, permissões).

**Arquivo alterado**: `app/static/css/app.css` (regra `.container-fluid`).

**Lição para o futuro**: qualquer `animation`/`transition` em CSS que afete
`opacity` ou `transform` cria um contexto de empilhamento *enquanto estiver
"ativa"* - e com `animation-fill-mode: both`/`forwards`, ela nunca deixa de
estar ativa, mesmo parada no frame final idêntico ao normal. Evitar
`fill-mode: both/forwards` em elementos que são ancestrais de qualquer coisa
`position: fixed`/`sticky` (modais, dropdowns, tooltips) - ou, se for
realmente necessário, resetar o `animation` explicitamente após o fim
(`animationend`) em vez de deixar o fill-mode permanente.

## 2. Overflow no banner de status do painel (tablet/celular em tela estreita)

**Data**: 2026-06-22

**Sintoma relatado**: testando o app `display_app` direto num celular Android
real (conectado via `adb`/USB), o banner de status ("Disponível" + reunião
atual/próxima + botão de ação) aparecia com uma faixa de aviso do Flutter
("RIGHT OVERFLOWED BY 31 PIXELS") sobre o botão "Iniciar agora", em vez de
renderizar normalmente.

**Causa raiz**: `DisplayBody._statusBanner()`
(`display_app/lib/widgets/display_body.dart`) usava um `Row` fixo com o
texto de status (`Expanded`) de um lado e o botão de ação grande
(`_bigActionButton`, com padding `40h/30v` e fonte `21px` - aumentado a
pedido em ajustes anteriores) do outro. Isso foi desenhado e só testado em
viewport largo (emulador web em 1280x800, estilo tablet/paisagem). Num
celular real em retrato (1080px de largura), o `Expanded` do texto somado à
largura mínima do botão grande excede a largura disponível do `Row` - como
nenhum dos dois lados podia encolher mais, o `Row` estourou (`RenderFlex
overflow`) em vez de fazer wrap.

**Diagnóstico**: reproduzido instalando e rodando o app de verdade num
celular Android via `flutter run -d <device-id>` (não dava pra notar isso só
testando no emulador web em formato de tablet - o bug só aparece em telas
estreitas). Capturado via `adb exec-out screencap`, a faixa de overflow do
Flutter (vermelho/preto, renderizada automaticamente em modo debug sempre
que um `RenderFlex` não cabe no espaço disponível) apontou exatamente para o
`Row` do banner de status.

**Correção**: o `Row` interno do banner passou a ser construído dentro de um
`LayoutBuilder`: quando `constraints.maxWidth < 560`, o texto de status e o
botão de ação são empilhados em `Column` (texto acima, botão alinhado à
direita abaixo) em vez de lado a lado; em telas largas mantém o `Row`
original. Validado de ponta a ponta no mesmo celular físico, conectado ao
servidor Flask real via `adb reverse tcp:5000 tcp:5000` - sem overflow, sala
"Quarto" exibida corretamente com o novo layout empilhado.

**Arquivo alterado**: `display_app/lib/widgets/display_body.dart`
(`_statusBanner()`).

**Lição para o futuro**: testar widgets responsivos do Flutter só no Chrome
em resolução de tablet não garante nada sobre celular em retrato (ou
qualquer viewport mais estreito) - `Row`s com um `Expanded` e um botão de
tamanho fixo precisam de um `LayoutBuilder`/breakpoint para telas estreitas,
ou o `RenderFlex` estoura silenciosamente em produção (a faixa de overflow
só aparece em modo debug; em release o conteúdo é cortado sem aviso nenhum).

## 3. `OperationalError: no such column: site_branding_settings.icon_filename`

**Data**: 2026-06-22

**Sintoma relatado**: depois de adicionar o upload do "ícone" (segundo logo,
usado na marca pequena da barra lateral e no favicon), o site inteiro parou
de funcionar no servidor real já em execução - toda página quebrava com uma
tela de erro do Flask: `sqlalchemy.exc.OperationalError:
(sqlite3.OperationalError) no such column: site_branding_settings.icon_filename`.

**Causa raiz**: o model `SiteBrandingSettings` foi criado nesta mesma sessão,
inicialmente só com `logo_filename`/`primary_color`/`secondary_color`. No
primeiro `create_app()` depois disso, `db.create_all()` criou a tabela
`site_branding_settings` no banco real do usuário (`instance/readyroom.sqlite3`)
já com esse schema (sem `icon_filename`). Pouco depois, a pedido do usuário
("E tem que trocar o segundo logo no caso o 'icon'"), a coluna `icon_filename`
foi adicionada ao model - mas `db.create_all()` só cria tabelas que **ainda
não existem**; nunca altera tabelas já existentes. Como o servidor real do
usuário ficou rodando o tempo todo durante o desenvolvimento (de propósito,
para não interromper o trabalho dele - ver lição abaixo), a tabela em disco
continuou com o schema antigo, sem a coluna nova, e qualquer leitura via
SQLAlchemy (inclusive o context processor que injeta a identidade visual em
toda página) passou a falhar.

**Diagnóstico**: a própria mensagem de erro do SQLAlchemy já aponta a causa
exata (`no such column: site_branding_settings.icon_filename`) - o projeto já
tem um mecanismo dedicado a esse tipo de problema (`app/schema_migrations.py`,
com um comentário explícito avisando que `db.create_all()` não cobre colunas
novas em tabelas já existentes), e a nova coluna não tinha sido adicionada à
lista `_NEW_COLUMNS` dele.

**Correção**: adicionada a entrada `("site_branding_settings",
"icon_filename", "VARCHAR(255)")` em `_NEW_COLUMNS`
(`app/schema_migrations.py`), para que `ensure_columns()` rode o `ALTER TABLE`
necessário no próximo restart do servidor. Validado recriando localmente o
cenário exato (tabela SQLite criada manualmente com o schema antigo, sem
`icon_filename`) e confirmando que `create_app()` aplica o `ALTER TABLE` e a
leitura via `SiteBrandingSettings.get_settings()` passa a funcionar sem erro.

**Arquivo alterado**: `app/schema_migrations.py`.

**Lição para o futuro**: toda vez que um model novo ganha uma coluna *depois*
de já ter sido criado - mesmo que o model em si tenha sido adicionado na
mesma sessão/feature -, a entrada correspondente precisa entrar em
`_NEW_COLUMNS`; `db.create_all()` só ajuda enquanto a tabela ainda não existe
em nenhum banco real. Esse tipo de schema drift fica invisível enquanto o
servidor de desenvolvimento não reinicia (o processo em memória não vê a
mudança no model até recarregar) - só aparece de fato no primeiro restart
depois da mudança, então vale sempre checar `schema_migrations.py` ao alterar
um model que já passou por pelo menos um `create_app()`. Esta correção só tem
efeito a partir do próximo restart do servidor real - rodando em memória, ele
continua com o erro até reiniciar.

## 4. Botão "Instalar via USB" não encontrava o `adb` numa máquina onde ele funciona normalmente

**Data**: 2026-06-23

**Sintoma relatado**: ao clicar em "Instalar via USB" (aba Configurações ->
Layout do painel -> Tablet), a mensagem de erro dizia `'adb' não encontrado
no PATH desta máquina. Instale o Android SDK Platform Tools.` - mesmo sendo a
mesma máquina onde `flutter run -d <device-id>` e comandos `adb` manuais já
tinham funcionado nesta sessão (ver bug #2).

**Causa raiz**: a rota `install_tablet_apk()`
(`app/rooms/routes.py`) localizava o `adb` só com `shutil.which("adb")`, que
procura exclusivamente nos diretórios listados na variável de ambiente
`PATH`. O Android SDK Platform Tools (onde o binário `adb`/`adb.exe` de fato
mora, em `<SDK>/platform-tools/`) nunca foi adicionado ao `PATH` desta
máquina - o Flutter e o Android Studio encontram o `adb` por outro caminho:
lendo as variáveis `ANDROID_HOME`/`ANDROID_SDK_ROOT`. Como essas variáveis
não são `PATH`, `shutil.which("adb")` retornava `None` mesmo com o SDK
instalado e o `adb` plenamente funcional.

**Diagnóstico**: confirmado comparando os dois mecanismos de busca na mesma
sessão de PowerShell: `Get-Command adb` não encontrava nada, enquanto
`$env:ANDROID_HOME` apontava para `...\AppData\Local\Android\Sdk` e
`Test-Path "$env:ANDROID_HOME\platform-tools\adb.exe"` confirmava que o
binário existia ali. Reproduzido isoladamente chamando `shutil.which("adb")`
direto em Python (retornou `None`) e depois `shutil.which("adb",
path=f"{sdk}\\platform-tools")` (encontrou o `adb.EXE`).

**Correção**: adicionado `_resolve_adb_path()` em `app/rooms/routes.py`, que
tenta `shutil.which("adb")` primeiro e, se não encontrar, procura em
`ANDROID_HOME`/`ANDROID_SDK_ROOT` + `platform-tools` antes de desistir.
`install_tablet_apk()` passou a usar essa função em vez de chamar
`shutil.which` diretamente. Validado chamando `_resolve_adb_path()` nesta
máquina (resolveu para o `adb.exe` real do SDK) e confirmando com `adb
devices` que o dispositivo físico conectado aparece como `device`
(autorizado).

**Arquivo alterado**: `app/rooms/routes.py` (`_resolve_adb_path`,
`install_tablet_apk`); testes ajustados em `tests/test_tablet_apk_install.py`.

**Lição para o futuro**: nunca assumir que uma ferramenta de linha de comando
usada por outro programa (IDE, Flutter, Android Studio) está no `PATH` do
sistema só porque ela "funciona" nesse ambiente - muitas ferramentas de
desenvolvimento resolvem o caminho de binários por variáveis de ambiente
próprias (`ANDROID_HOME`, `JAVA_HOME`, etc.), não pelo `PATH` do shell. Código
que precisa invocar esses binários via `subprocess` deve espelhar essa mesma
lógica de resolução, não só `shutil.which`.

## 5. `UnicodeDecodeError`/`TypeError` ao rodar `flutter build apk` via `subprocess` no Windows

**Data**: 2026-06-23

**Sintoma relatado**: ao clicar em "Instalar via USB" (que builda o app antes
de instalar - ver item anterior), o servidor real quebrou com dois erros
encadeados no log: primeiro um `UnicodeDecodeError: 'charmap' codec can't
decode byte 0x90 in position 177` dentro de uma thread interna do
`subprocess` (`_readerthread`), e na sequência um `TypeError: unsupported
operand type(s) for +: 'NoneType' and 'str'` na linha que concatena
`build_result.stdout + build_result.stderr`. No navegador, isso apareceu como
`SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON` -
porque o front-end tentava interpretar a página de erro 500 (HTML) como JSON.

**Causa raiz**: `subprocess.run(..., text=True)` sem um `encoding` explícito
usa, no Windows, a codificação padrão do console (`cp1252` nesta máquina), não
UTF-8. A saída do `flutter build apk`/Gradle contém caracteres (acentos,
símbolos de progresso) fora do intervalo válido de `cp1252`. Quando a thread
interna do `subprocess` que lê `stdout` encontrava um desses bytes (`0x90`),
o decode falhava silenciosamente *dentro da thread* - o `subprocess.run`
não propagava essa exceção pra cima, só deixava `build_result.stdout`/
`stderr` como `None`. A linha seguinte, que soma os dois (`stdout + stderr`),
quebrava com `TypeError` por tentar somar `None` com `str`. Do lado do
front-end, o `fetch().then(res => res.json())` assumia que toda resposta era
JSON e quebrava com um erro confuso ao receber a página HTML de erro 500 do
Flask.

**Diagnóstico**: o próprio traceback enviado pelo usuário já mostrava as duas
exceções encadeadas, na ordem certa (decode dentro de `_readerthread`,
depois o `TypeError` na linha de concatenação) - bastou ler o stack trace.
Reproduzido isoladamente rodando um subprocesso que escreve o byte `0x90` cru
em `stdout`: com `text=True` (sem `encoding`), o decode falha; com
`encoding="utf-8", errors="replace"`, o byte inválido é substituído (`�`) sem
derrubar o processo.

**Correção**: todas as chamadas a `subprocess.run` em `install_tablet_apk()`
(`flutter build apk`, `adb devices`, `adb install`, `adb reverse`) passaram a
usar `encoding="utf-8", errors="replace"` em vez de `text=True` puro - bytes
fora do esperado viram `�` em vez de derrubar a leitura. Como reforço, toda
concatenação de `stdout`/`stderr` passou a usar `(x.stdout or "") + (x.stderr
or "")`, pra nunca mais quebrar com `TypeError` se algum dia `None` aparecer
por outro motivo. No front-end, o `fetch` agora confere o `content-type` da
resposta antes de chamar `res.json()`, mostrando uma mensagem clara em vez do
`SyntaxError` quando o servidor responde com uma página de erro HTML.

**Arquivo alterado**: `app/rooms/routes.py` (`install_tablet_apk`);
`app/templates/rooms/settings.html` (handler do `fetch`).

**Lição para o futuro**: em qualquer `subprocess.run`/`Popen` com `text=True`
(ou `universal_newlines=True`) no Windows, especificar sempre `encoding` e
`errors` explicitamente (`encoding="utf-8", errors="replace"` é o padrão mais
seguro) - o encoding padrão do console do Windows quase nunca é UTF-8, e
saída de ferramentas modernas (Flutter, Node, etc.) quase sempre contém
caracteres fora de `cp1252`. Além disso, qualquer código no servidor que
devolve JSON pra um `fetch()` precisa que TODOS os caminhos de erro
(`try/except`, exceções não tratadas) também devolvam JSON - senão o
front-end recebe a página de erro HTML do framework e quebra de um jeito que
não aponta pra causa real.
