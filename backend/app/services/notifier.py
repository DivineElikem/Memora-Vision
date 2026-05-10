import smtplib
from email.mime.text import MIMEText
from app.core.config import get_settings

def send_alert_email(rule_text: str, message: str):
    settings = get_settings()
    
    body = f"""
    Agentic Vision Alert Triggered!
    
    Rule: {rule_text}
    Details: {message}
    
    This is an automated notification.
    """
    
    msg = MIMEText(body)
    msg['Subject'] = f"Alert: {rule_text}"
    msg['From'] = settings.smtp_sender
    msg['To'] = settings.alert_email_receiver
    
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        print(f"Alert email sent for rule: {rule_text}")
    except Exception as e:
        print(f"Failed to send alert email: {e}")
