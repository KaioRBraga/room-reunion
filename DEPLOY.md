# Deploy em servidor Linux com outro serviço já em produção

Runbook para subir o ReadyRoom num servidor Linux que já tem outro serviço
rodando, sem alterar nada do que já existe (sem proxy reverso, sem tocar em
configuração, pacotes ou portas do serviço atual). Tudo aqui é aditivo:
usuário próprio, diretório próprio, venv próprio, processo próprio, porta
própria, com limites de CPU/RAM via systemd para nunca disputar recursos com
o que já está rodando.

Execute os comandos no servidor de destino (via SSH), um bloco por vez.

## 0. Levantamento antes de tocar em qualquer coisa

```bash
# Portas já em uso (não escolha nenhuma destas)
sudo ss -tulpn

# CPU/RAM disponíveis - usados para calibrar os limites do passo 5
nproc
free -h

# Versão do Python (precisa de 3.10+)
python3 --version

# Conectividade com o AD (ajuste host/porta se LDAP_PORT for diferente)
nc -zv 10.100.0.10 636

# Firewall ativo na máquina (rode só o que existir)
sudo ufw status 2>/dev/null
sudo firewall-cmd --state 2>/dev/null
```

Anote uma porta livre (ex.: `8000`) para o ReadyRoom — vai ser usada nos
passos 4, 5 e 6. Se a máquina for realmente enxuta (pouca RAM/poucos núcleos),
reduza os limites do passo 5 (`MemoryMax`, `CPUQuota`) na proporção do que o
`free -h`/`nproc` mostrou.

## 1. Usuário e diretório isolados

```bash
sudo useradd --system --home /opt/readyroom --shell /usr/sbin/nologin readyroom
sudo mkdir -p /opt/readyroom
sudo chown "$USER":"$USER" /opt/readyroom   # temporário, só para copiar os arquivos
```

## 2. Copiar o código

Se o repositório está num remoto (GitHub/GitLab) acessível pelo servidor:

```bash
git clone <url-do-repositorio> /opt/readyroom
```

Senão, o Git Bash do Windows não traz `rsync` — use `git archive` (empacota
só os arquivos versionados, já excluindo `.env`, `instance/`, `.venv` etc.
via `.gitignore`) + `scp` (esse já vem no Git Bash). `display_app/` também é
excluído porque é o app Flutter do tablet — não roda no servidor:

```bash
# na raiz do repositório, no Git Bash
git archive --format=tar HEAD -- . ':!display_app' | gzip > /tmp/readyroom.tar.gz
scp /tmp/readyroom.tar.gz aut@10.100.0.97:/tmp/       # nome motsrvaut001 nao resolve fora do servidor; use o IP. -P 2222 se a 22 nao for acessivel de fora

# no servidor (via ssh aut@10.100.0.97)
sudo tar -xzf /tmp/readyroom.tar.gz -C /opt/readyroom
rm /tmp/readyroom.tar.gz
```

## 3. Ambiente Python isolado (venv próprio — não toca no Python global)

```bash
cd /opt/readyroom
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-prod.txt
```

`requirements-prod.txt` reaproveita o `requirements.txt` do projeto e
adiciona só o `gunicorn` (servidor WSGI de produção — o `python run.py` do
modo dev não deve ser usado aqui).

**Plano B se o `pip install` falhar tentando compilar algum pacote** (comum
quando o `python3` do sistema é muito recente — este servidor tem Python
3.14 — e alguma dependência com extensão C, como `cryptography`, `PyMuPDF`
ou `Pillow`, ainda não publicou wheel pronta para essa versão): instale uma
versão mais conservadora do Python só para este venv, sem tocar no
`python3` padrão do sistema (nem em nada usado pelo nginx ou outro serviço):

```bash
sudo apt install python3.12 python3.12-venv
python3.12 -m venv .venv   # repita o venv com este interpretador
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-prod.txt
```

## 4. Configuração (`.env`)

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Ajuste pelo menos:

- `SECRET_KEY` — gere uma chave nova (`python3 -c "import secrets; print(secrets.token_hex(32))"`), não reaproveite a de dev.
- `PUBLIC_BASE_URL=http://10.100.0.97:8000` (necessário para o QR code de pareamento dos tablets funcionar).
- `DOMINIO_AD`, `SERVIDOR_AD`, `BASE_DN`, `LDAP_PORT`, `GRUPOS_ADMIN_SALAS`, `LDAP_SERVICE_USER`, `LDAP_SERVICE_PASSWORD` — dados reais do AD.

Banco fica como SQLite (padrão, arquivo isolado em `instance/`) — não
depende de nenhum banco que o outro serviço já use.

## 5. Inicializar o banco e ajustar dono dos arquivos

```bash
.venv/bin/python -c "from app import create_app; create_app()"
sudo chown -R readyroom:readyroom /opt/readyroom
```

(`create_app()` cria `instance/readyroom.sqlite3` e aplica as migrações leves
automaticamente — ver `app/schema_migrations.py`.)

## 6. Serviço systemd (isolado, com limites de CPU/RAM)

```bash
sudo cp deploy/readyroom.service /etc/systemd/system/readyroom.service
sudo nano /etc/systemd/system/readyroom.service   # confirme/ajuste CPUQuota e MemoryMax (passo 0)
sudo nano deploy/gunicorn_conf.py                 # confirme a porta (bind)
sudo systemctl daemon-reload
sudo systemctl enable --now readyroom
sudo systemctl status readyroom
```

O unit file (`deploy/readyroom.service`) já vem com:

- `CPUQuota=100%` (1 núcleo cheio de 4), `MemoryMax=768M`, `Nice=10`,
  `IOWeight=50` — teto de recursos para nunca competir com o serviço
  existente, calibrado para este servidor (4 núcleos, ~6.7GiB RAM livre).
- `OOMScoreAdjust=200` — se a máquina entrar em pressão de memória, o kernel
  mata o ReadyRoom antes do serviço existente.
- `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome` —
  processo sem privilégios extras e sem acesso a `/home` ou outras áreas do
  sistema.

## 7. Firewall

Neste servidor `ufw` está inativo e `firewalld` nem está instalado — não há
firewall de host bloqueando portas, então **este passo pode ser pulado**.
O acesso à porta 8000 depende só de controle de rede fora do host (security
group, VLAN, ACL de switch/roteador) — confirme com quem administra a rede
que os tablets/usuários que vão acessar o ReadyRoom alcançam essa porta.

Se algum dia um firewall de host for ativado nesta máquina, libere só a
porta nova sem tocar em outras regras:

```bash
# ufw
sudo ufw allow 8000/tcp comment 'ReadyRoom'

# ou firewalld
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## 8. Smoke test

```bash
curl -I http://127.0.0.1:8000/login
journalctl -u readyroom -f
```

E de outra máquina na rede: `http://10.100.0.97:8000/login`.

Confirme que o serviço existente continua respondendo normalmente
(`systemctl status <unit-do-servico-existente>` ou um `curl` na porta dele)
antes e depois de cada passo acima.

## Rollback

Tudo é aditivo e isolado — reverter não afeta o serviço existente:

```bash
sudo systemctl disable --now readyroom
sudo rm /etc/systemd/system/readyroom.service
sudo systemctl daemon-reload
sudo rm -rf /opt/readyroom
sudo userdel readyroom
# se o passo 7 chegou a liberar porta em algum firewall de host:
# sudo ufw delete allow 8000/tcp  (ou firewall-cmd --permanent --remove-port=8000/tcp && firewall-cmd --reload)
```

## Notas

- SQLite serializa escritas; com poucos usuários simultâneos (calendário +
  tablets fazendo polling) isso não é um problema. Se aparecer erro
  `database is locked` em produção, considere ativar `PRAGMA journal_mode=WAL`
  (mudança pequena em `app/extensions.py`, fora do escopo deste deploy).
- `flutter build apk` / instalação via USB (aba Configurações → Layout do
  painel) só funciona executando o navegador na própria máquina onde o
  tablet está plugado — não funciona contra este servidor remoto.
