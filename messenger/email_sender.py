import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
from email.header import Header
import logging

logger = logging.getLogger(__name__)

def send_email(sender_email, password, recipient_email, subject, body, smtp_server="smtp.naver.com", smtp_port=465, attachments=None):
    """
    Sends an email using a specified SMTP server with optional attachments.
    """
    # Force strip whitespace to prevent RFC-5322 errors
    sender_email = sender_email.strip() if sender_email else ""
    recipient_email = recipient_email.strip() if recipient_email else ""
    
    if not sender_email or not password:
        return False, "Email credentials missing."
        
    try:
        # Create a multipart message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = Header(subject, 'utf-8')
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid()

        # Add body to email
        message.attach(MIMEText(body, "plain", "utf-8"))

        # Add attachments
        if attachments:
            for att in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(att['content'])
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {att['name']}",
                )
                message.attach(part)

        # Create secure connection with server and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, password)
            # Naver SMTP is very sensitive to envelope sender vs From header
            server.sendmail(sender_email, [recipient_email], message.as_string())
            
        return True, "Email sent successfully."
    except Exception as e:
        logger.error(f"Email Send Error: {e}")
        return False, str(e)

