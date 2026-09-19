# JARVIS AI Assistant 🤖

JARVIS is an advanced **Multi-Agent AI System** built using [LangGraph](https://python.langchain.com/docs/langgraph) and powered by Google's **Gemini 2.5 Flash** models. 

Unlike traditional, monolithic chatbots, JARVIS uses a hierarchical **Supervisor Architecture**. A central "Supervisor" agent interprets your requests, breaks down complex tasks, and delegates work to highly specialized sub-agents. These sub-agents can even be chained together to complete multi-step workflows autonomously!

## 🏗️ Architecture

The system operates as a hierarchical graph network:
- **Supervisor Agent** (`/chat.py` & `/graph.py`): The brain of the operation. It communicates directly with the user, maintains conversation history, and routes specific sub-tasks to specialized agents.
- **Tools/Delegation** (`/tools.py`): The sub-agents are exposed to the Supervisor as fully self-contained tool nodes.

### 🧩 The Specialized Sub-Agents

1. **Email Agent** (`/email_agent`)
   - Capable of reading, summarizing, filtering, replying to, and drafting new emails.
   - Requires your approval before actually sending or saving drafts, implementing a "Human in the Loop" safety check.
2. **Calendar Agent** (`/calendar_agent`)
   - Manages your Google Calendar. It can read upcoming events, schedule new meetings, and delete or postpone existing ones.
3. **Search Agent** (`/search_agent`)
   - Uses the Tavily API to browse the live internet. If you ask about current events or facts outside the LLM's training data, this agent fetches the answers.

## 🚀 Installation & Setup

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd JARVIS
```

### 2. Set up a Python Virtual Environment
Isolate your dependencies to ensure everything runs smoothly:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
You must set up your API keys locally.
1. Create a `.env` file in the root of the `JARVIS` directory.
2. Add your keys:
   ```env
   GEMINI_API_KEY="your-gemini-api-key"
   TAVILY_API_KEY="your-tavily-api-key"
   ```

### 5. Setup Google OAuth Credentials
For the Email and Calendar agents to interface with your actual accounts:
1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable both the **Gmail API** and **Google Calendar API**.
3. Generate **OAuth 2.0 Client IDs** (Desktop App) and download the resulting `credentials.json` file.
4. Place `credentials.json` in the root directory. On your first run, a browser window will open asking you to authenticate, and a `token.json` file will be generated automatically.

## 💻 Usage

Start your personal assistant by running the central chat script from the root of the project:

```bash
python3 chat.py
```

Try asking complex, multi-step questions like:
- *"Check my calendar for tomorrow and see if I have time to meet Batman. If so, book a meeting and email him to let him know!"*
- *"Summarize the latest emails in my inbox, and then search the web for the latest news on OpenAI."*

## 🛠️ Code Structure & Imports

The codebase uses **Absolute Importing** from the root folder to prevent module name collisions between the different agents. For example, if you are modifying a tool inside the email agent, always import it via:
`from email_agent.tools.filtering import filter_email`

This ensures that the multi-agent graph compiles cleanly without namespace overlaps.
