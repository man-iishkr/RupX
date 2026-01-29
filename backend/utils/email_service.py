"""
Email verification service using Brevo SMTP
Send OTP for email verification
"""
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import requests

# Store OTPs temporarily (in production, use Redis or database)
otp_storage = {}

def generate_otp():
    """Generate 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

 

def send_verification_email(to_email, otp):
    """
    Send OTP verification email using Brevo HTTP API
    This bypasses SMTP port blocking on Render.
    """
    api_key = os.getenv('SMTP_PASSWORD') 
    sender_email = os.getenv('SMTP_EMAIL')
    
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key
    }
    
    payload = {
        "sender": {"name": "RupX", "email": sender_email},
        "to": [{"email": to_email}],
        "subject": "RupX - Verify Your Email",
        "htmlContent": f"""
            <html>
        <body style="font-family: Arial, sans-serif; background-color: #0a0a0a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%); border-radius: 16px; padding: 40px; border: 1px solid rgba(255, 120, 73, 0.2);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #ff7849; font-size: 2.5rem; margin: 0;">RupX</h1>
                    <p style="color: #b0b0b0; margin-top: 10px;">AI-Powered Attendance Tracking</p>
                </div>
                
                <h2 style="color: #ffffff; margin-bottom: 20px;">Verify Your Email</h2>
                
                <p style="color: #b0b0b0; line-height: 1.6; margin-bottom: 30px;">
                    Thank you for signing up with RupX! To complete your registration, please verify your email address using the OTP below:
                </p>
                
                <div style="background: rgba(255, 120, 73, 0.1); border: 2px solid #ff7849; border-radius: 12px; padding: 30px; text-align: center; margin: 30px 0;">
                    <p style="color: #b0b0b0; margin: 0 0 10px 0; font-size: 14px;">Your Verification Code</p>
                    <h1 style="color: #ff7849; font-size: 3rem; letter-spacing: 10px; margin: 0; font-family: 'Courier New', monospace;">{otp}</h1>
                </div>
                
                <p style="color: #b0b0b0; line-height: 1.6; margin-bottom: 20px;">
                    This OTP will expire in <strong style="color: #ff7849;">10 minutes</strong>.
                </p>
                
                <p style="color: #b0b0b0; line-height: 1.6;">
                    If you didn't request this verification, please ignore this email.
                </p>
                
                <hr style="border: none; border-top: 1px solid rgba(255, 120, 73, 0.2); margin: 30px 0;">
                
                <p style="color: #666; font-size: 12px; text-align: center;">
                    © 2026 RupX. All rights reserved.<br>
                    This is an automated email, please do not reply.
                </p>
            </div>
        </body>
    </html>
        """
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [201, 200, 202]:
            print(f"✅ OTP email sent via API to {to_email}")
            return True
        else:
            print(f"❌ Brevo API Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False
def create_otp(email):
    """Create and store OTP for email"""
    otp = generate_otp()
    expiry = datetime.now() + timedelta(minutes=10)
    
    otp_storage[email] = {
        'otp': otp,
        'expiry': expiry,
        'attempts': 0
    }
    
    print(f"📝 OTP created for {email}: {otp} (expires in 10 min)")
    return otp

def verify_otp(email, otp):
    """Verify OTP for email"""
    if email not in otp_storage:
        return False, 'No OTP found for this email'
    
    stored = otp_storage[email]
    
    if datetime.now() > stored['expiry']:
        del otp_storage[email]
        return False, 'OTP expired'
    
    if stored['attempts'] >= 3:
        del otp_storage[email]
        return False, 'Too many attempts'
    
    if stored['otp'] == otp:
        del otp_storage[email]
        return True, 'Verified'
    else:
        stored['attempts'] += 1
        return False, 'Invalid OTP'

def resend_otp(email):
    """Resend OTP to email"""
    if email in otp_storage:
        del otp_storage[email]
    
    otp = create_otp(email)
    success = send_verification_email(email, otp)
    return success