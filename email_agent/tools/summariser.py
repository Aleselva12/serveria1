import os
import sys

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

load_dotenv()
GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")

SUMMARISER_PROMPT = """
<>
You are an expert email assistant. Read the following email and provide a concise, clear, and actionable summary of its contents.
If the subject is empty, then continue to summarize without it.

Subject: {subject}
Content: {content}
</>
"""

from typing import Annotated
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool

@tool
def summarize_email(email_id: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Analyzes and summarizes the core message of an email. 
    Extracts key points and provides a concise, actionable summary.

    Args:
        email_id (str): The ID of the email to be summarized.
        state (dict): The injected graph state containing fetched emails.

    Returns:
        str: A concise summary of the email.
    """
    emails = state.get("emails", [])
    email = next((e for e in emails if e.get("id") == email_id), None)
    
    if not email:
        return f"No email found with ID: {email_id}. Make sure it is in the recent emails list."
        
    prompt_template = PromptTemplate(
        input_variables=["subject", "content"],
        template=SUMMARISER_PROMPT
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
    
    # We just want the raw text response for a summary, not structured output
    response = llm.invoke(formatted_prompt) 
    
    return response.content

if __name__ == "__main__":
    pass