# ReadyRoom

Sistema de reserva de salas de reunião. Web app em Flask (calendário, mapa interativo de salas, relatórios e administração) + app Flutter para o painel/tablet fixado na porta de cada sala.

## Estrutura do repositório

```
app/                  # Aplicação Flask (backend + páginas web)
  auth/               # Login via Active Directory (LDAP), sessão, perfil (e-mail, PIN, avatar)
  bookings/           # Reservas: calendário, criação/cancelamento, convidados, sala virtual
  rooms/              # Salas: mapa interativo com pins, lixeira, CRUD admin, permissões, dispositivos,
                      #   identidade visual do site e layout do painel (aba "Configurações")
  display/            # API consumida pelo painel/tablet de cada sala (sem login AD)
  reports/            # Dashboard de estatísticas de reservas (admin / grupos autorizados)
  models.py           # Room, Booking, BookingAttendee, User, FloorMap, RoomBookingGroup,
                      #   ReportViewerGroup, DisplayLayoutSettings, SiteBrandingSettings
  schema_migrations.py # ALTER TABLE leve para colunas novas em bancos já existentes (sem Alembic)
  ldap_client.py       # Bind/consulta no AD (autenticação, grupos, busca de pessoas)
  templates/, static/  # Views Jinja2, CSS e JS (FullCalendar, mapa, relatórios com Chart.js)
config.py             # Configuração (lê .env)
run.py                # Entry point (flask run / python run.py)
instance/             # SQLite (readyroom.sqlite3) e uploads (mapas, avatares - gitignored)
tests/                # Testes pytest
display_app/          # App Flutter do painel de sala (Android/Windows/Web)
BACKLOG.md            # Spec de funcionalidades levantadas antes da implementação
```

## Conceitos principais

- **Room**: sala física. Pode estar "no mapa" (`pos_x`/`pos_y`), tem capacidade mínima de participantes, janela de horário comercial opcional e um `display_token` usado pelo painel para autenticar sem login AD. Desativar uma sala (`is_active=False`) some com ela do mapa e da reserva, mas mantém o histórico — ver **Lixeira** abaixo.
- **Booking**: reserva de uma sala. Tem checagem de conflito de horário (`Booking.find_conflict`), número de participantes, URL de sala virtual (sugestão automática via Jitsi), convidados (`BookingAttendee`) e suporta cancelamento e check-in.
- **FloorMap**: planta baixa atual (PDF/JPG/PNG convertido para PNG) sobre a qual os pins das salas são posicionados.
- **Lixeira de salas**: arrastar um pin até o ícone de lixeira no mapa (ou usar "Desativar" na lista admin) desativa a sala sem apagar nada. A aba **Lixeira** (`/rooms/lixeira`, acessada clicando no ícone de lixeira no mapa) lista as salas desativadas e permite apagá-las **permanentemente** (remove a sala e todo o histórico de reservas via cascade) com confirmação antes de excluir.
- **Painel da sala**: status calculado (`available` / `starting_soon` / `in_use`) com janela de aviso antes do início (`CHECK_IN_HEADSUP_MINUTES`) e tolerância de check-in depois do início (`CHECK_IN_GRACE_MINUTES`); sem check-in dentro do prazo, a reserva expira automaticamente (no-show, `cancelled_by="auto:no-show"`). Também permite agendar direto pelo tablet, autenticado por PIN (ver **Agendamento por PIN**).
- **User**: cadastro local (SQLite), alimentado a cada login bem-sucedido no AD (`app/auth/services.py:upsert_user_login`). Guarda e-mail e PIN (criptografados, vinculados na aba **Perfil**) e foto de perfil.
- **Relatórios**: dashboard agregando reservas por período/sala — nº de reservas, taxa de ocupação, taxa de no-show, duração média, sala/organizador com mais e menos reservas, reuniões iniciadas mais cedo via check-in antecipado. Acesso liberado a admins e a grupos AD listados em `ReportViewerGroup` (configurável na aba Permissões).
- **DisplayLayoutSettings** / **SiteBrandingSettings**: configuração global (singleton, uma linha cada) editada na aba **Configurações** -> **Layout do painel**. A primeira controla a aparência do app do painel (cor por status, visibilidade de elementos) e viaja dentro do próprio payload de `/api/display/status`; a segunda controla a identidade visual do site (ícone, logo, cor primária/secundária) e é aplicada a toda página via context processor + variáveis CSS. Ver seção dedicada abaixo.

## Autenticação

- Usuários comuns fazem login com usuário/senha do AD (`app/ldap_client.py`, bind LDAP/LDAPS). Permissões de admin de salas vêm de pertencer a um dos grupos AD listados em `GRUPOS_ADMIN_SALAS`.
- Separado do admin: cada sala pode ter uma lista de grupos AD autorizados a *reservá-la* (aba "Permissões" -> "Agendamento de salas"). Sala sem grupo associado continua aberta a qualquer usuário logado; administradores sempre podem reservar qualquer sala. Os grupos do usuário são lidos do `memberOf` no login e cacheados na sessão (sem nova consulta LDAP por reserva). A listagem de grupos do AD na tela de admin exige uma conta de serviço somente leitura (`LDAP_SERVICE_USER`/`LDAP_SERVICE_PASSWORD`).
- O acesso ao dashboard de relatórios usa a mesma lógica de grupos, mas é **global** (não por sala) e configurado na aba "Permissões" -> "Relatórios": sem nenhum grupo cadastrado, só administradores veem o relatório.
- **Perfil** (`/auth/profile`): cada usuário vincula seu e-mail (usado para convidar/buscar pessoas em reservas), define uma foto de perfil (recortada/redimensionada para avatar) e um PIN numérico (4-6 dígitos, criptografado com Fernet derivado do `SECRET_KEY`) usado para agendar pelo tablet sem digitar a senha do AD. O PIN atual só é exibido em texto puro depois de confirmar a senha do AD novamente.
- O painel/tablet de cada sala não usa essa sessão: autentica via header `X-Display-Token` (rotas em `/api/display/*`, ver `app/display/auth.py`). Esse blueprint é isento de CSRF porque não usa cookies de sessão. Uma rota específica (`/api/display/book`) permite que qualquer colaborador agende a sala do dia direto no tablet informando usuário + PIN (sem sessão web), respeitando as mesmas permissões/grupos da reserva pelo site.

## Rotas principais

| Prefixo | Blueprint | Acesso |
|---|---|---|
| `/login`, `/logout`, `/profile` | `auth` | público / logado |
| `/bookings` | `bookings` | usuário logado |
| `/rooms` | `rooms` | mapa visível a todos; lixeira, upload de planta, criação/edição de pins e a aba **Configurações** (`/rooms/settings` - lista de salas, dispositivos, layout do painel, permissões) são admin-only |
| `/reports` | `reports` | admin ou grupo AD liberado em `ReportViewerGroup` |
| `/api/display/*` | `display` | token de dispositivo (`X-Display-Token`), usado pelo app Flutter |

## Rodando localmente (backend Flask)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
python run.py
```

`requirements-dev.txt` inclui `requirements.txt` + pytest. Ajuste `SECRET_KEY` e os dados de AD/LDAP no `.env` copiado. O servidor sobe em http://localhost:5000.

Por padrão usa SQLite em `instance/readyroom.sqlite3` (criado automaticamente no primeiro `create_app()`; `app/schema_migrations.py` aplica `ALTER TABLE` para colunas adicionadas depois da primeira versão do schema, sem precisar de Alembic). Para usar outro banco, defina `DATABASE_URL` no `.env`.

### Testes

```bash
pytest
```

Cobrem sobreposição de horários de reserva e convidados (`test_booking_overlap.py`, `test_booking_attendees.py`), restrições de sala/capacidade/horário comercial (`test_room_constraints.py`), permissões de agendamento e de relatório (`test_room_permissions.py`), rotas admin de salas (`test_room_admin_routes.py`), lógica de status do painel (`test_display_status.py`), agendamento por PIN no tablet (`test_display_pin_booking.py`), PIN/perfil (`test_profile_pin.py`) e o dashboard de relatórios (`test_reports.py`).

## Conectando um painel/tablet a uma sala

Aba **Configurações** -> **Dispositivos** (admin-only, `/rooms/settings?tab=devices`): lista todas as salas com um QR code por sala, gerado a partir da URL do servidor + `display_token` (gera/renova o token reaproveitando `rooms.regenerate_display_token`). No app do painel, a tela de configuração tem um botão "Escanear QR code" que lê esse QR (via `mobile_scanner`, `lib/screens/qr_scan_screen.dart`) e preenche URL + token automaticamente, sem digitação manual — útil tanto para tablets fixos quanto para testar rápido em um celular.

## Identidade visual e layout (aba "Configurações" > "Layout do painel")

Admin-only, `/rooms/settings?tab=layout`. Duas sub-abas, cada uma com pré-visualização ao vivo (reage antes de salvar) e botão "Restaurar padrão":

- **Site**: upload de ícone (marca pequena ao lado de "ReadyRoom" na sidebar + favicon da aba do navegador) e logo (wordmark do topo do login e do rodapé da sidebar), além de cor primária e secundária. Os arquivos são normalizados para PNG (`app/rooms/branding_storage.py`) e salvos em `app/static/img/uploads/`; as cores ficam em `SiteBrandingSettings` e são injetadas como variáveis CSS (`--rr-primary`/`--rr-secondary`) num `<style>` inline em `base.html` via context processor (`inject_site_branding`). O resto da paleta (tons de hover/active/claro, sombras, foco de formulário) é derivado dessas duas cores via `color-mix()` em `app.css`, então qualquer cor escolhida propaga pro site inteiro (botões, links, sidebar, FullCalendar, gráficos do relatório) sem precisar editar CSS à mão.
- **Tablet**: cor de cada status (disponível/começando/em uso) e visibilidade de elementos (logo, tags de equipamento, ícone de videoconferência, dica de toque na agenda) do app `display_app`. Persistido em `DisplayLayoutSettings` e enviado pro app Flutter dentro do próprio payload de `/api/display/status` (chave `"layout"`, ver `get_display_status` em `app/bookings/services.py`) - sem endpoint separado, sem precisar reinstalar o app pra refletir a mudança. O botão de "caneta" na pré-visualização revela opções avançadas (posição da agenda, posição do botão de ação, logo exclusiva do tablet). Há também o botão **"Instalar via USB"** (`POST /rooms/layout/install-apk`), que roda `flutter build apk` em `display_app/` antes de instalar - garante que o APK instalado reflete o código atual, em vez de reaproveitar um build antigo esquecido em `display_app/build/`. Depois do build, roda `adb devices` + `adb install -r` no(s) dispositivo(s) conectado(s). Só funciona quando o navegador acessa o servidor a partir da própria máquina onde o tablet está plugado, com `adb`/`flutter` no PATH ou localizáveis via `ANDROID_HOME`/`ANDROID_SDK_ROOT`/`FLUTTER_ROOT` (`_resolve_adb_path`/`_resolve_flutter_path`, que cobrem o caso comum dessas ferramentas funcionarem no terminal do Flutter sem estarem no PATH do sistema). Depois de instalar com sucesso, a rota também roda `adb reverse tcp:<porta> tcp:<porta>` (porta de quem acessou a página) em cada dispositivo - assim o app recém-instalado já consegue testar contra `http://127.0.0.1:<porta>` sem precisar configurar o IP de rede manualmente.

## App do painel (`display_app/`)

App Flutter (Android/Windows/Web) que fica fixado na entrada da sala. Consome a API `/api/display/*` usando o token configurado na tela de setup (`lib/screens/setup_screen.dart`, persistido com `shared_preferences`), preenchido por QR code ou manualmente. Mostra o status atual da sala e a agenda do dia (`lib/widgets/day_timeline.dart`, `display_body.dart`) e permite check-in, encerrar reunião, estender, iniciar uma reserva avulsa ("começar agora") ou agendar um horário livre do próprio dia direto no painel via usuário + PIN (`lib/widgets/pin_booking_sheet.dart`).

```bash
cd display_app
flutter pub get
flutter run
```

(ou `flutter build apk` / `flutter build windows`). Configure a URL base da API e o token do dispositivo na tela de setup do app, apontando para a instância Flask publicada (não localhost, salvo testes na mesma máquina).

## Variáveis de ambiente (`.env`)

Ver `.env.example`. Principais:

- `SECRET_KEY` — chave de sessão Flask (troque em produção); também usada para derivar a chave de criptografia do PIN do tablet (`app/auth/pin_crypto.py`).
- `DATABASE_URL` — opcional; default é SQLite local.
- `DOMINIO_AD`, `SERVIDOR_AD`, `BASE_DN`, `LDAP_PORT` — conexão com o Active Directory.
- `GRUPOS_ADMIN_SALAS` — grupos (cn) do AD com permissão de administrar salas.
- `LDAP_SERVICE_USER`, `LDAP_SERVICE_PASSWORD` — conta de serviço (somente leitura) usada para listar grupos do AD na aba de permissões e para checar permissão/grupo de quem agenda pelo PIN do tablet, fora do fluxo de login.
- `AD_GROUP_PREFIXES` — prefixos do cn (separados por vírgula) para filtrar a listagem de grupos do AD; sem isso a lista traz todos os grupos do AD, incluindo os nativos do Windows (vazio lista todos).
- `MAX_UPLOAD_MB` — limite de upload da planta baixa e de fotos de perfil.
- `PUBLIC_BASE_URL` — URL fixa do servidor (ex: `http://10.100.0.20:5000`) usada para montar o QR code de pareamento na aba Dispositivos. Sem isso, o QR usa a URL que o admin digitou no navegador — se for `localhost`/`127.0.0.1`, o painel (outro dispositivo) não vai conseguir alcançar o servidor.
- `CHECK_IN_HEADSUP_MINUTES`, `CHECK_IN_GRACE_MINUTES`, `DISPLAY_START_NOW_MINUTES` — janelas de tempo usadas pela lógica do painel (aviso de início, tolerância de check-in/no-show, duração da reserva avulsa "começar agora").
