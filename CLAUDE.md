# adstxt-agent

This is a training project for a product manager building an agent for the Supply team.

## Rules

- **Never print, log or commit the API key.** It lives only in `.env`, which is git-ignored.
- **The agent always uses the model in `ANTHROPIC_MODEL`, which is `claude-sonnet-5`. Never change it.**
- **The models in this agent never write to the database directly** — only through tools that validate first.
- **Nothing in `data/` or `results/` ever goes to GitHub.**
- **Explain what you did in plain English after every step.**
