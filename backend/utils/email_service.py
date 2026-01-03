"""
Email verification service using Gmail SMTP
Send OTP for email verification
"""
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os

# Store OTPs temporarily (in production, use Redis or database)
otp_storage = {}

def generate_otp():
    """Generate 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email, otp):
    """
    Send OTP verification email
    
    Configure these environment variables:
    - SMTP_EMAIL: Your Gmail address
    - SMTP_PASSWORD: Your Gmail app password (not regular password)
    """
    
    # Get SMTP credentials from environment variables
    smtp_email = os.getenv('SMTP_EMAIL', 'your-email@gmail.com')
    smtp_password = os.getenv('SMTP_PASSWORD', 'your-app-password')
    
    # Create message
    message = MIMEMultipart('alternative')
    message['Subject'] = 'RupX - Verify Your Email'
    message['From'] = f'RupX <{smtp_email}>'
    message['To'] = to_email
    
    # HTML email body
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #0a0a0a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%); border-radius: 16px; padding: 40px; border: 1px solid rgba(255, 120, 73, 0.2);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #ff7849; font-size: 2.5rem; margin: 0;"><img src="RupX_Logo.png" alt="RupX Logo" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; display: block;"> RupX</h1>
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
    
    # Attach HTML part
    part = MIMEText(html, 'html')
    message.attach(part)
    
    try:
        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(smtp_email, smtp_password)
        
        # Send email
        server.send_message(message)
        server.quit()
        
        print(f"✅ OTP email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
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
    print(f"🔍 Verifying OTP for {email}")
    print(f"📋 Current OTP storage: {list(otp_storage.keys())}")
    
    if email not in otp_storage:
        print(f"❌ No OTP found for {email}")
        return False, 'No OTP found for this email'
    
    stored = otp_storage[email]
    
    # Check expiry
    if datetime.now() > stored['expiry']:
        del otp_storage[email]
        print(f"⏰ OTP expired for {email}")
        return False, 'OTP expired'
    
    # Check attempts (max 3)
    if stored['attempts'] >= 3:
        del otp_storage[email]
        print(f"🚫 Too many attempts for {email}")
        return False, 'Too many attempts'
    
    # Verify OTP
    if stored['otp'] == otp:
        del otp_storage[email]
        print(f"✅ OTP verified for {email}")
        return True, 'Verified'
    else:
        stored['attempts'] += 1
        print(f"❌ Invalid OTP for {email} (attempt {stored['attempts']}/3)")
        return False, 'Invalid OTP'

def resend_otp(email):
    """Resend OTP to email"""
    if email in otp_storage:
        # Delete old OTP
        del otp_storage[email]
    
    # Create new OTP
    otp = create_otp(email)
    
    # Send email
    success = send_verification_email(email, otp)
    
    return success