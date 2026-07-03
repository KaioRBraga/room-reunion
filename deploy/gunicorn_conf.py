
import os

# Porta escolhida durante o deploy (ver DEPLOY.md, passo "Escolher uma porta livre").
# Pode ser sobrescrita sem editar este arquivo: GUNICORN_BIND=0.0.0.0:8080 systemctl ...
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# Maquina enxuta / SQLite (escreve serializado) -> poucos workers evita
# disputar CPU com o servico que ja roda na maquina e excesso de lock no banco.
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))

accesslog = "-"
errorlog = "-"
