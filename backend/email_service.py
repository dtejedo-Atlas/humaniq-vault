"""Envío de emails transaccionales vía Resend (invitaciones y reset de contraseña)."""
import os
import asyncio
import logging
import resend

logger = logging.getLogger(__name__)

resend.api_key = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")


async def _send(to_email: str, subject: str, html: str) -> str:
    if not resend.api_key or not SENDER_EMAIL:
        raise RuntimeError("Servicio de email no configurado (faltan RESEND_API_KEY o SENDER_EMAIL en .env)")
    params = {
        "from": f"Humaniq Talent Vault <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    result = await asyncio.to_thread(resend.Emails.send, params)
    email_id = result.get("id") if isinstance(result, dict) else None
    logger.info(f"Email '{subject}' enviado a {to_email} (id={email_id})")
    return email_id


def _base_template(title: str, greeting: str, body: str, cta_label: str, cta_url: str, footer_note: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="520" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0;">
        <tr>
          <td style="background-color:#0f172a;padding:24px 32px;">
            <span style="color:#ffffff;font-size:18px;font-weight:bold;">Humaniq</span>
            <span style="color:#22d3ee;font-size:18px;font-weight:bold;"> Talent Vault</span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h1 style="margin:0 0 16px 0;font-size:20px;color:#0f172a;">{title}</h1>
            <p style="margin:0 0 8px 0;font-size:14px;color:#334155;line-height:1.6;">{greeting}</p>
            <p style="margin:0 0 24px 0;font-size:14px;color:#334155;line-height:1.6;">{body}</p>
            <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
              <tr><td style="background-color:#0891b2;border-radius:6px;">
                <a href="{cta_url}" style="display:inline-block;padding:12px 28px;color:#ffffff;font-size:14px;font-weight:bold;text-decoration:none;">{cta_label}</a>
              </td></tr>
            </table>
            <p style="margin:24px 0 0 0;font-size:12px;color:#64748b;line-height:1.6;">{footer_note}</p>
            <p style="margin:12px 0 0 0;font-size:11px;color:#94a3b8;line-height:1.5;">Si el botón no funciona, copia y pega este enlace en tu navegador:<br>{cta_url}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px;background-color:#f8fafc;border-top:1px solid #e2e8f0;">
            <p style="margin:0;font-size:11px;color:#94a3b8;">Humaniq Talent Vault — Plataforma de reclutamiento ejecutivo. Si no esperabas este correo, ignóralo.</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_invitation_email(to_email: str, name: str, setup_link: str) -> str:
    html = _base_template(
        title="Te han invitado a Humaniq Talent Vault",
        greeting=f"Hola {name},",
        body="Un administrador te dio de alta en la plataforma de reclutamiento de Humaniq. Para activar tu cuenta, establece tu contraseña con el siguiente botón.",
        cta_label="Establecer mi contraseña",
        cta_url=setup_link,
        footer_note="Este enlace es de un solo uso y expira en 48 horas. Si expira, pide a un administrador que reenvíe la invitación.",
    )
    return await _send(to_email, "Invitación a Humaniq Talent Vault — Establece tu contraseña", html)


async def send_password_reset_email(to_email: str, name: str, reset_link: str) -> str:
    html = _base_template(
        title="Restablece tu contraseña",
        greeting=f"Hola {name},",
        body="Un administrador solicitó el restablecimiento de tu contraseña en Humaniq Talent Vault. Define tu nueva contraseña con el siguiente botón.",
        cta_label="Restablecer contraseña",
        cta_url=reset_link,
        footer_note="Este enlace es de un solo uso y expira en 48 horas. Tu contraseña actual sigue siendo válida hasta que establezcas una nueva.",
    )
    return await _send(to_email, "Humaniq Talent Vault — Restablece tu contraseña", html)
