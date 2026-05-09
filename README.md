# Hisho

Agentic workflow assistant for managing letters, emails, approvals, and Google Workspace automation for clubs/organizations.

---

# Project Structure

```text
hisho/
├── __init__.py
├── agent.py                   # Main orchestrator (state machine)
├── config.py                  # Model config, keys, limits
├── main.py                    # FastAPI app
├── api/
│   ├── routes/
│   │   ├── letters.py
│   │   ├── forms.py
│   │   └── reports.py
├── sub_agents/
│   ├── __init__.py
│   ├── drafting/
│   │   ├── content_writer.py
│   │   ├── letter_writer.py
│   │   ├── email_writer.py
│   │   └── form_generator.py
│   ├── workflow/
│   │   ├── approval_router.py
│   │   └── status_tracker.py
│   └── agent_schemas.py
├── tools/                     # these tools are globally shared by multiple agents
│   ├── __init__.py
│   ├── google_docs.py
│   ├── gmail.py
│   ├── drive.py
│   ├── sheets.py
│   ├── db.py
│   └── forms.py
├── datastore/
│   ├── __init__.py
│   └── vector_store.py
├── prompts/                   # Write system prompts for these agents in one place
│   ├── letter_prompts.py
│   ├── email_prompts.py
│   └── form_prompts.py
└── utils/
    ├── logger.py
    └── helpers.py
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
