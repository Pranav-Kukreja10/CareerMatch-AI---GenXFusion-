import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)


def _send_transactional_email(recipient_email: str, subject: str, html_content: str, plain_summary: str) -> dict:
    """
    Unified transactional email dispatcher supporting:
    1. Google SMTP (smtp.gmail.com) via App Passwords for unrestricted recipient delivery
    2. Resend API fallback
    3. Terminal console logging fallback
    """
    recipient_clean = recipient_email.strip()
    
    # Check Django settings first, then fallback to environment variables
    try:
        from django.conf import settings
        smtp_user = getattr(settings, "EMAIL_HOST_USER", "").strip() or os.getenv("EMAIL_HOST_USER", "").strip()
        smtp_pass = getattr(settings, "EMAIL_HOST_PASSWORD", "").strip() or os.getenv("EMAIL_HOST_PASSWORD", "").strip()
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "").strip() or os.getenv("DEFAULT_FROM_EMAIL", "").strip()
    except Exception:
        smtp_user = os.getenv("EMAIL_HOST_USER", "").strip()
        smtp_pass = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
        from_email = os.getenv("DEFAULT_FROM_EMAIL", "").strip()

    smtp_pass = smtp_pass.replace(" ", "")
    if not from_email:
        from_email = f"CareerMatch AI No-Reply <{smtp_user}>" if smtp_user else "CareerMatch AI No-Reply <noreply@careermatch.ai>"

    # 1. Attempt delivery via Google / Standard SMTP if configured
    if smtp_user and smtp_pass:
        try:
            from django.core.mail import EmailMultiAlternatives
            reply_to = os.getenv("REPLY_TO_EMAIL", "noreply@careermatch.ai")

            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_summary,
                from_email=from_email,
                to=[recipient_clean],
                reply_to=[reply_to]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            logger.info(f"Email successfully delivered via Google SMTP to {recipient_clean}")
            print(f"[EMAIL SERVICE] Successfully dispatched email to {recipient_clean} via Google SMTP (From: {from_email})")
            return {
                "status": "sent",
                "provider": "google_smtp",
                "recipient": recipient_clean
            }
        except Exception as e:
            err_msg = f"Google SMTP delivery failed: {str(e)}"
            logger.warning(f"{err_msg}. Falling back to Resend API...")
            print(f"[EMAIL SERVICE WARNING] {err_msg}. Falling back to Resend API...")

    # 2. Fallback to Resend API
    resend_api_key = os.getenv("EMAIL_API") or os.getenv("RESEND_API_KEY")
    if resend_api_key:
        sender_address = os.getenv("DEFAULT_FROM_EMAIL", "CareerMatch AI No-Reply <onboarding@resend.dev>")
        reply_to_email = os.getenv("REPLY_TO_EMAIL", "noreply@careermatch.ai")
        headers = {
            "Authorization": f"Bearer {resend_api_key.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": sender_address,
            "to": [recipient_clean],
            "reply_to": reply_to_email,
            "subject": subject,
            "html": html_content
        }

        try:
            response = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                logger.info(f"Resend email sent successfully to {recipient_clean}: {response.text}")
                return {
                    "status": "sent",
                    "provider": "resend",
                    "resend_id": response.json().get("id")
                }
            else:
                logger.warning(f"Resend API responded with {response.status_code}: {response.text}")
                return {
                    "status": "api_warning",
                    "message": f"Resend API response: {response.text}"
                }
        except Exception as e:
            logger.error(f"Failed to deliver email via Resend: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    return {
        "status": "logged_to_console",
        "message": "Email logged to development console."
    }


def send_password_reset_otp(recipient_email: str, otp_code: str) -> dict:
    """
    Dispatches a branded no-reply email containing
    the 6-digit password reset OTP.
    """
    print(f"\n==================================================")
    print(f" [CAREERMATCH AI NO-REPLY SECURITY NOTIFICATION]")
    print(f" Recipient: {recipient_email}")
    print(f" Password Reset OTP: [ {otp_code} ]")
    print(f" Valid for: 10 minutes")
    print(f"==================================================\n")

    subject = f"[CareerMatch AI] Your Password Reset Code: {otp_code}"
    plain_summary = f"Your CareerMatch AI password reset code is {otp_code}. Valid for 10 minutes. Please do not reply."

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Reset Your CareerMatch AI Password</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" max-width="540" border="0" cellspacing="0" cellpadding="0" style="max-width: 540px; background-color: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
              <!-- Brand Header -->
              <tr>
                <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 32px; text-align: center;">
                  <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">
                    Skill <span style="color: #14b8a6;">Setu</span>
                  </h1>
                  <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;">
                    Academia &bull; Industry &bull; Innovation
                  </p>
                </td>
              </tr>

              <!-- Main Body -->
              <tr>
                <td style="padding: 40px 36px;">
                  <h2 style="margin: 0 0 12px 0; color: #0f172a; font-size: 20px; font-weight: 700;">
                    Password Reset Verification Code
                  </h2>
                  <p style="margin: 0 0 24px 0; color: #475569; font-size: 14px; line-height: 1.6;">
                    We received a request to reset the password for your CareerMatch AI account. Enter the verification code below in your browser:
                  </p>

                  <!-- OTP Code Display -->
                  <div style="background-color: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin: 28px 0;">
                    <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #0f172a; display: inline-block;">
                      {otp_code}
                    </span>
                  </div>

                  <p style="margin: 0 0 16px 0; color: #64748b; font-size: 13px; line-height: 1.5;">
                    &bull; This one-time code is valid for <strong>10 minutes</strong>.<br>
                    &bull; If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.
                  </p>
                </td>
              </tr>

              <!-- Automated Footer -->
              <tr>
                <td style="background-color: #f8fafc; border-top: 1px solid #f1f5f9; padding: 24px 36px; text-align: center;">
                  <p style="margin: 0; color: #94a3b8; font-size: 12px; line-height: 1.5;">
                    This is an automated security message from CareerMatch AI.<br>
                    <strong>Please do not reply directly to this email.</strong>
                  </p>
                  <p style="margin: 8px 0 0 0; color: #cbd5e1; font-size: 11px;">
                    &copy; 2026 CareerMatch AI Inc. All rights reserved.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    return _send_transactional_email(recipient_email, subject, html_content, plain_summary)


def send_welcome_verification_email(recipient_email: str, full_name: str, role: str, otp_code: str, verification_token: str) -> dict:
    """
    Dispatches a branded welcome & email verification notification
    with a 6-digit OTP code and a 1-click verification link.
    """
    client_base_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    direct_verify_url = f"{client_base_url}?verify_token={verification_token}&email={recipient_email}"

    print(f"\n==================================================")
    print(f" [CAREERMATCH AI WELCOME & VERIFICATION NOTIFICATION]")
    print(f" Recipient: {recipient_email}")
    print(f" Name: {full_name} ({role})")
    print(f" Verification OTP: [ {otp_code} ]")
    print(f" Direct Verify URL: {direct_verify_url}")
    print(f" Valid for: 24 hours")
    print(f"==================================================\n")

    role_titles = {
        "STUDENT": "Student / Candidate Ecosystem",
        "CANDIDATE": "Student / Candidate Ecosystem",
        "RECRUITER": "Enterprise Recruitment Network",
        "ACADEMIA": "Institutional Placement & Academic Hub"
    }
    role_headline = role_titles.get(role, "CareerMatch AI Platform")

    subject = f"[CareerMatch AI] Welcome! Verify your email address ({otp_code})"
    plain_summary = f"Welcome to CareerMatch AI, {full_name}! Your email verification code is {otp_code}. Direct link: {direct_verify_url}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Welcome to CareerMatch AI</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" max-width="560" border="0" cellspacing="0" cellpadding="0" style="max-width: 560px; background-color: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
              <!-- Brand Header -->
              <tr>
                <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 36px 32px; text-align: center;">
                  <h1 style="margin: 0; color: #ffffff; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">
                    Skill <span style="color: #14b8a6;">Setu</span>
                  </h1>
                  <p style="margin: 8px 0 0 0; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;">
                    {role_headline}
                  </p>
                </td>
              </tr>

              <!-- Main Body -->
              <tr>
                <td style="padding: 40px 36px;">
                  <h2 style="margin: 0 0 12px 0; color: #0f172a; font-size: 22px; font-weight: 700;">
                    Welcome, {full_name or 'there'}!
                  </h2>
                  <p style="margin: 0 0 20px 0; color: #475569; font-size: 14px; line-height: 1.6;">
                    Thank you for creating an account on <strong>CareerMatch AI</strong>. Your profile is ready. To complete your security onboarding and earn the <strong>Verified Account</strong> badge, please verify your email address.
                  </p>

                  <!-- 6-Digit Code -->
                  <div style="background-color: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin: 24px 0;">
                    <span style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #64748b; font-weight: 600; display: block; margin-bottom: 8px;">Your 6-Digit Verification Code</span>
                    <span style="font-family: 'Courier New', Courier, monospace; font-size: 34px; font-weight: 800; letter-spacing: 10px; color: #0f172a; display: inline-block;">
                      {otp_code}
                    </span>
                  </div>

                  <!-- 1-Click Verification Action Button -->
                  <div style="text-align: center; margin: 28px 0 20px 0;">
                    <a href="{direct_verify_url}" style="display: inline-block; background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff; text-decoration: none; font-weight: 600; font-size: 14px; padding: 14px 32px; border-radius: 9999px; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);">
                      Verify Email Address
                    </a>
                  </div>

                  <p style="margin: 24px 0 0 0; color: #64748b; font-size: 13px; line-height: 1.5;">
                    &bull; This verification code expires in <strong>24 hours</strong>.<br>
                    &bull; You can continue using CareerMatch AI immediately without waiting for verification.<br>
                    &bull; If you did not create this account, you can safely ignore this email.
                  </p>
                </td>
              </tr>

              <!-- Automated No-Reply Footer -->
              <tr>
                <td style="background-color: #f8fafc; border-top: 1px solid #f1f5f9; padding: 24px 36px; text-align: center;">
                  <p style="margin: 0; color: #94a3b8; font-size: 12px; line-height: 1.5;">
                    This is an automated message from CareerMatch AI.<br>
                    <strong>Please do not reply directly to this email.</strong>
                  </p>
                  <p style="margin: 8px 0 0 0; color: #cbd5e1; font-size: 11px;">
                    &copy; 2026 CareerMatch AI Inc. All rights reserved.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    return _send_transactional_email(recipient_email, subject, html_content, plain_summary)
