# adstxt-agent

A small agent for the OneTag Supply team. Each morning it answers two questions: **which publisher domains have not authorised OneTag to sell their inventory, and how much bid volume does that put at risk?**

You give it a spreadsheet of domains and their bid requests. It checks each site's public `ads.txt` file for our line (`onetag.com, 65e2f0d9f4ee117`) and writes a short brief for the Supply account managers, with the biggest risks first.

This is a training project, built by a product manager to learn how agents are put together.

## What it does

The work runs as one workflow with four steps:

1. **Intake** (AI model). The model looks at the spreadsheet and works out which sheet and columns hold the domains, the bid requests and the publisher. Then it stages every row in a holding table. Rows that aren't real domains, such as blanks, Google Translate mirrors, duplicates or `unknown_domain`, are set aside with a reason. If the file is ambiguous, the model stops and asks instead of guessing.
2. **Gate** (plain code, no model). Nothing is saved unless the numbers add up. Rows read must equal rows accepted plus rows rejected, and the bid requests across all rows must equal the file's own total row. If either check fails, the workflow stops and says why. For example, a spreadsheet with ten rows deleted is caught here.
3. **Check** (AI model plus code). The model asks for the top N domains to be checked. Code fetches each site's `ads.txt` with `curl`, like a normal browser, 20 sites at a time. Code, not the model, then decides whether our line is there.
4. **Report** (AI model). The model writes the brief from what is in the database. It saves the brief to `results/brief-<date>.md`.

### What each result means

| Status | Meaning | Counts as |
|---|---|---|
| `authorised` | `onetag.com, 65e2f0d9f4ee117` is listed, as DIRECT or RESELLER | fine |
| `ob_only` | only `65e2f0d9f4ee117-OB` is listed, which is not our line | at risk |
| `other_onetag_id` | onetag.com is listed with a different account ID | at risk |
| `no_onetag_line` | the site has an ads.txt but no onetag.com line | at risk |
| `no_ads_txt` | the site has no ads.txt | at risk |
| `blocked` | the site refused us or showed a bot check | **check by hand, not missing** |
| `error` | the check failed (timeout, DNS, server error) | check by hand |
| `mirror` | a translate.goog copy of another site, which can't be checked | reported separately |

If a subdomain has no ads.txt, the check tries the main domain and records that it did.

### The brief

- A headline with the bid requests at risk, and how much of the authorised volume depends on Freestar's central file.
- The at-risk sites, largest first, each with its evidence: the exact line, the final URL and when it was checked.
- A list of sites to check by hand.
- Questions for Supply that the agent raises but doesn't decide.
- Coverage: how many domains have been checked so far.

## What it needs

- macOS or Linux with Python 3.12 and `curl`.
- An Anthropic API key.
- The model is fixed to `claude-sonnet-5`. The agent refuses to run with any other model.

## How to run it

One-time setup:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create a file called `.env` in this folder with these two lines, and put your key after the `=`:

```
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5
```

**From the web page:**

```bash
.venv/bin/streamlit run app.py
```

Drop a `.xlsx` file on the page. It runs intake and the gate and shows what was accepted and rejected. Then press **Check the top N domains** to run the check and the report. The page shows which step is running and displays the brief at the end.

**From the command line:**

```bash
.venv/bin/python graph.py "path/to/domains.xlsx" --top 50
```

This runs all four steps and prints each tool call, the brief, the tokens used and the estimated cost.

**Just the checking agent**, on domains already imported:

```bash
.venv/bin/python check_agent.py "check the top 50 domains and tell me what you found"
```

## Time and cost

Measured on the full Freestar list: 1,711 rows, 1,650 domains.

- **Intake, gate and checking every domain:** about 4 minutes. The ads.txt fetches are plain `curl` and cost nothing. Only the model calls cost money.
- **Writing the brief:** about 2 minutes and roughly $0.58. It is the most expensive step, because the model reads up to 200 rows for each status.
- **Whole run:** about 6–7 minutes and roughly $0.60–0.70.
- **Top 50 only:** about 2 minutes and roughly $0.15–0.20.

## What it never does

- **It never sends anything.** It doesn't email, message or contact publishers. The brief is only saved to `results/`.
- **The models never write to the database directly.** They can only use tools that validate first. Saving an import is plain code behind the gate, and the model can't call it. The reporting tools open the database read-only.
- **It never states a result that isn't a row in the database.** Numbers come from the database, not from the model's memory or estimates.
- **It never counts a blocked site as missing.**
- **It never prints, logs or commits the API key.** `.env` is git-ignored.
- **Nothing in `data/` or `results/` goes to GitHub.** The spreadsheets, the database and the briefs stay on your machine.

## Files

| File | What it is |
|---|---|
| `app.py` | The upload page (Streamlit) |
| `graph.py` | The four-step workflow (LangGraph) and its command-line version |
| `intake.py` | The intake agent |
| `check_agent.py` | The checking agent |
| `tools.py` | Every tool: reading the spreadsheet, staging, the gate, the ads.txt checks, reading results and saving the brief |
| `agent_runner.py` | Runs an agent, prints its tool calls, and counts tokens and cost |
| `prompts/intake.md`, `prompts/check.md` | The system prompts for the two models |
| `data/` | Uploaded spreadsheets and the SQLite database (`adstxt.db`). Local only. |
| `results/` | Briefs and audit files. Local only. |
