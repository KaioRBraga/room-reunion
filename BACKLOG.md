# Backlog de funcionalidades — ReadyRoom

Spec de itens levantados em 2026-06-19, antes de qualquer implementação. Cada
item descreve: estado atual no código, proposta de mudança (dados / UI / API),
dependências e perguntas ainda abertas. Decisões já confirmadas com o
dono do produto estão marcadas como **Decidido**.

## 1. Painel do tablet: iniciar reunião no check-in + status em português

**Estado atual**
- `resolve_display_state` (app/bookings/services.py:177-214) calcula o status
  (`available` / `starting_soon` / `in_use`) só a partir do horário: uma
  reserva só conta como `in_use` quando `room.current_booking(now)` a
  encontra, o que exige `start_at <= now` (app/models.py:89-99). Check-in
  antecipado (dentro da janela `CHECK_IN_HEADSUP_MINUTES`) seta
  `checked_in_at` (`check_in_booking`, app/bookings/services.py:139-142), mas
  esse campo só é consultado no ramo "reserva já começou" (linha 195) — no
  ramo "ainda não começou" (linhas 203-208) ele é ignorado. Resultado: check-in
  antecipado não muda o status; a sala continua "Começando" até o horário
  agendado chegar.
- Os textos exibidos no painel Android estão em inglês: "Starting Soon" /
  "Available" / "In Use" (display_app/lib/widgets/display_body.dart:29-33).
  Os valores internos (`available`/`starting_soon`/`in_use`) vêm do backend e
  alimentam o enum Dart (display_app/lib/models/display_status.dart:76-87) —
  não precisam mudar, só o texto exibido.

**Proposta de mudança**
- Dados/API: em `resolve_display_state`, quando `checked_in_at is not None`
  (mesmo com `now < start_at`), tratar a reserva como `in_use` e usá-la como
  `headline`, independente da janela de "starting_soon".
- UI: trocar os literais em `display_body.dart` para "Começando" /
  "Disponível" / "Em Uso".

**Dependências**: nenhuma migração de schema; só lógica + strings.

**Decidido**
- `booking.start_at` não é reescrito no check-in antecipado — o horário
  agendado original se mantém. O `checked_in_at` (campo que já existe) passa
  a ser a fonte da informação "começou mais cedo": no relatório (item 3) essa
  reunião aparece com a nota "Reunião começou mais cedo: {checked_in_at em
  HH:mm}" sempre que `checked_in_at < start_at`. Não precisa de coluna nova.
- Fluxo de check-in e fluxo "Iniciar agora" (`startNow`) continuam
  independentes: `startNow` cria uma reserva nova avulsa; check-in apenas
  adianta o status de uma reserva que já existia. Nenhuma unificação entre os
  dois.

## 2. Agendamento por PIN no tablet — já implementado, sem ação pendente

Conferi o código antes de adicionar isso como item novo: o fluxo descrito já
existe de ponta a ponta.
- app/templates/auth/profile.html:44-60 — colaborador define o PIN (4-6
  dígitos) na própria página de perfil.
- app/display/routes.py (`/book`) + app/auth/services.py:42-46
  (`verify_user_pin`) — tablet valida usuário+PIN sem precisar de sessão web.
- app/bookings/services.py (`create_booking`) grava `organizer_username` /
  `organizer_display_name` resolvidos a partir do PIN.
- app/bookings/routes.py (`_booking_to_event`) exibe "{Organizador} -
  {Título}" no calendário web para qualquer reserva, incluindo as feitas pelo
  tablet.
- Coberto por tests/test_display_pin_booking.py.

Se algo específico não está aparecendo como esperado (ex: algum lugar do site
que não mostra o nome de quem reservou via tablet), me diga qual tela para eu
investigar — pelo código hoje isso já funciona.

## 3. Página de relatório com estatísticas de reservas

**Estado atual**: não existe nenhuma rota, template ou query de agregação
para isso — não há ocorrência de "relatorio"/"report"/"estatistica"/
"dashboard" no projeto (fora artefatos de build do Android). app/bookings/routes.py
só tem o calendário e o CRUD de reservas; app/rooms/routes.py só tem
mapa/cadastro/permissões/dispositivos.

**Proposta de mudança (final)**
- Dados: consultas de agregação sobre `Booking` — já tem os campos
  necessários (`room_id`, `organizer_username`, `start_at`/`end_at`,
  `cancelled_at`, `cancelled_by`, `checked_in_at`, `attendees_count`); não
  precisa de schema novo na tabela `booking`.
- Permissão (nova tabela `report_viewer_group`, global, sem `room_id` —
  mesma forma de `RoomBookingGroup`, só sem o vínculo de sala): lista de
  `group_cn` do AD com permissão de ver o relatório. Sem nenhum grupo
  cadastrado = **só admins** veem o relatório (diferente da reserva de sala,
  que por padrão é aberta a todos — aqui o padrão é mais restritivo, por ser
  dado agregado sobre todo mundo. Aviso se quiser inverter esse default).
- UI de permissão: a aba "Permissões" do admin (hoje só
  `rooms/permissions_index.html`, por sala) passa a ter duas seções/abas na
  mesma página:
  - "Agendamento de salas" — exatamente o que já existe hoje, sem mudança.
  - "Relatórios" — lista única (global) de checkboxes de grupos do AD,
    mesmo componente de filtro/busca já usado em `permissions.html`, com
    submit próprio (nova rota) que grava em `report_viewer_group`.
- API/rota do relatório: `GET /rooms/relatorios` (ou equivalente), protegida
  por `current_user.is_admin or bool(set(current_user.group_cns) &
  set(allowed_report_groups))` — mesmo padrão de `Room.is_bookable_by`.
- UI do dashboard: uma página com filtro de período (semana/mês/intervalo
  customizado) e de sala, **dinâmica** (filtra via fetch/JS sem reload de
  página, no mesmo espírito do calendar.js puxando `/api/events`) — sem
  exportação CSV/Excel.
- Métricas exibidas:
  - nº de reservas por sala/período;
  - taxa de ocupação (horas reservadas vs. horário comercial da sala);
  - taxa de no-show (`cancelled_by = 'auto:no-show'`);
  - reservas por organizador;
  - sala mais e menos usada;
  - duração média das reuniões;
  - **pessoa com mais reservas e pessoa com menos reservas** no período
    (entre quem fez pelo menos 1 reserva);
  - reuniões que começaram mais cedo via check-in antecipado, com o horário
    real de início (`checked_in_at`) — ver item 1.
- Visual: como o projeto não usa nenhuma lib de gráfico hoje (só FullCalendar
  via CDN), entra Chart.js via CDN para os gráficos do dashboard.

**Decidido**
- Sem exportação — só dashboard dinâmico em tela.
- Permissão de visualização é **global** (uma lista de grupos só, não por
  sala); dentro do dashboard a pessoa filtra por sala livremente.
- A configuração de quem pode ver o relatório fica unificada na mesma aba
  "Permissões" que já existe para agendamento de salas (duas seções, uma
  página).

---

## Itens levantados em 2026-06-24

Todos os 6 itens abaixo foram implementados em 2026-06-24 (commits desta
sessão) - mantidos aqui como registro da spec original e das decisões
tomadas, no mesmo espírito do item 2 acima.

## 4. Remover campo "Disponibilidade" do modal de nova sala

**Estado atual**
- O modal "Nova sala"/edição de pin (`app/templates/rooms/map.html:87-90`) tem
  um textarea "Disponibilidade" que mapeia para `Room.availability_notes`
  (`app/models.py:24`, `nullable=True`, texto livre sem nenhuma regra de
  negócio atrelada).
- `app/static/js/room_map.js` referencia esse campo em 5 pontos: declaração
  (`:18`), inclusão no array de campos do form (`:28`), reset ao abrir o
  modal pra criar uma sala nova (`:157`, `availabilityInput.value = ""`),
  preenchimento ao abrir o modal pra editar um pin existente (`:190`,
  `availabilityInput.value = room.availability_notes`) e leitura no payload
  enviado ao salvar (`:236`, `availability_notes:
  availabilityInput.value.trim()`).
- Backend: `app/rooms/routes.py:46` (`_room_to_pin`, devolve o campo no JSON
  do pin), `:122`/`:149` (criação) e `:193-194` (update) leem/gravam
  `availability_notes`. Não há nenhuma exibição read-only desse campo em
  outro lugar da UI (confirmado: nenhuma outra referência a
  `roomPinAvailability`/`availability_notes` fora desses pontos) - é só
  usado dentro do próprio modal de admin.

**Proposta de mudança**
- Remover o bloco do textarea em `map.html:87-90`.
- Remover as 5 referências em `room_map.js` listadas acima - sem isso,
  `document.getElementById("roomPinAvailability")` retorna `null` e tanto
  criar quanto editar um pin quebra na primeira interação (`TypeError` ao
  tentar ler/setar `.value` de `null`).
- Manter a coluna `availability_notes` e a leitura/escrita no backend
  intocadas - é `nullable`, sem migração necessária. Salas que já tinham
  essa nota mantêm o dado no banco, só deixa de ser editável/visível pela UI
  a partir de agora (não há onde mais esse valor apareça hoje, então não
  sobra nenhuma exibição "órfã").

**Dependências**: nenhuma migração de schema.

**Implementado**: textarea removido de `map.html`; as 5 referências em
`room_map.js` removidas junto. Coluna e leitura/escrita no backend mantidas
intocadas, como proposto.

## 5. Conceito de Andares/Unidade para upload de planta (restrito a admin)

**Estado atual**
- Existe uma única planta global: model `FloorMap` (`app/models.py:340-350`)
  sem nenhum vínculo de andar/unidade - `FloorMap.query.first()`
  (`app/rooms/routes.py:73`, `:91`) sempre busca a (única) linha existente.
- Upload (`POST /rooms/map/upload`, `routes.py:99-113`) e leitura (`GET
  /rooms/map/image`, `:88-96`) não recebem nem filtram por andar - é "a
  planta do prédio inteiro", uma imagem só pra todas as salas.
- `Room` (`models.py:16-31`) não tem nenhuma referência a andar/unidade - só
  `pos_x`/`pos_y` relativos (0.0-1.0) à única imagem existente.
- O requisito "quem não é admin não pode subir planta" **já é verdade
  hoje**: a rota de upload já tem `@admin_required` (`routes.py:100`,
  decorator em `app/auth/decorators.py:7-14`, checa `current_user.is_admin`).
  Falta é o conceito de múltiplos andares/unidades pra organizar o que já é
  admin-only.

**Proposta de mudança**
- Novo model `Floor` (nome/label, ordem de exibição), substituindo o
  singleton `FloorMap` por uma relação 1 planta por andar (`FloorMap.floor_id`
  FK, ou fundir os dois models em um só).
- `Room.floor_id` (FK pra `Floor`, NOT NULL após migração) - toda sala passa
  a pertencer a um andar/unidade.
- `pos_x`/`pos_y` continuam relativos (0.0-1.0), agora relativos à imagem do
  andar da sala, não a uma imagem global.
- UI do mapa (`map.html`): seletor de andar/unidade (abas ou dropdown) acima
  da imagem; pins filtrados por `room.floor_id == andar_selecionado`; upload
  por andar (`POST /rooms/map/upload` passa a receber `floor_id`),
  continuando `@admin_required`.
- Migração: andar "padrão" criado automaticamente pra herdar a planta e as
  salas já existentes, sem perder a posição de nenhum pin.
- Gestão de andares (criar/renomear/excluir) - nova seção em
  "Configurações", admin-only.

**Dependências**: migração de schema (`Room.floor_id`, novo model `Floor`,
ajuste em `FloorMap`); reescrita de `map_view`/`upload_map`/`map_image` pra
filtrar por andar.

**Perguntas abertas**
- "Andares" e "Unidade" são o mesmo conceito (um nível só, ex: "Andar 1",
  "Andar 2") ou dois níveis hierárquicos diferentes (Unidade = prédio/site,
  contendo vários Andares)? O pedido cita os dois termos juntos
  ("Andares\Unidade") - preciso confirmar antes de desenhar o schema, porque
  um nível só é uma FK simples em `Room`; dois níveis é uma FK em cascata
  (`Floor.unit_id` também).
- O que acontece com uma sala existente ao excluir o andar dela - bloquear a
  exclusão se tiver sala vinculada, ou mover as salas pra um andar "sem
  andar"?

**Decidido**
- Dois níveis hierárquicos: `Unit` (prédio/site) contém vários `Floor`
  (andar) - `Floor.unit_id` é FK pra `Unit`.
- Exclusão bloqueada: não dá pra excluir uma `Unit` com `Floor`s, nem um
  `Floor` com `Room`s - precisa mover/desativar antes.

**Implementado**
- Models `Unit`/`Floor` em `app/models.py` (substituindo o singleton
  `FloorMap`); `Room.floor_id` (FK, nullable por causa do ALTER TABLE em
  banco existente).
- Migração: `_NEW_COLUMNS` em `app/schema_migrations.py` ganhou
  `("room", "floor_id", "INTEGER")`; nova função `ensure_default_floor(db)`
  cria uma `Unit`/`Floor` padrão no primeiro startup, migra a imagem da
  antiga `floor_map` (se existir) pra esse andar, e aponta toda sala sem
  `floor_id` pra ele - chamada em `app/__init__.py` logo depois de
  `ensure_columns`.
- `app/rooms/map_storage.py` reescrito pra operar em `Floor` em vez de
  `FloorMap` (`save_uploaded_map`/`map_image_path`/`delete_map_file` agora
  recebem o andar).
- Rotas em `app/rooms/routes.py`: `map_view`/`map_image`/`upload_map`
  passaram a depender de `floor_id`; `create_pin` exige `floor_id`; CRUD novo
  pra `Unit`/`Floor` (`create_unit`, `rename_unit`, `delete_unit`,
  `create_floor`, `rename_floor`, `delete_floor`), todas `@admin_required`,
  com o bloqueio de exclusão decidido acima. `settings_index` ganhou a aba
  `floors` (`_SETTINGS_TABS`) e passa `units` pro template.
- `app/templates/rooms/map.html`: revisado a pedido do usuário depois da
  primeira versão - o mapa fica só com um botão **"Filtrar"** (dropdown
  simples listando unidade > andares, sem nenhuma ação de gerenciar) acima
  do mapa; upload de planta continua por andar.
- `app/templates/rooms/settings.html`: nova aba **"Andares"** - lista de
  `Unit`s em accordion (clicar numa unidade mostra/esconde os andares dela,
  com renomear/excluir unidade, lista de andares com renomear/excluir/"Ver
  no mapa", e formulário "+ Andar"/"+ Unidade"). Todas as 6 rotas de
  CRUD passaram a redirecionar pra essa aba (`_redirect_to_floors_tab()`)
  em vez de pro mapa.
- `app/static/js/room_map.js`: inclui `floor_id` (de
  `window.READYROOM_CURRENT_FLOOR_ID`) no payload de criação de sala.
- Validado de ponta a ponta via test client: criação de unidade/andar,
  bloqueio de exclusão com vínculo, `create_pin` com/sem `floor_id`,
  renderização do mapa (com "Filtrar", sem "Gerenciar") e da aba Andares
  (com o accordion e os dados certos).

## 6. Lixeira: botão restaurar, preservando a posição do pin

**Estado atual**
- `discard_room` (`app/rooms/routes.py:236-249`, fluxo de arrastar o pin pra
  lixeira no mapa) zera `pos_x`/`pos_y` **e** desativa (`is_active = False`)
  na mesma chamada (linhas 245-247).
- `delete_room` (`routes.py:759-766`, usado pela aba "Lista de salas" em
  Configurações) só desativa, sem tocar em `pos_x`/`pos_y` - esse caminho já
  preserva a posição hoje.
- A query que decide o que aparece no mapa (`pinned_rooms`,
  `routes.py:74-78`) já filtra por `is_active=True AND pos_x is not None AND
  pos_y is not None` - uma sala inativa nunca aparece no mapa,
  independentemente do valor de `pos_x`/`pos_y`.
- A lixeira (`GET /lixeira`, `routes.py:252-256` +
  `app/templates/rooms/trash.html`) lista salas inativas e só oferece
  "Apagar permanentemente" (`routes.py:259-269`, `trash.html:29-33`) - não
  existe rota nem botão de reativação hoje.

**Proposta de mudança**
- Como `pinned_rooms` já exige `is_active=True`, a posição não precisa de
  nenhuma coluna de backup: basta **parar de zerar `pos_x`/`pos_y` em
  `discard_room`** (remover as linhas `room.pos_x = None` / `room.pos_y =
  None`, `routes.py:245-246`). Sala desativada some do mapa só por
  `is_active=False`, com a posição intacta guardada no banco.
- Nova rota `POST /<room_id>/restore` (`@admin_required`): seta `is_active =
  True`, redireciona pra lixeira com flash de confirmação - sem tocar em
  `pos_x`/`pos_y`, que já está preservado.
- Novo botão "Restaurar" em `trash.html`, ao lado de "Apagar
  permanentemente", mesmo padrão de form com `csrf_token` + confirmação.

**Dependências**: nenhuma migração de schema - mudança pequena (1 rota nova
+ remover 2 linhas em `routes.py`, 1 botão em `trash.html`).

**Implementado**: `discard_room` não zera mais `pos_x`/`pos_y`; nova rota
`POST /<room_id>/restore`; botão "Restaurar" em `trash.html`. Teste existente
`test_discard_room_unpins_and_deactivates` foi renomeado/ajustado
(`test_discard_room_deactivates_and_keeps_position`, já que o nome e a
asserção antiga descreviam o comportamento antigo) e foi adicionado
`test_restore_room_reactivates_keeping_position`
(`tests/test_room_admin_routes.py`).

## 7. Relatórios: detalhe ao clicar no card de indicador

**Estado atual**
- O dashboard (`app/templates/reports/dashboard.html:41`, populado por
  `app/static/js/reports.js`) já é dinâmico via fetch (`loadReport()`,
  `reports.js:166-196`, chama `GET /relatorios/dados`) sempre que
  período/sala mudam, sem reload de página.
- 8 cards de indicador (`reports.js:40-76`, função `card()` em `:27-38`):
  Reservas no período, Cancelamentos, Taxa de no-show, Duração média, Sala
  mais usada, Sala menos usada, Quem mais reservou, Quem menos reservou. Hoje
  são `<div>` estáticos - sem `cursor: pointer`, sem listener de clique, sem
  nenhuma forma de abrir detalhe.
- `build_report()` (`app/reports/services.py:17-121`) já calcula tudo a
  partir de uma lista de `Booking` carregada em memória (`bookings`/`active`/
  `cancelled`, linhas 27-34), mas **só devolve os agregados** no JSON -
  exceto `early_started_meetings` (linhas 111-120), que já é uma lista
  detalhada e é exatamente o padrão de "detalhe" que falta nos outros cards.

**Proposta de mudança**
- Cada card (`reports.js`, função `card()`) ganha `cursor: pointer` + um
  listener de clique, abrindo um modal Bootstrap (novo, em `dashboard.html`)
  com uma tabela das reservas que compõem aquele número.
- `build_report()` passa a incluir, junto de cada agregado, a lista de
  bookings correspondente (mesmo padrão já usado em
  `early_started_meetings`): todas as reservas ativas no período, as
  canceladas, as de no-show, e a lista de reservas de cada sala/organizador
  (pra "mais/menos usada" e "mais/menos reservou"). Evita endpoint novo por
  métrica - tudo já vem no mesmo payload de `/relatorios/dados`, já filtrado
  pelo período/sala selecionados.
- JS guarda o último payload recebido (`loadReport`) e, no clique de cada
  card, só filtra/exibe a lista já em memória - sem fetch adicional.

**Dependências**: nenhuma migração de schema (só leitura adicional dos
`Booking`s já carregados em `build_report`); aumenta o tamanho do JSON de
resposta (lista de reservas em vez de só agregados) - aceitável pro volume
esperado (reservas de salas de uma empresa, não milhões de linhas).

**Perguntas abertas**
- Detalhe de "Sala mais/menos usada" e "Quem mais/menos reservou" é a lista
  de reservas daquela sala/pessoa no período - confirma? E os outros 4 cards
  (Reservas no período, Cancelamentos, Taxa de no-show, Duração média) cada
  um mostra a lista completa correspondente (todas as reservas, todas as
  canceladas, todos os no-show, todas ordenadas por duração)?
- Layout do detalhe: modal (proposto acima, mesmo padrão já usado em outras
  telas do projeto) ou uma área expansível abaixo do próprio card?

**Decidido**
- Modal (não área expansível).
- Todos os 8 cards ganham detalhe, com a lista completa correspondente -
  inclusive os 4 que não são por sala/organizador (Reservas no período,
  Cancelamentos, Taxa de no-show, Duração média).

**Implementado**
- `app/reports/services.py`: nova função `_booking_brief()` e 3 listas
  novas no retorno de `build_report()` - `bookings` (ativas),
  `cancelled_bookings`, `no_show_bookings`. Endpoint `/relatorios/dados`
  não precisou mudar (só repassa o dict).
- `app/templates/reports/dashboard.html`: novo modal `#reportDetailModal`.
- `app/static/js/reports.js`: `card()` ganhou um parâmetro `getRows`
  (avaliado só no clique, sempre reflete o filtro atual); os 8 cards em
  `renderSummary()` passam a função de filtro certa (ex: "Sala mais usada"
  filtra `data.bookings` por `room_id`; "Duração média" ordena por
  `duration_minutes`). Sem fetch adicional - tudo já vinha no payload de
  `/relatorios/dados`.
- Validado via test client (`GET /relatorios/dados` retorna as 3 listas
  novas) e suíte de testes existente (`tests/test_reports.py`, sem
  alteração necessária).

## 8. Configurações: alinhar botões "Salvar" e "Restaurar padrão"

**Estado atual**
- Nas duas sub-abas de "Layout do painel" (Site e Tablet), "Salvar" fica
  dentro do `<form>` principal como último elemento (`settings.html:200` e
  `:339`) e "Restaurar padrão" é um `<form>` **separado**, logo depois
  (`:202-206` e `:388-392`), só esse segundo form com `class="d-inline"`. Como
  o primeiro `<form>` não tem `d-inline` (é `display: block`), tudo que vem
  depois dele cai numa linha nova - os dois botões ficam empilhados
  verticalmente (`mt-2` de espaço entre eles), não lado a lado.

**Proposta de mudança**
- Sub-aba Site (`:200-206`): envolver os dois `<form>` (mantendo `action`/
  `onsubmit` de cada um) num `<div class="d-flex gap-2 align-items-center">`,
  cada form com `class="d-inline"` (já tem no segundo, falta no primeiro).
- Sub-aba Tablet: mais trabalho, porque "Salvar" (`:339`) está dentro do
  `#layoutForm`, que só fecha na linha 387 (depois de toda a coluna de
  pré-visualização) - não é viável só com CSS. Pra alinhar lado a lado de
  verdade, mover o bloco do form de "Restaurar padrão" (`:388-392`) pra
  dentro da mesma `<div class="col-lg-6">` do botão "Salvar", logo após a
  linha 339, em vez de deixá-lo solto depois do `</form>`.

**Dependências**: nenhuma (só HTML/CSS no template).

**Implementado**: solução mais robusta que a proposta original - em vez de
mover HTML de um form pra dentro do outro, os botões usam o atributo HTML5
`form="<id>"` (ex: `<button form="layoutForm">`), o que permite os dois
botões serem irmãos visuais dentro de um `<div class="d-flex gap-2">`
mesmo cada um submetendo um `<form>` diferente (com seu próprio `action`/
`onsubmit`/CSRF) em outro lugar do DOM - funciona nas duas sub-abas (Site e
Tablet) sem precisar restructurar o HTML existente em torno dos cards.

## 9. Configurações: renomear aba "Layout do painel" para "Layout"

**Estado atual**
- O texto exato "Layout do painel" aparece como label da aba em
  `settings.html:14` (`<button ...>Layout do painel</button>`) e num
  comentário HTML não renderizado (`:135`). Mensagens de flash no backend
  (`app/rooms/routes.py`, após salvar/restaurar layout) também usam a frase
  "Layout do painel atualizado"/"restaurado" - não fazem parte do pedido
  (são confirmação de ação, não o nome da aba), só registrando que existem
  caso queira alinhar a redação depois.

**Proposta de mudança**
- Trocar o texto do botão da aba (`settings.html:14`) de "Layout do painel"
  para "Layout". Resto (rotas, parâmetro `tab=layout`, IDs como
  `#tab-layout`) não muda - é só o label visível.

**Dependências**: nenhuma.

**Implementado**: label trocado em `settings.html:14`.

