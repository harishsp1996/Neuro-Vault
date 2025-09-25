"""
Complete Support Case Management Module for HelperGPT
Enhanced with WFH, Cloud, and Interactive Support Features with SMTP Email Integration
"""
import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from openai import AsyncAzureOpenAI
from database import get_db_connection, log_user_query
from utils import generate_response

logger = logging.getLogger(__name__)

# Azure OpenAI configuration
azure_openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

GPT_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

class SupportCaseManager:
    def __init__(self):
        # Complete issue categories with WFH and Cloud support
        self.issue_categories = {
            "hardware": {
                "subcategories": [
                    "laptop_wont_start", "screen_issues", "keyboard_mouse_issues", 
                    "battery_charging", "overheating", "ports_connectivity"
                ],
                "department": "IT Hardware Support",
                "email": "hardware@company.com",
                "priority": "high"
            },
            "software": {
                "subcategories": [
                    "slow_performance", "application_crashes", "login_issues",
                    "system_updates", "file_corruption"
                ],
                "department": "IT Software Support", 
                "email": "software@company.com",
                "priority": "medium"
            },
            "cloud": {
                "subcategories": [
                    "aws_issues", "azure_problems", "cloud_access",
                    "storage_issues", "deployment_problems", "api_errors",
                    "ec2_problems", "s3_issues", "lambda_errors"
                ],
                "department": "Cloud Support Team",
                "email": "cloudsupport@company.com", 
                "priority": "high"
            },
            "wfh": {
                "subcategories": [
                    "leave_request", "remote_work_policy", "wfh_equipment",
                    "attendance_issues", "policy_questions", "sick_leave",
                    "vacation_request", "wfh_approval"
                ],
                "department": "HR Support",
                "email": "hrsupport@company.com",
                "priority": "medium"
            },
            "network": {
                "subcategories": [
                    "wifi_connection", "vpn_issues", "internet_slow",
                    "email_problems", "network_drive_access"
                ],
                "department": "Network Support",
                "email": "network@company.com", 
                "priority": "medium"
            },
            "security": {
                "subcategories": [
                    "malware_suspected", "password_reset", "account_locked",
                    "suspicious_activity", "data_breach_concern"
                ],
                "department": "Security Team",
                "email": "security@company.com",
                "priority": "critical"
            }
        }
        
        # Complete troubleshooting steps for all categories
        self.safe_troubleshooting_steps = {
            # Hardware troubleshooting
            "laptop_wont_start": [
                "Check if power adapter is properly connected to laptop and wall outlet",
                "Look for any LED lights on the power adapter or laptop",
                "Try a different power outlet",
                "If removable, carefully remove and reinsert the battery",
                "Hold the power button for 30 seconds while unplugged",
                "Contact IT Hardware Support if none of these steps work"
            ],
            "screen_issues": [
                "Check if the laptop is actually on (listen for fan noise, check LED indicators)",
                "Try adjusting screen brightness using function keys", 
                "Connect an external monitor to test if display works",
                "Close and reopen the laptop lid",
                "If external display works, the issue may be with the laptop screen",
                "Contact IT Hardware team for screen replacement if needed"
            ],
            
            # Cloud troubleshooting
            "aws_issues": [
                "Check your AWS console for any service status alerts",
                "Verify your IAM permissions for the specific service",
                "Check CloudWatch logs for error messages",
                "Ensure your billing account is in good standing",
                "Try accessing from a different browser or incognito mode",
                "Contact Cloud Support with specific error messages and logs"
            ],
            "azure_problems": [
                "Check Azure Service Health portal for known issues",
                "Verify your subscription status and quotas",
                "Review Activity Log for failed operations",
                "Clear browser cache and try again",
                "Try using Azure CLI or PowerShell as alternative",
                "Contact Cloud Support with subscription and error details"
            ],
            "cloud_access": [
                "Verify you're using the correct login credentials",
                "Check if your account has the required permissions",
                "Try accessing from a different network/location",
                "Clear browser cookies and cache",
                "Ensure MFA is configured correctly",
                "Contact Cloud Support for access review"
            ],
            "deployment_problems": [
                "Check deployment logs for specific error messages",
                "Verify all configuration files are correct",
                "Ensure all dependencies are properly installed",
                "Check resource quotas and limits",
                "Try deploying to a different region/environment",
                "Contact Cloud Support with deployment logs"
            ],
            
            # WFH/HR troubleshooting
            "leave_request": [
                "Check the company HR portal for leave request forms",
                "Ensure you have sufficient leave balance",
                "Submit request at least 2 weeks in advance for planned leave",
                "Include all required documentation (medical certificates, etc.)",
                "Follow up with your direct manager for approval",
                "Contact HR Support if the portal is not working"
            ],
            "remote_work_policy": [
                "Review the latest WFH policy document on the company intranet",
                "Check with your manager about team-specific requirements",
                "Ensure you have proper home office setup",
                "Verify your internet connectivity meets requirements",
                "Complete any required WFH training modules",
                "Contact HR Support for policy clarification"
            ],
            "wfh_equipment": [
                "Check if you're eligible for WFH equipment allowance",
                "Review the list of approved equipment vendors",
                "Submit equipment request through HR portal",
                "Ensure equipment meets company security standards",
                "Keep receipts for reimbursement",
                "Contact HR Support for equipment policy details"
            ],
            "sick_leave": [
                "Obtain medical certificate from registered practitioner",
                "Submit leave request as soon as possible",
                "Notify your direct manager immediately",
                "Check if you have sufficient sick leave balance",
                "Follow company medical leave procedures",
                "Contact HR Support for extended sick leave requirements"
            ],
            
            # Network troubleshooting
            "slow_performance": [
                "Close unnecessary programs and browser tabs",
                "Restart your computer to clear temporary files",
                "Check available disk space (should have at least 10% free)",
                "Run Windows Disk Cleanup tool",
                "Check Task Manager for high CPU/memory usage programs",
                "If problem persists, contact IT for further diagnosis"
            ],
            "wifi_connection": [
                "Check if WiFi is enabled on your device",
                "Try forgetting and reconnecting to the WiFi network", 
                "Restart your WiFi adapter from Network Settings",
                "Move closer to the WiFi router if possible",
                "Try connecting other devices to the same network",
                "Contact Network Support if issue continues"
            ]
        }
    
    async def categorize_issue(self, issue_description: str, user_context: Dict = None) -> Dict[str, Any]:
        """Enhanced AI categorization for all support categories"""
        try:
            system_prompt = '''You are an IT support specialist. Categorize the user's issue into one of these categories:

- hardware: Physical device problems (laptop won't start, screen issues, keyboard/mouse, battery, overheating)
- software: Application or OS issues (slow performance, crashes, login problems, updates)  
- cloud: Cloud services issues (AWS, Azure, deployments, permissions, storage, API errors)
- wfh: Work from home and HR issues (leave requests, remote work policy, WFH equipment, attendance)
- network: Connectivity issues (WiFi, VPN, internet, email, network drives)
- security: Security concerns (malware, passwords, suspicious activity, data breach)

Pay special attention to:
- Leave/vacation/sick requests → wfh category  
- AWS/Azure/Cloud deployments → cloud category
- Remote work questions → wfh category

Respond with JSON format:
{
    "category": "category_name",
    "subcategory": "specific_issue", 
    "confidence": 0.95,
    "priority": "low/medium/high/critical",
    "reasoning": "brief explanation"
}'''
            
            user_prompt = f"""User Issue: {issue_description}
User Context: {json.dumps(user_context) if user_context else None}

Categorize this issue, paying special attention to WFH/HR and Cloud-related requests."""
            
            response = await azure_openai_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            try:
                categorization = json.loads(ai_response)
            except json.JSONDecodeError:
                # Enhanced fallback categorization
                issue_lower = issue_description.lower()
                
                if any(word in issue_lower for word in ["leave", "vacation", "sick", "wfh", "remote", "hr", "policy"]):
                    category = "wfh"
                elif any(word in issue_lower for word in ["aws", "azure", "cloud", "deploy", "s3", "ec2", "lambda"]):
                    category = "cloud"
                elif any(word in issue_lower for word in ["laptop", "screen", "battery", "hardware"]):
                    category = "hardware"
                else:
                    category = "software"
                    
                categorization = {
                    "category": category,
                    "subcategory": "general_issue", 
                    "confidence": 0.6,
                    "priority": "medium",
                    "reasoning": "Fallback categorization based on keywords"
                }
            
            # Add department and email info
            if categorization["category"] in self.issue_categories:
                cat_info = self.issue_categories[categorization["category"]]
                categorization["department"] = cat_info["department"]
                categorization["email"] = cat_info["email"]
            
            logger.info(f"Categorized issue as: {categorization}")
            return categorization
            
        except Exception as e:
            logger.error(f"Error categorizing issue: {str(e)}")
            return {
                "category": "software",
                "subcategory": "general_issue",
                "confidence": 0.3, 
                "priority": "medium",
                "department": "IT Support",
                "email": "support@company.com",
                "reasoning": f"Error in categorization: {str(e)}"
            }
    
    async def generate_troubleshooting_steps(self, category: str, subcategory: str, issue_details: Dict) -> List[str]:
        """Generate safe troubleshooting steps based on issue category"""
        try:
            # Get predefined safe steps if available
            if subcategory in self.safe_troubleshooting_steps:
                base_steps = self.safe_troubleshooting_steps[subcategory]
            else:
                # Category-based fallback steps
                fallback_steps = {
                    "hardware": [
                        "Restart your device and check connections",
                        "Look for any physical damage or loose cables", 
                        "Try using the device in safe mode if possible",
                        "Contact IT Hardware Support with device model details"
                    ],
                    "cloud": [
                        "Check service status page for known issues",
                        "Verify your account permissions and quotas",
                        "Review logs for specific error messages",
                        "Try accessing from different browser/network",
                        "Contact Cloud Support with error logs and account details"
                    ],
                    "wfh": [
                        "Check the HR portal for relevant forms and policies",
                        "Review your eligibility and current balances",
                        "Gather all required documentation",
                        "Notify your manager as per company policy",
                        "Contact HR Support for guidance"
                    ],
                    "software": [
                        "Restart the application and try again",
                        "Check for any error messages and note them down", 
                        "Try the same action on a different device if possible",
                        "Contact IT Software Support with error details"
                    ]
                }
                base_steps = fallback_steps.get(category, [
                    "Document the exact issue and any error messages",
                    "Try restarting and attempting the action again", 
                    "Contact appropriate support team with details"
                ])
            
            # Use AI to customize steps based on specific issue details
            system_prompt = f'''You are a {category} support specialist. Provide SAFE troubleshooting steps for users.

IMPORTANT SAFETY RULES:
- Only suggest steps that are safe for non-technical users
- No registry editing, command line operations, or system file modifications
- No opening computer cases or hardware disassembly (for hardware issues)
- For cloud issues: focus on console checks, permission verification, and log review
- For WFH/HR issues: focus on policy review, form submission, and documentation
- Always recommend contacting appropriate support for complex issues
- Keep steps simple and clear'''
            
            user_prompt = f"""Issue Category: {category}
Issue Subcategory: {subcategory}
Issue Details: {json.dumps(issue_details)}
Base safe steps: {json.dumps(base_steps)}

Customize these troubleshooting steps for this specific {category} issue. Keep them SAFE and appropriate for end users. Return as a JSON array of strings."""
            
            response = await azure_openai_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=600,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            try:
                customized_steps = json.loads(ai_response)
                if isinstance(customized_steps, list):
                    return customized_steps
            except json.JSONDecodeError:
                logger.warning("Could not parse AI troubleshooting response, using base steps")
            
            return base_steps
            
        except Exception as e:
            logger.error(f"Error generating troubleshooting steps: {str(e)}")
            return [
                "Please document the specific issue and any error messages",
                "If safe to do so, try restarting and attempting the action again",
                f"Contact {self.issue_categories.get(category, {}).get('department', 'IT Support')} with detailed information about the issue"
            ]
    
    async def generate_follow_up_questions(self, issue_description: str, categorization: Dict) -> List[str]:
        """Generate contextual follow-up questions based on category"""
        try:
            category = categorization.get("category", "general")
            
            # Category-specific question prompts
            category_prompts = {
                "cloud": """Generate specific follow-up questions for cloud/infrastructure issues. Focus on:
- Which cloud service (AWS, Azure, GCP)?
- Specific error messages or codes
- When the issue started
- Impact on users/services
- Recent changes or deployments""",
                
                "wfh": """Generate specific follow-up questions for WFH/HR issues. Focus on:
- Type of leave or request
- Dates and duration needed
- Required documentation
- Manager approval status
- Urgency level""",
                
                "hardware": """Generate specific follow-up questions for hardware issues. Focus on:
- Device model and age
- Physical condition and environment
- When issue first occurred
- Any recent drops or spills
- Power and connectivity status""",
                
                "software": """Generate specific follow-up questions for software issues. Focus on:
- Which application or system
- Error messages displayed  
- When problem started
- Other users affected
- Recent updates or changes"""
            }
            
            system_prompt = category_prompts.get(category, '''Generate 2-3 specific follow-up questions to gather more details about the user's technical issue.

Questions should be:
- Specific and technical but understandable  
- Help narrow down the problem
- Gather context about when/how the issue occurs
- Ask about error messages, timing, or specific symptoms

Return as JSON array of strings.''')
            
            user_prompt = f"""Original Issue: {issue_description}
Category: {category}
Subcategory: {categorization.get("subcategory", "unknown")}

Generate helpful follow-up questions to diagnose this {category} issue better."""
            
            response = await azure_openai_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=400,
                temperature=0.4
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            try:
                questions = json.loads(ai_response)
                if isinstance(questions, list):
                    return questions[:4]  # Limit to 4 questions
            except json.JSONDecodeError:
                logger.warning("Could not parse follow-up questions response")
            
            # Category-specific fallback questions
            fallback_questions = {
                "cloud": [
                    "Which cloud service are you having issues with (AWS, Azure, etc.)?",
                    "What specific error message or code are you seeing?",
                    "When did this issue first occur?",
                    "Have there been any recent deployments or changes?"
                ],
                "wfh": [
                    "What type of leave or request are you making?",
                    "What dates do you need the leave for?",
                    "Do you have any required documentation ready?",
                    "Have you discussed this with your manager yet?"
                ],
                "hardware": [
                    "What is the make and model of your device?",
                    "When did you first notice this issue?",
                    "Are there any visible signs of damage?",
                    "Does the device show any LED lights or make sounds?"
                ],
                "software": [
                    "Which application or program is having the issue?",
                    "What error message (if any) do you see?",
                    "When did this problem start occurring?",
                    "Are other users experiencing the same issue?"
                ]
            }
            
            return fallback_questions.get(category, [
                "Can you provide more details about when this issue occurs?",
                "What error messages (if any) do you see?",
                "Has this worked before, or is this a new setup?",
                "How urgently do you need this resolved?"
            ])
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return [
                "Can you provide more details about the issue?",
                "When did you first notice this problem?",
                "What happens when you try to use the device/application?",
                "How urgently do you need this resolved?"
            ]
    
    async def create_support_case(self, user_input: Dict) -> Dict[str, Any]:
        """Create new support case with enhanced categorization"""
        try:
            # Generate unique case number
            case_number = f"SUP{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
            
            # Enhanced categorization
            categorization = await self.categorize_issue(
                user_input.get("issue_description", ""),
                user_input.get("context", {})
            )
            
            # Generate troubleshooting steps
            troubleshooting_steps = await self.generate_troubleshooting_steps(
                categorization["category"],
                categorization.get("subcategory", ""),
                user_input
            )
            
            # Generate follow-up questions
            follow_up_questions = await self.generate_follow_up_questions(
                user_input.get("issue_description", ""),
                categorization
            )
            
            # Store in database
            case_data = {
                "case_number": case_number,
                "user_name": user_input.get("user_name"),
                "user_email": user_input.get("user_email"),
                "issue_category": categorization["category"],
                "issue_description": user_input.get("issue_description", ""),
                "severity_level": categorization.get("priority", "medium"),
                "status": "open",
                "assigned_department": categorization.get("department"),
                "assigned_email": categorization.get("email"),
                "conversation_log": json.dumps([{
                    "timestamp": datetime.now().isoformat(),
                    "type": "issue_reported", 
                    "content": user_input.get("issue_description", ""),
                    "category": categorization["category"],
                    "confidence": categorization.get("confidence", 0.8)
                }]),
                "troubleshooting_steps": json.dumps(troubleshooting_steps)
            }
            
            case_id = await self.insert_support_case(case_data)
            
            result = {
                "case_id": case_id,
                "case_number": case_number,
                "issue_category": categorization["category"],
                "department": categorization.get("department"),
                "department_email": categorization.get("email"),
                "priority": categorization.get("priority"),
                "troubleshooting_steps": troubleshooting_steps,
                "follow_up_questions": follow_up_questions,
                "estimated_resolution": self.get_estimated_resolution_time(categorization["category"]),
                "confidence": categorization.get("confidence", 0.8)
            }
            
            logger.info(f"Created support case: {case_number} - Category: {categorization['category']}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating support case: {str(e)}")
            raise
    
    async def insert_support_case(self, case_data: Dict) -> int:
        """Insert support case into database"""
        try:
            conn = await get_db_connection()
            
            # Enhanced support_cases table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS support_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_number TEXT UNIQUE NOT NULL,
                    user_name TEXT,
                    user_email TEXT,
                    issue_category TEXT NOT NULL,
                    issue_description TEXT NOT NULL,
                    severity_level TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'open',
                    assigned_department TEXT,
                    assigned_email TEXT,
                    conversation_log TEXT,
                    troubleshooting_steps TEXT,
                    resolution_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    escalated BOOLEAN DEFAULT FALSE,
                    email_sent BOOLEAN DEFAULT FALSE,
                    satisfaction_rating INTEGER,
                    tags TEXT
                )
            """)
            
            cursor = await conn.execute("""
                INSERT INTO support_cases (
                    case_number, user_name, user_email, issue_category,
                    issue_description, severity_level, status, assigned_department,
                    assigned_email, conversation_log, troubleshooting_steps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case_data["case_number"],
                case_data.get("user_name"),
                case_data.get("user_email"),
                case_data["issue_category"],
                case_data["issue_description"],
                case_data.get("severity_level", "medium"),
                case_data.get("status", "open"),
                case_data.get("assigned_department"),
                case_data.get("assigned_email"),
                case_data.get("conversation_log"),
                case_data.get("troubleshooting_steps")
            ))
            
            case_id = cursor.lastrowid
            await conn.commit()
            await conn.close()
            
            logger.info(f"Support case inserted with ID: {case_id}")
            return case_id
            
        except Exception as e:
            logger.error(f"Error inserting support case: {str(e)}")
            raise
    
    def get_estimated_resolution_time(self, category: str) -> str:
        """Get estimated resolution time based on category"""
        estimates = {
            "hardware": "2-4 business days",
            "software": "1-2 business days", 
            "cloud": "4-8 business hours",
            "wfh": "1-3 business days",
            "network": "4-8 business hours",
            "security": "Immediate attention - within 2 hours"
        }
        return estimates.get(category, "1-2 business days")

# Create global instance
support_manager = SupportCaseManager()
