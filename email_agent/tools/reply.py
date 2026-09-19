import os
import sys
from typing import Annotated
import json

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

class EmailDraft(BaseModel):
    receiver_id: str = Field(description="The email address of the receiver")
    subject: str = Field(description="The subject of the email")
    body: str = Field(description="The main content of the email")

load_dotenv()

REPLY_EMAIL_PROMPT = """<>
You are an expert email copywriter. You need to write a professional reply to the following email.

Original Email Sender: {sender}
Original Email Subject: {subject}
Original Email Content: {original_content}

Instructions/Content for the reply (if any):
{content}

If no instructions are provided above, generate an appropriate, polite, and professional response acknowledging the email.

Drafted Reply:
</>
"""

@tool
def reply_email(email_id: str, tool_call_id: Annotated[str, InjectedToolCallId], content: str = None, state: Annotated[dict, InjectedState] = None) -> Command:
    """
    Generates a professional reply to an existing email.
    
    Args:
        email_id (str): The ID of the email to reply to.
        content (str): Optional instructions or specific content to include in the reply. If not provided, pass an empty string.
        state (dict): The injected graph state containing fetched emails.
        
    Returns:
        str: The full text of the drafted reply email.
    """
    emails = state.get("emails", [])
    email = next((e for e in emails if e.get("id") == email_id), None)
    
    if not email:
        return f"Error: Email with ID {email_id} not found."
        
    prompt_template = PromptTemplate(
        input_variables=["sender", "subject", "original_content", "content"],
        template=REPLY_EMAIL_PROMPT
    )
    
    formatted_prompt = prompt_template.format(
        sender=email.get("from", "Unknown Sender"),
        subject=email.get("subject", "No Subject"),
        original_content=email.get("body", "No Content"),
        content=content if content else "No specific instructions provided. Please draft a polite, standard reply."
    )
    
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11435"),
        temperature=0.0
    )
    
    structured_llm = llm.with_structured_output(EmailDraft)
    response: EmailDraft = structured_llm.invoke(formatted_prompt)
    
    return Command(
        update={
            "email_draft": {
                "receiver_id": response.receiver_id,
                "subject": response.subject,
                "body": response.body
            },
            "messages": [
                ToolMessage(content="Reply drafted successfully and saved to state.", tool_call_id=tool_call_id)
            ]
        }
    )
