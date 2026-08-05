import logging
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)


def _smtp_send(app, to_addrs, subject, html_body, text_body):
    cfg = app.config
    server = cfg.get("MAIL_SERVER", "")
    if not server:
        return

    sender = cfg.get("MAIL_FROM") or cfg.get("MAIL_USERNAME", "")
    port = cfg.get("MAIL_PORT", 587)
    use_tls = cfg.get("MAIL_USE_TLS", True)
    username = cfg.get("MAIL_USERNAME", "")
    password = cfg.get("MAIL_PASSWORD", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(server, port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(sender, to_addrs, msg.as_bytes())
        logger.info("Convite enviado para: %s", to_addrs)
    except Exception:
        logger.exception("Falha ao enviar e-mail de convite para %s", to_addrs)


def send_invite_emails(to_addrs, subject, room_name, start_str, end_str, organizer_name,
                       description=None, virtual_room_url=None):
    """Envia convite de reunião para cada endereço de `to_addrs`.

    Executa em thread separada para não atrasar a resposta da API.
    Todos os dados devem ser strings simples (sem objetos ORM).
    """
    if not to_addrs:
        return

    description_html = ""
    description_text = ""
    if description:
        escaped = description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        description_html = (
            "<tr><td colspan='2' style='padding-top:12px;'>"
            f"<strong>Pauta:</strong><br>"
            f"<span style='white-space:pre-line'>{escaped}</span>"
            "</td></tr>"
        )
        description_text = f"\nPauta:\n{description}"

    virtual_html = ""
    virtual_text = ""
    if virtual_room_url:
        virtual_html = (
            "<tr><td style='padding:4px 16px 4px 0;color:#666;'>Sala virtual</td>"
            f"<td><a href='{virtual_room_url}' style='color:#007bbb;'>{virtual_room_url}</a></td></tr>"
        )
        virtual_text = f"\nSala virtual: {virtual_room_url}"

    html_body = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:560px;margin:0 auto;padding:24px;">
  <h2 style="color:#007bbb;margin-bottom:4px;">Convite de Reunião</h2>
  <p style="color:#666;margin-top:0;">Você foi convidado para uma reunião no <strong>ReadyRoom</strong>.</p>
  <table style="border-collapse:collapse;width:100%;margin:16px 0;">
    <tr>
      <td style="padding:4px 16px 4px 0;color:#666;white-space:nowrap;vertical-align:top;">Reunião</td>
      <td><strong>{subject}</strong></td>
    </tr>
    <tr>
      <td style="padding:4px 16px 4px 0;color:#666;vertical-align:top;">Sala</td>
      <td>{room_name}</td>
    </tr>
    <tr>
      <td style="padding:4px 16px 4px 0;color:#666;vertical-align:top;">Data e horário</td>
      <td>{start_str} – {end_str}</td>
    </tr>
    <tr>
      <td style="padding:4px 16px 4px 0;color:#666;vertical-align:top;">Organizador</td>
      <td>{organizer_name}</td>
    </tr>
    {virtual_html}
    {description_html}
  </table>
  <p style="font-size:12px;color:#999;border-top:1px solid #eee;padding-top:12px;margin-top:24px;">
    Este é um e-mail automático do sistema ReadyRoom. Não responda a esta mensagem.
  </p>
</body>
</html>"""

    text_body = (
        f"Convite de Reunião — ReadyRoom\n"
        f"{'=' * 40}\n\n"
        f"Reunião:    {subject}\n"
        f"Sala:       {room_name}\n"
        f"Horário:    {start_str} – {end_str}\n"
        f"Organizador: {organizer_name}"
        f"{virtual_text}"
        f"{description_text}\n\n"
        "Este é um e-mail automático do sistema ReadyRoom."
    )

    app = current_app._get_current_object()
    threading.Thread(
        target=_smtp_send,
        args=(app, to_addrs, subject, html_body, text_body),
        daemon=True,
    ).start()
