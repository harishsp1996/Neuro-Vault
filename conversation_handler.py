"""
Conversation Handler Module for HelperGPT Support Case Extension
Manages interactive conversations and follow-up questions for support cases
"""
import os
import json
import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from openai import AsyncAzureOpenAI
from database import get_db_connection

logger = logging.getLogger(__name__)

# Azure OpenAI configuration
azure_openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

GPT_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

class ConversationHandler:
    def __init__(self):
        self.conversation_states = {}  # In-memory conversation states
        self.session_timeout = timedelta(hours=2)  # 2 hour timeout

        # Conversation flow states
        self.conversation_flow = {
            "initial": {
                "next_states": ["gathering_details", "providing_solution"],
                "questions": [
                    "Can you provide more details about when this issue occurs?",
                    "What error message (if any) do you see?",
                    "Has this worked before, or is this a new setup?"
                ]
            },
            "gathering_details": {
                "next_states": ["clarifying_symptoms", "providing_solution", "escalating"],
                "questions": [
                    "What specific symptoms are you experiencing?",
                    "When did you first notice this problem?",
                    "Are other users experiencing the same issue?"
                ]
            },
            "clarifying_symptoms": {
                "next_states": ["providing_solution", "escalating", "complete"],
                "questions": [
                    "Can you try the troubleshooting step and let me know what happens?",
                    "Do you see any specific error codes or messages?",
                    "Is there anything else that might be related to this issue?"
                ]
            }
        }

    async def initialize_conversation_tables(self):
        """Initialize conversation-related database tables"""
        try:
            conn = await get_db_connection()

            # Conversation sessions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    user_name TEXT,
                    user_email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    case_number TEXT,
                    issue_category TEXT,
                    conversation_state TEXT DEFAULT 'initial'
                )
            """)

            # Conversation messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions (session_id)
                )
            """)

            await conn.commit()
            await conn.close()
            logger.info("Conversation tables initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing conversation tables: {str(e)}")
            raise

    async def start_conversation(self, initial_message: str, user_info: Dict = None) -> Dict[str, Any]:
        """Start a new conversation session"""
        try:
            session_id = str(uuid.uuid4())

            # Create session in database
            conn = await get_db_connection()
            await conn.execute("""
                INSERT INTO conversation_sessions 
                (session_id, user_name, user_email, conversation_state)
                VALUES (?, ?, ?, 'initial')
            """, (
                session_id,
                user_info.get("user_name") if user_info else None,
                user_info.get("user_email") if user_info else None
            ))

            # Store initial message
            await conn.execute("""
                INSERT INTO conversation_messages 
                (session_id, message_type, content)
                VALUES (?, 'user', ?)
            """, (session_id, initial_message))

            await conn.commit()
            await conn.close()

            # Initialize in-memory state
            self.conversation_states[session_id] = {
                "state": "initial",
                "messages": [{"type": "user", "content": initial_message, "timestamp": datetime.now()}],
                "extracted_info": {},
                "created_at": datetime.now(),
                "user_info": user_info or {}
            }

            # Generate initial response
            response = await self.generate_contextual_response(session_id, initial_message)

            logger.info(f"Started conversation session: {session_id}")
            return {
                "session_id": session_id,
                "message": response["message"],
                "follow_up_questions": response.get("questions", []),
                "next_action": response.get("next_action", "continue"),
                "case_ready": response.get("case_ready", False)
            }

        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}")
            raise

    async def handle_support_conversation(self, user_message: str, session_id: str) -> Dict[str, Any]:
        """Handle ongoing support conversation with follow-up questions"""
        try:
            # Load conversation state
            await self.load_conversation_state(session_id)

            if session_id not in self.conversation_states:
                # Session not found, start new one
                return await self.start_conversation(user_message)

            # Update conversation state
            conversation = self.conversation_states[session_id]
            conversation["messages"].append({
                "type": "user",
                "content": user_message,
                "timestamp": datetime.now()
            })

            # Store message in database
            await self.store_message(session_id, "user", user_message)

            # Generate contextual response
            response = await self.generate_contextual_response(session_id, user_message)

            # Store bot response
            await self.store_message(session_id, "bot", response["message"], response.get("metadata"))

            # Update conversation state in database
            await self.update_conversation_state(session_id, response.get("new_state", conversation["state"]))

            logger.info(f"Handled conversation for session: {session_id}")
            return {
                "message": response["message"],
                "follow_up_questions": response.get("questions", []),
                "next_action": response.get("next_action", "continue"),
                "case_ready": response.get("case_ready", False),
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"Error handling conversation: {str(e)}")
            return {
                "message": "I apologize, but I encountered an error. Please try again or contact support.",
                "follow_up_questions": [],
                "next_action": "error",
                "case_ready": False,
                "session_id": session_id
            }

    async def generate_contextual_response(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """Generate AI response based on conversation context"""
        try:
            conversation = self.conversation_states[session_id]
            current_state = conversation["state"]

            # Build conversation history
            messages_history = "\n".join([
                f"{msg['type'].title()}: {msg['content']}"
                for msg in conversation["messages"][-10:]  # Last 10 messages for context
            ])

            system_prompt = f"""
            You are an IT support specialist having an interactive conversation with a user.
            Your goal is to gather enough information to either:
            1. Provide helpful troubleshooting steps
            2. Determine if the issue needs to be escalated to a department

            Current conversation state: {current_state}

            Guidelines:
            - Ask specific, targeted questions to narrow down the problem
            - Provide safe troubleshooting steps when appropriate
            - Be empathetic and professional
            - If you have enough information, indicate that a support case can be created
            - Limit to 2-3 follow-up questions at a time

            Respond with JSON format:
            {{
                "message": "Your response to the user",
                "questions": ["Question 1", "Question 2"],
                "next_action": "continue|create_case|escalate",
                "case_ready": true/false,
                "new_state": "current_state",
                "extracted_info": {{"key": "value"}},
                "troubleshooting_steps": ["step1", "step2"] (optional)
            }}
            """

            user_prompt = f"""
            Conversation History:
            {messages_history}

            Latest User Message: {user_message}

            Generate an appropriate response to continue this support conversation.
            """

            response = await azure_openai_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=600,
                temperature=0.4
            )

            ai_response = response.choices[0].message.content.strip()

            try:
                parsed_response = json.loads(ai_response)

                # Update conversation state with extracted info
                if "extracted_info" in parsed_response:
                    conversation["extracted_info"].update(parsed_response["extracted_info"])

                # Update state
                if "new_state" in parsed_response and parsed_response["new_state"] != current_state:
                    conversation["state"] = parsed_response["new_state"]

                return parsed_response

            except json.JSONDecodeError:
                logger.warning("Could not parse AI response as JSON, providing fallback")
                return {
                    "message": ai_response,
                    "questions": self.get_fallback_questions(current_state),
                    "next_action": "continue",
                    "case_ready": False,
                    "new_state": current_state
                }

        except Exception as e:
            logger.error(f"Error generating contextual response: {str(e)}")
            return {
                "message": "Thank you for the information. Let me help you with this issue.",
                "questions": ["Can you provide more details about the problem?"],
                "next_action": "continue",
                "case_ready": False,
                "new_state": current_state
            }

    def get_fallback_questions(self, current_state: str) -> List[str]:
        """Get fallback questions based on current state"""
        return self.conversation_flow.get(current_state, {}).get("questions", [
            "Can you provide more details about the issue?",
            "When did this problem first occur?"
        ])

    async def extract_issue_details(self, session_id: str) -> Dict[str, Any]:
        """Extract structured issue details from conversation"""
        try:
            conversation = self.conversation_states.get(session_id)
            if not conversation:
                await self.load_conversation_state(session_id)
                conversation = self.conversation_states.get(session_id)

            if not conversation:
                return {}

            # Prepare conversation text for analysis
            conversation_text = "\n".join([
                f"{msg['type']}: {msg['content']}"
                for msg in conversation["messages"]
            ])

            system_prompt = """
            You are analyzing a support conversation to extract structured information.
            Extract the following details from the conversation:
            - Issue description (summarized)
            - Issue category (hardware/software/network/security/account_access)
            - Severity level (low/medium/high/critical)
            - User information (if provided)
            - Symptoms mentioned
            - Error messages (if any)
            - When the issue started
            - Steps already tried

            Return as JSON format with these keys.
            """

            user_prompt = f"Analyze this conversation and extract issue details:\n{conversation_text}"

            response = await azure_openai_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=400,
                temperature=0.2
            )

            ai_response = response.choices[0].message.content.strip()

            try:
                extracted_details = json.loads(ai_response)

                # Merge with already extracted info
                if "extracted_info" in conversation:
                    extracted_details.update(conversation["extracted_info"])

                return extracted_details

            except json.JSONDecodeError:
                return conversation.get("extracted_info", {})

        except Exception as e:
            logger.error(f"Error extracting issue details: {str(e)}")
            return {}

    async def determine_next_action(self, session_id: str) -> str:
        """Determine if more info is needed or ready to route"""
        try:
            conversation = self.conversation_states.get(session_id)
            if not conversation:
                return "continue"

            # Check if we have enough information
            extracted_info = conversation.get("extracted_info", {})
            message_count = len(conversation.get("messages", []))

            # Criteria for creating a case
            has_description = "issue_description" in extracted_info or any(
                len(msg.get("content", "")) > 20 
                for msg in conversation["messages"] 
                if msg["type"] == "user"
            )

            has_category = "issue_category" in extracted_info
            enough_messages = message_count >= 4  # At least 2 exchanges

            if has_description and (has_category or enough_messages):
                return "create_case"
            elif message_count > 10:  # Too many messages, escalate
                return "escalate"
            else:
                return "continue"

        except Exception as e:
            logger.error(f"Error determining next action: {str(e)}")
            return "continue"

    async def load_conversation_state(self, session_id: str):
        """Load conversation state from database"""
        try:
            if session_id in self.conversation_states:
                # Check if state is not too old
                state = self.conversation_states[session_id]
                if datetime.now() - state["created_at"] < self.session_timeout:
                    return

            conn = await get_db_connection()

            # Load session
            cursor = await conn.execute("""
                SELECT user_name, user_email, conversation_state, created_at
                FROM conversation_sessions 
                WHERE session_id = ? AND status = 'active'
            """, (session_id,))
            session_row = await cursor.fetchone()

            if not session_row:
                await conn.close()
                return

            # Load messages
            cursor = await conn.execute("""
                SELECT message_type, content, timestamp, metadata
                FROM conversation_messages 
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            message_rows = await cursor.fetchall()

            await conn.close()

            # Reconstruct state
            messages = []
            extracted_info = {}

            for row in message_rows:
                message = {
                    "type": row[0],
                    "content": row[1],
                    "timestamp": datetime.fromisoformat(row[2])
                }
                if row[3]:  # metadata
                    try:
                        metadata = json.loads(row[3])
                        message["metadata"] = metadata
                        if "extracted_info" in metadata:
                            extracted_info.update(metadata["extracted_info"])
                    except json.JSONDecodeError:
                        pass

                messages.append(message)

            self.conversation_states[session_id] = {
                "state": session_row[2],
                "messages": messages,
                "extracted_info": extracted_info,
                "created_at": datetime.fromisoformat(session_row[3]),
                "user_info": {
                    "user_name": session_row[0],
                    "user_email": session_row[1]
                }
            }

        except Exception as e:
            logger.error(f"Error loading conversation state: {str(e)}")

    async def store_message(self, session_id: str, message_type: str, content: str, metadata: Dict = None):
        """Store message in database"""
        try:
            conn = await get_db_connection()

            metadata_json = json.dumps(metadata) if metadata else None

            await conn.execute("""
                INSERT INTO conversation_messages 
                (session_id, message_type, content, metadata)
                VALUES (?, ?, ?, ?)
            """, (session_id, message_type, content, metadata_json))

            await conn.commit()
            await conn.close()

        except Exception as e:
            logger.error(f"Error storing message: {str(e)}")

    async def update_conversation_state(self, session_id: str, new_state: str):
        """Update conversation state in database"""
        try:
            conn = await get_db_connection()

            await conn.execute("""
                UPDATE conversation_sessions 
                SET conversation_state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (new_state, session_id))

            await conn.commit()
            await conn.close()

        except Exception as e:
            logger.error(f"Error updating conversation state: {str(e)}")

    async def complete_conversation(self, session_id: str, case_number: str = None):
        """Mark conversation as completed"""
        try:
            conn = await get_db_connection()

            await conn.execute("""
                UPDATE conversation_sessions 
                SET status = 'completed', case_number = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (case_number, session_id))

            await conn.commit()
            await conn.close()

            # Clean up memory state
            if session_id in self.conversation_states:
                del self.conversation_states[session_id]

            logger.info(f"Completed conversation session: {session_id}")

        except Exception as e:
            logger.error(f"Error completing conversation: {str(e)}")

    async def cleanup_old_conversations(self):
        """Clean up old conversation sessions"""
        try:
            cutoff_time = datetime.now() - timedelta(days=7)  # 7 days old

            conn = await get_db_connection()

            await conn.execute("""
                UPDATE conversation_sessions 
                SET status = 'archived'
                WHERE created_at < ? AND status = 'active'
            """, (cutoff_time.isoformat(),))

            await conn.commit()
            await conn.close()

            # Clean up memory states
            expired_sessions = [
                session_id for session_id, state in self.conversation_states.items()
                if datetime.now() - state["created_at"] > self.session_timeout
            ]

            for session_id in expired_sessions:
                del self.conversation_states[session_id]

            logger.info(f"Cleaned up {len(expired_sessions)} expired conversation sessions")

        except Exception as e:
            logger.error(f"Error cleaning up conversations: {str(e)}")

# Create global instance
conversation_handler = ConversationHandler()
