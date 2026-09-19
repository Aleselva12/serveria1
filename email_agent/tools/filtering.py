import os
import sys

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

load_dotenv()
GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")

class EmailClassification(BaseModel):
    category: str = Field(
        description="The category of the email. Must be EXACTLY ONE of: 'spam', 'urgent', 'informational', or 'needs_review'."
    )

FILTERING_PROMPT = """<>
Analyze the following email and classify its type.
Classify it as EXACTLY ONE of the following options: 'spam', 'urgent', 'informational', or 'needs_review'.
Do not include any other text in your response.

Subject: {subject}
Content: {content}
</>
"""

from typing import Annotated
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool

@tool
def filter_email(email_id: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Classifies an email's content into EXACTLY ONE of the following categories: 
    'spam', 'urgent', 'informational', or 'needs_review'.

    Args:
        email_id (str): The ID of the email to be classified.
        state (dict): The injected graph state containing fetched emails.

    Returns:
        str: The classification category.
    """
    emails = state.get("emails", [])
    email = next((e for e in emails if e.get("id") == email_id), None)
    
    if not email:
        return f"No email found with ID: {email_id}. Make sure it is in the recent emails list."
        
    prompt_template = PromptTemplate(
        input_variables=["subject", "content"],
        template=FILTERING_PROMPT
    )
    
    formatted_prompt = prompt_template.format(
        subject=email.get("subject", ""),
        content=email.get("body", "")
    )
    
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=GROQ_API_KEY2,
        temperature=0.0
    )
    
    structured_llm = llm.with_structured_output(EmailClassification)
    response = structured_llm.invoke(formatted_prompt)
    
    return response.category

if __name__ == "__main__":
    pass
