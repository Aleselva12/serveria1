import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from typing import Annotated
import json

class EmailDraft(BaseModel):
    receiver_id: str = Field(description="The email address of the receiver")
    subject: str = Field(description="The subject of the email")
    body: str = Field(description="The main content of the email")

load_dotenv()
GROQ_API_KEY3 = os.getenv("GROQ_API_KEY3")

CREATE_EMAIL_PROMPT = """<>
You are an expert email copywriter. Given the brief provided below, generate a professional, clear, and engaging email.

Brief: {brief}

Email Content:
</>
"""

@tool
def create_email(brief: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """
    Generates a complete, professional email draft based on a short description or brief.
    Use this tool when you need to write a brand new email or reply to an existing one.

    Args:
        brief (str): Instructions or a short description of what the email should say.

    Returns:
        str: The full text of the drafted professional email.
    """
    prompt_template = PromptTemplate(
        input_variables=["brief"],
        template=CREATE_EMAIL_PROMPT
    )
    
    formatted_prompt = prompt_template.format(brief=brief)
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=GROQ_API_KEY3,
        temperature=0.7
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
                ToolMessage(content="Email drafted successfully and saved to state.", tool_call_id=tool_call_id)
            ]
        }
    )

if __name__ == "__main__":
    pass
