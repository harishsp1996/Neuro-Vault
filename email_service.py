"""
Complete Email Service Module for HelperGPT Support Case Extension
Enhanced with SMTP integration for support cases with department routing
"""
import os
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any
from datetime import datetime
from jinja2 import Template
from openai import AsyncAzureOpenAI
from database import get_db_connection

logger = logging.getLogger(__name__)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "192.168.1.252")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "ccd@bsolsystems.com")

# Department emails
HR_SUPPORT_EMAIL = os.getenv("HR_SUPPORT_EMAIL", "hrsupport@company.com")
CLOUD_SUPPORT_EMAIL = os.getenv("CLOUD_SUPPORT_EMAIL", "harishsp@bsolsystems.com")
HARDWARE_SUPPORT_EMAIL = os.getenv("HARDWARE_SUPPORT_EMAIL", "hardware@company.com")

# Azure OpenAI for email generation
azure_openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

GPT_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

class EmailService:
    def __init__(self):
        self.department_directory = {}
        self.email_templates = {}
        
    async def initialize_email_directory(self):
        """Initialize email directory with department mappings"""
        try:
            self.department_directory = {
                "hardware": {
                    "department_name": "IT Hardware Support",
                    "primary_email": HARDWARE_SUPPORT_EMAIL,
                    "secondary_email": "hardware-manager@company.com",
                    "issue_categories": ["laptop_wont_start", "screen_issues", "keyboard_mouse_issues", "battery_charging"],
                    "priority": "high"
                },
                "software": {
                    "department_name": "IT Software Support", 
                    "primary_email": "software@company.com",
                    "secondary_email": "software-manager@company.com",
                    "issue_categories": ["slow_performance", "application_crashes", "login_issues", "system_updates"],
                    "priority": "medium"
                },
                "cloud": {
                    "department_name": "Cloud Support Team",
                    "primary_email": CLOUD_SUPPORT_EMAIL,
                    "secondary_email": "cloud-manager@company.com", 
                    "issue_categories": ["aws_issues", "azure_problems", "deployment_problems", "cloud_access"],
                    "priority": "high"
                },
                "wfh": {
                    "department_name": "HR Support",
                    "primary_email": HR_SUPPORT_EMAIL,
                    "secondary_email": "hr-manager@company.com",
                    "issue_categories": ["leave_request", "remote_work_policy", "wfh_equipment", "sick_leave"],
                    "priority": "medium"
                },
                "network": {
                    "department_name": "Network Support",
                    "primary_email": "network@company.com",
                    "secondary_email": "network-manager@company.com",
                    "issue_categories": ["wifi_connection", "vpn_issues", "internet_slow"],
                    "priority": "medium"
                },
                "security": {
                    "department_name": "Security Team",
                    "primary_email": "security@company.com",
                    "secondary_email": "ciso@company.com",
                    "issue_categories": ["malware_suspected", "password_reset", "account_locked"],
                    "priority": "critical"
                }
            }
            
            logger.info("Email directory initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing email directory: {str(e)}")
    
    async def send_support_case_email(self, case_number: str, conversation_history: list, department_email: str = None):
        """Send support case email via SMTP"""
        try:
            # Get case details
            case_data = await self.get_case_details(case_number)
            if not case_data:
                return {"success": False, "error": "Case not found"}
            
            # Determine recipient email
            recipient_email = department_email or self.get_department_email(case_data.get("issue_category"))
            
            # Generate professional email content
            email_content = await self.generate_case_email_content(case_data, conversation_history)
            
            # Send via SMTP
            smtp_result = await self.send_smtp_email(
                to_email=recipient_email,
                subject=f"Support Case {case_number} - {case_data.get('issue_category', 'General').title()} Issue",
                body=email_content,
                case_number=case_number
            )
            
            # Log email sent
            await self.log_email_sent(case_number, recipient_email, smtp_result)
            
            return {
                "success": smtp_result["success"],
                "recipients": [recipient_email],
                "email_id": smtp_result.get("message_id"),
                "error": smtp_result.get("error")
            }
            
        except Exception as e:
            logger.error(f"Error sending support case email: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def send_smtp_email(self, to_email: str, subject: str, body: str, case_number: str = None):
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = FROM_EMAIL
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'html'))
            
            # Connect to SMTP server
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                if EMAIL_PASSWORD:
                    server.login(EMAIL_USER, EMAIL_PASSWORD)
                
                # Send email
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {to_email} for case {case_number}")
            return {
                "success": True,
                "message_id": f"{case_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
        except Exception as e:
            logger.error(f"SMTP email sending failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_department_email(self, category: str) -> str:
        """Get department email based on category"""
        department_emails = {
            "hardware": HARDWARE_SUPPORT_EMAIL,
            "software": "software@company.com", 
            "cloud": CLOUD_SUPPORT_EMAIL,
            "wfh": HR_SUPPORT_EMAIL,
            "network": "network@company.com",
            "security": "security@company.com"
        }
        return department_emails.get(category, "support@company.com")
    
    async def generate_case_email_content(self, case_data: dict, conversation_history: list) -> str:
        """Generate professional email content for support case"""
        try:
            # Use AI to generate professional email content
            system_prompt = """You are a professional support system generating emails for technical support teams. Create a well-structured, professional email that includes all relevant case information.

Email should include:
- Professional greeting
- Case summary with key details
- User information  
- Issue description and category
- Troubleshooting steps attempted
- Conversation history (if available)
- Priority level
- Next steps recommendations
- Professional closing

Format as HTML email."""
            
            user_prompt = f"""Generate professional support case email:

Case Details:
- Case Number: {case_data.get('case_number', 'Unknown')}
- User: {case_data.get('user_name', 'Unknown')} ({case_data.get('user_email', 'No email')})
- Category: {case_data.get('issue_category', 'General')}  
- Priority: {case_data.get('severity_level', 'Medium')}
- Department: {case_data.get('assigned_department', 'Support')}
- Created: {case_data.get('created_at', 'Unknown')}

Issue Description:
{case_data.get('issue_description', 'No description available')}

Troubleshooting Steps Attempted:
{case_data.get('troubleshooting_steps', 'None documented')}

Conversation History:
{json.dumps(conversation_history, indent=2) if conversation_history else 'No conversation history'}

Create a professional email to the support team."""
            
            response = await azure_openai_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            email_content = response.choices[0].message.content.strip()
            
            # Fallback template if AI generation fails
            if not email_content or len(email_content) < 100:
                email_content = self.get_fallback_email_template(case_data, conversation_history)
            
            return email_content
            
        except Exception as e:
            logger.error(f"Error generating email content: {str(e)}")
            return self.get_fallback_email_template(case_data, conversation_history)
    
    def get_fallback_email_template(self, case_data: dict, conversation_history: list) -> str:
        """Fallback email template"""
        return f"""
        <html>
        <body>
        <h2>Support Case: {case_data.get('case_number', 'Unknown')}</h2>
        
        <h3>Case Details:</h3>
        <ul>
            <li><strong>User:</strong> {case_data.get('user_name', 'Unknown')} ({case_data.get('user_email', 'No email')})</li>
            <li><strong>Category:</strong> {case_data.get('issue_category', 'General')}</li>
            <li><strong>Priority:</strong> {case_data.get('severity_level', 'Medium')}</li>
            <li><strong>Created:</strong> {case_data.get('created_at', 'Unknown')}</li>
        </ul>
        
        <h3>Issue Description:</h3>
        <p>{case_data.get('issue_description', 'No description available')}</p>
        
        <h3>Troubleshooting Steps Attempted:</h3>
        <p>{case_data.get('troubleshooting_steps', 'None documented')}</p>
        
        <h3>Conversation History:</h3>
        <pre>{json.dumps(conversation_history, indent=2) if conversation_history else 'No conversation history'}</pre>
        
        <p><strong>Please review and take appropriate action.</strong></p>
        
        <p>Best regards,<br>
        HelperGPT Support System</p>
        </body>
        </html>
        """
    
    async def get_case_details(self, case_number: str) -> Optional[dict]:
        """Get support case details from database"""
        try:
            conn = await get_db_connection()
            cursor = await conn.execute("""
                SELECT * FROM support_cases WHERE case_number = ?
            """, (case_number,))
            row = await cursor.fetchone()
            await conn.close()
            
            if row:
                return {
                    "id": row[0],
                    "case_number": row[1],
                    "user_name": row[2],
                    "user_email": row[3],
                    "issue_category": row[4],
                    "issue_description": row[5],
                    "severity_level": row[6],
                    "status": row[7],
                    "assigned_department": row[8],
                    "assigned_email": row[9],
                    "conversation_log": row[10],
                    "troubleshooting_steps": row[11],
                    "resolution_notes": row[12],
                    "created_at": row[13],
                    "updated_at": row[14],
                    "resolved_at": row[15],
                    "escalated": bool(row[16]) if row[16] is not None else False
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting case details: {str(e)}")
            return None
    
    async def log_email_sent(self, case_number: str, recipient: str, smtp_result: dict):
        """Log email sending to database"""
        try:
            conn = await get_db_connection()
            
            # Create email log table if it doesn't exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS email_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_number TEXT,
                    recipient_email TEXT,
                    subject TEXT,
                    success BOOLEAN,
                    message_id TEXT,
                    error_message TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert email log
            await conn.execute("""
                INSERT INTO email_log (case_number, recipient_email, success, message_id, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                case_number,
                recipient,
                smtp_result.get("success", False),
                smtp_result.get("message_id"),
                smtp_result.get("error")
            ))
            
            # Update support case to mark email sent
            await conn.execute("""
                UPDATE support_cases 
                SET email_sent = ?, updated_at = CURRENT_TIMESTAMP
                WHERE case_number = ?
            """, (smtp_result.get("success", False), case_number))
            
            await conn.commit()
            await conn.close()
            
            logger.info(f"Email log recorded for case {case_number}")
            
        except Exception as e:
            logger.error(f"Error logging email: {str(e)}")
    
    async def get_email_directory(self) -> List[dict]:
        """Get email directory for all departments"""
        try:
            directory = []
            for category, info in self.department_directory.items():
                directory.append({
                    "category": category,
                    "department_name": info["department_name"],
                    "primary_email": info["primary_email"],
                    "secondary_email": info.get("secondary_email"),
                    "issue_categories": info["issue_categories"],
                    "priority": info["priority"]
                })
            return directory
            
        except Exception as e:
            logger.error(f"Error getting email directory: {str(e)}")
            return []
    
    async def test_email_configuration(self):
        """Test SMTP email configuration"""
        try:
            test_result = await self.send_smtp_email(
                to_email=FROM_EMAIL,  # Send test email to self
                subject="HelperGPT SMTP Test",
                body="<p>This is a test email from HelperGPT support system.</p>",
                case_number="TEST"
            )
            
            return {
                "status": "success" if test_result["success"] else "error",
                "message": "SMTP configuration is working" if test_result["success"] else test_result.get("error"),
                "smtp_server": SMTP_SERVER,
                "smtp_port": SMTP_PORT,
                "from_email": FROM_EMAIL
            }
            
        except Exception as e:
            logger.error(f"Email configuration test failed: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "smtp_server": SMTP_SERVER,
                "smtp_port": SMTP_PORT
            }

# Create global instance
email_service = EmailService()
