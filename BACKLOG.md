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

