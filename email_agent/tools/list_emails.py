from typing import Annotated
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool

@tool
def list_emails(state: Annotated[dict, InjectedState], max_results: int = 10) -> str:
    """
    Lists the recent emails fetched from the user's inbox.
    
    Args:
        state (dict): The injected graph state containing fetched emails.
        max_results (int): The maximum number of emails to list. Defaults to 10.
        
    Returns:
        str: A formatted string containing the details of recent emails (ID, Subject, Sender, Date).
    """
    emails = state.get("emails", [])
    if not emails:
        return "No recent emails found in the current state."
        
    # Limit the number of emails
    emails_to_list = emails[:max_results]
    
    formatted_emails = []
    for idx, email in enumerate(emails_to_list):
        email_id = email.get('id', 'N/A')
        subject = email.get('subject', 'No Subject')
        sender = email.get('from', 'Unknown Sender')
        date = email.get('date', 'Unknown Date')
        
        formatted_emails.append(f"{idx+1}. ID: {email_id}\n   From: {sender}\n   Date: {date}\n   Subject: {subject}\n")
        
    return "\n".join(formatted_emails)
