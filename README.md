# Hisho

Agentic workflow assistant for managing letters, emails, approvals, and Google Workspace automation for clubs/organizations.

# Setup
Make sure the below tools installed:
```
python
postgres
uv
ollama
```

## 1. Clone repository

```bash
git clone https://github.com/sceptix-club/Hisho.git
cd Hisho
```


## 2. Create environment file

```bash
cp .env.example .env
```

Update `.env`:
```env
LETTER_MODEL="ollama_chat/qwen3:4b"
OLLAMA_BASE_URL="http://localhost:11434"
DATABASE_URL="postgresql://user:password@localhost:5432/hisho"
```


## 3. Install dependencies

```bash
uv sync
```



# Apply Database Migrations

```bash
uv run alembic upgrade head
```


# Run Agents

## Web UI

```bash
uv run adk web
```


## Console

```bash
uv run adk run hisho_agents/
```


# Run FastAPI Server

```bash
uv run python main.py
```

# Project Structure

```text
Hisho/
├── README.md
├── alembic.ini
├── api                             # FastAPI endpoints
│   └── routes
│       └── letters.py
├── config.py                       # Environment Config
├── db                              # postgres database
│   ├── migrations
│   ├── models.py
│   └── session.py
├── hisho_agents
│   ├── agent.py                    # Root agent
│   ├── prompts
│   │   ├── content_writer.py
│   │   └── letter_agent.py
│   ├── sub_agents                  # Sub agents for letter, report etc
│   │   ├── agent_schemas.py
│   │   ├── drafting
│   │   │   ├── content_writer.py
│   │   │   └── email_writer.py
│   │   └── workflow
│   │       └── approval_router.py
│   └── tools                       # Tools for agents
│       ├── db.py
│       ├── docs.py
│       ├── drive.py
│       ├── letter_tools.py
│       └── validation_checkers.py
├── main.py                         # FastAPI server
├── pyproject.toml
├── utils
└── uv.lock
```

# Plan

**Requirements**
- Google Docs, Drive, Gmail, Sheets, Forms integration
- Autonomously
	- Write letter drafts for any requirements
	- Write emails to concerned people
	- Create draft google forms for a given event

**With inputs**
- Human in the loop for mailing and printing tasks
- Should be able to edit letters on the fly by taking suggestions
- Analytics on letters, organizing them by project/event/time
- Be able to track status on letter approvals

**Datastore**
- Should be aware about the standard chain of command for past know letter types
- Should be aware of college associates and their titles + profile
- Strict formatting rules on letters
- Club assets access

**Interface**
- Must be able to run locally on Club PC
- Good to have it instantly switch to Gemini/OpenAI api keys if needed (future use cases)
- Agent backend is essentially a REST API, so that we can plug it into any frontend we require, like website, whatsapp, telegram etc.
- Maybe route the traffic through the VPS? since its up 24/7. Can't guarantee uptime for the PC so, we use it when we need it. And its not like we write letters 24/7
