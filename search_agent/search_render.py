from typing import Any
import sys

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from langchain_core.messages import AIMessage
except ImportError:
    print("Please install 'rich' library: pip install rich")
    sys.exit(1)

console = Console()

def extract_text(content: Any) -> str:
    """Safely extract text from the message content."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)
    return str(content)

def render_message(message: Any, node_name: str = ""):
    """Render only the AI text response cleanly."""
    
    # We only care about displaying what the AI Assistant says.
    # We ignore ToolMessage (raw tool outputs), HumanMessage (already printed in input()),
    # and SystemMessage.
    if isinstance(message, AIMessage):
        text = extract_text(message.content)
        
        # If the AI generated text (not just a silent tool call), print it out nicely
        if text.strip():
            console.print("\n🤖 [bold green]AI Assistant:[/bold green]")
            console.print(Markdown(text))
            console.print()
