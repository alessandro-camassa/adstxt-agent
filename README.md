# adstxt-agent

A small agent for the OneTag Supply team. Each morning it answers two questions: **which publisher domains have not authorised OneTag to sell their inventory, and how much bid volume does that put at risk?**

You give it a spreadsheet of domains and their bid requests. It checks each site's public `ads.txt` file for our line (`onetag.com, 65e2f0d9f4ee117`) and writes a short brief for the Supply account managers, with the biggest risks first.

This is a training project, built by a product manager to learn how agents are put together. **For the course results (the brief, the prompts, the rule I changed and the audit), see [Course results](#course-results-24-september-2026) at the bottom.**

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

**In a container** (Docker or OrbStack). The image holds only the code. The key comes from `.env` when the container starts, and `data/` and `results/` are shared with your machine:

```bash
docker build -t adstxt-agent .
docker run --rm --env-file .env \
  -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" \
  adstxt-agent "data/uploads/<spreadsheet>.xlsx" --top 20
```

The spreadsheet must be inside `data/`, so the container can see it.

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
- **The files in `data/` and `results/` never go to GitHub.** The spreadsheets, the database and the briefs stay on your machine. (The course section below includes one brief as a snapshot, by the author's choice.)

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

---

## Course results (24 September 2026)

What the agent produced on the real Freestar list (1,711 rows, 1,650 domains), and how it got there.

### How long it took and what it cost

| | By hand | With the agent |
|---|---|---|
| Checking every domain's ads.txt | about a week | about 4 minutes |
| Writing the brief | | about 2 minutes |
| **Total** | **about a week** | **about 6–7 minutes, roughly $0.60–0.70 a run** |

The full day, including three report runs while I fixed problems at full scale, cost about $1.62 in model calls. The ads.txt fetches themselves are free: they are plain `curl`.

### The brief it wrote

The morning brief for the full list, exactly as the agent saved it. Every number in it comes from the database, and I checked each figure against the database myself.

<details>
<summary>Show the full brief</summary>

#### ads.txt authorisation — 2026-09-24

##### Headline
467,731,431 of 7,341,207,759 checked bid requests (6.37%) are on sites that do not authorise OneTag. 553 sites at risk, 134 to check by hand.
Of the authorised bid requests, 2,270,137,938 (303 sites) are authorised independently and 4,345,938,290 (660 sites) through Freestar's central file.

##### Shared dependency
Freestar's central file (a.pub.network): 1 file, 660 sites, 4,345,938,290 bid requests (59.2% of checked). If this file changes, all of them change together.

##### At risk (largest first)
| Status | Sites | Bid requests |
|---|---|---|
| ob_only | 200 | 262,771,755 |
| other_onetag_id | 290 | 162,235,237 |
| no_ads_txt | 42 | 34,796,327 |
| no_onetag_line | 21 | 7,928,112 |

Top 25 at-risk sites by bid requests:

| Domain | Bid requests | Status | Evidence | Final URL | Checked |
|---|---|---|---|---|---|
| wenxuecity.com | 120,130,595 | other_onetag_id | onetag.com, 62d98ebd4882fb0, DIRECT | https://static.wenxuecity.com/ads.txt | 2026-09-24T14:18:45Z |
| beebom.com | 46,146,907 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://beebom.com/ads.txt | 2026-09-24T13:58:38Z |
| textnow.com | 34,778,718 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://static.textnow.com/ads.txt | 2026-09-24T13:58:39Z |
| fortune.com | 31,697,683 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://fortune.com/ads.txt | 2026-09-24T13:58:38Z |
| merriam-webster.com | 28,146,347 | other_onetag_id | onetag.com, 7d614f4ac7b0a56, DIRECT | https://www.merriam-webster.com:443/ads.txt | 2026-09-24T13:58:39Z |
| jcpenney.com | 27,510,396 | no_ads_txt | no ads.txt (served an HTML page instead of ads.txt) | https://jcpenney.com/ads.txt | 2026-09-24T13:58:39Z |
| publicrecords.netronline.com | 23,381,382 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://publicrecords.netronline.com/ads.txt | 2026-09-24T13:58:40Z |
| whatfontis.com | 11,971,851 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://whatfontis.com/ads.txt | 2026-09-24T13:58:42Z |
| buffalonews.com | 8,227,407 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://stltoday.com/ads.txt | 2026-09-24T13:58:44Z |
| celebdirtylaundry.com | 7,392,920 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://celebdirtylaundry.com/ads.txt | 2026-09-24T13:58:44Z |
| stltoday.com | 5,151,769 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://stltoday.com/ads.txt | 2026-09-24T13:58:47Z |
| madison.com | 4,543,300 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://stltoday.com/ads.txt | 2026-09-24T13:58:49Z |
| gaiaonline.com | 4,369,734 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://gaiaonline.com/ads.txt | 2026-09-24T13:58:48Z |
| omaha.com | 4,076,078 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://stltoday.com/ads.txt | 2026-09-24T13:58:50Z |
| htmlmahjonggames.com | 3,761,616 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://htmlmahjonggames.com/ads.txt | 2026-09-24T13:58:50Z |
| textfree.us | 3,637,228 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://textfree.com/ads.txt | 2026-09-24T13:58:51Z |
| wallsflow.com | 3,573,456 | no_onetag_line | no onetag line | https://wallsflow.com/ads.txt | 2026-09-24T13:58:50Z |
| 1001tracklists.com | 3,298,773 | other_onetag_id | onetag.com, 5f8e06c2cbd2faa, DIRECT | https://www.1001tracklists.com/ads.txt | 2026-09-24T13:58:51Z |
| pinchme.com | 3,122,597 | no_ads_txt | no ads.txt (served an HTML page instead of ads.txt) | https://pinchme.com/ads.txt | 2026-09-24T13:58:51Z |
| thejc.com | 3,025,808 | no_onetag_line | no onetag line | https://www.thejc.com/ads.txt | 2026-09-24T13:58:51Z |
| tucson.com | 2,982,982 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://stltoday.com/ads.txt | 2026-09-24T13:58:52Z |
| wpsdlocal6.com | 2,808,727 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://wpsdlocal6.com/ads.txt | 2026-09-24T13:58:52Z |
| hadviser.com | 2,610,055 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://hadviser.com/ads.txt | 2026-09-24T13:58:52Z |
| journalstar.com | 2,599,581 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://stltoday.com/ads.txt | 2026-09-24T13:58:53Z |
| nwitimes.com | 2,420,483 | ob_only | onetag.com, 65e2f0d9f4ee117-OB, DIRECT | https://stltoday.com/ads.txt | 2026-09-24T13:58:53Z |

...and 528 more at-risk sites (76,365,038 bid requests) in the database.

##### Check by hand
Blocked and error sites. Not counted as missing. The 15 largest:

| Domain | Bid requests | Why | URL to open |
|---|---|---|---|
| tapology.com | 74,379,749 | blocked, HTTP 403 | https://tapology.com/ads.txt |
| the-express.com | 45,211,617 | blocked, bot check page | https://www.the-express.com/ads.txt |
| deckshop.pro | 27,147,337 | blocked, HTTP 403 | https://deckshop.pro/ads.txt |
| songkick.com | 24,381,532 | error, HTTP 406 | https://songkick.com/ads.txt |
| aviewfrommyseat.com | 20,530,520 | blocked, HTTP 403 | https://aviewfrommyseat.com/ads.txt |
| powerball.com | 8,282,145 | error, SSL certificate mismatch | https://www.powerball.com/ads.txt |
| babypips.com | 6,008,829 | blocked, HTTP 403 | https://babypips.com/ads.txt |
| latribuna.hn | 5,932,253 | blocked, HTTP 403 | https://latribuna.hn/ads.txt |
| koimoi.com | 5,879,104 | blocked, HTTP 403 | https://koimoi.com/ads.txt |
| sun-sentinel.com | 5,825,598 | blocked, HTTP 403 | https://sun-sentinel.com/ads.txt |
| stampworld.com | 5,312,099 | blocked, HTTP 403 | https://stampworld.com/ads.txt |
| orlandosentinel.com | 4,401,501 | blocked, HTTP 403 | https://orlandosentinel.com/ads.txt |
| bigbrothernetwork.com | 3,101,125 | blocked, HTTP 403 | https://bigbrothernetwork.com/ads.txt |
| aviewfrommyseat.co.uk | 2,754,081 | blocked, HTTP 403 | https://aviewfrommyseat.co.uk/ads.txt |
| 365chess.com | 1,760,760 | blocked, HTTP 403 | https://365chess.com/ads.txt |

...and 119 more (16,491,850 bid requests) in the manual_check and results tables.

##### Mirrors
None found in this check.

##### Questions for Supply
- **DIRECT vs RESELLER.** Among authorised sites: RESELLER 929 sites / 6,333,666,732 bid requests; DIRECT 34 sites / 282,409,496 bid requests. Does the relationship matter for how we treat these?
- **Other OneTag IDs.** The most common other account IDs found on checked sites (domains, bid requests): 774083553572acc (82, 2,388,156); 81bee8aadfb0dbb-ob (69, 16,776); 75601b04186d260 (25, 1,556,078); 69f48c2160c8113 (17, 1,250,661); 9677fda2f71f0c0 (14, 6,484); 5d0d72448d8bfb0 (12, 5,163); 7d614f4ac7b0a56 (10, 29,171,059); 7e6a5ca60220d5a (9, 108); 95c9026ad15398d (6, 590); 5847a7d7e75dee8 (3, 2,189). Are any of these OneTag accounts we recognise?

##### Coverage
Checked 1650 of 1650 imported domains (7,341,207,759 of 7,341,207,759 bid requests). 0 domains still unchecked.

</details>

### My system prompts

Claude interviewed me as Supply's product manager, three to five questions at a time, then wrote the two prompts from my answers:

- [`prompts/intake.md`](prompts/intake.md): for the model that reads and stages the spreadsheet.
- [`prompts/check.md`](prompts/check.md): for the model that checks the domains and writes the brief.

The decisions from the interview:
- The brief is for Supply account managers, who contact publishers to get our line added.
- Only `onetag.com, 65e2f0d9f4ee117` counts, as DIRECT or RESELLER. `-OB` is not a match.
- Evidence is the exact line, the final URL and the check time.
- Bid volume at risk comes first.
- Blocked is not missing: blocked sites go on a separate "check by hand" list.
- Two questions for Supply, not answers: the central Freestar file, and DIRECT vs RESELLER.
- Only facts from the database, and never send anything.
- The intake model stops and asks if a file is ambiguous.

### The rule I changed

**Before:** the central Freestar file was a question for Supply.

> **Central Freestar file.** Count how many authorised sites have a `final_url` on `a.pub.network`, and the bid requests behind them. Ask: are these that many separate authorisations, or one dependency on Freestar's file?

**After:** it is reported as one dependency.

> Authorised sites whose `final_url` is on `a.pub.network` pass because of one file that Freestar hosts, not because each publisher lists us. Treat them as **one dependency**, not as separate authorisations.

Same code, same data, different brief. The question disappeared from "Questions for Supply". A new "Shared dependency" section appeared, and the headline now splits authorised volume into "authorised independently" and "through Freestar's central file". On the full list that is 660 sites and 59% of checked bid requests hanging on one file.

### What the second model disagreed with

A separate Claude Code session audited the top-50 run independently. It took a stratified sample of 25 rows, wrote its own script, and re-fetched each ads.txt with `curl`.

**Agreement: 24 of 25 rows (96%).**

| Recorded status | Agree | Sampled |
|---|---|---|
| authorised | 20 | 20 |
| ob_only | 2 | 2 |
| other_onetag_id | 1 | 1 |
| blocked | 1 | 2 |

**The one disagreement: the-express.com.** We recorded it as *blocked*, because the site served an Amazon WAF bot-check page. The auditor got the real file, which lists `onetag.com, 65e2f0d9f4ee117, RESELLER`, so it is authorised. When I re-checked, our tool was blocked three times out of three, with five different request variants. The site's bot defence fires only some of the time.

This is the "blocked is not missing" rule working: the site was never counted as at risk, only sent to be checked by hand. The auditor also noticed that every row shared one check time, the batch save time, so I changed the code to record each site's own check time.

### Trying to break the gate

I deleted ten rows from a copy of the spreadsheet and dropped it on the page. The intake model staged it without noticing anything, because it looked like a normal file. The gate stopped the workflow before anything was saved:

> Bid requests don't add up: accepted + rejected rows sum to 7,333,935,202 but the file's total row says 7,358,081,492 (difference -24,146,290).

The difference is exactly the ten deleted rows. Nothing reached the domains table, and no domains were checked.

### What broke at full scale, and the fixes

1. **The first brief was never saved.** With 553 at-risk sites, the model tried to list them all and ran out of room in a single reply. The report step noticed that no brief was saved and stopped with a clear message. Fix: the brief now lists the 25 largest at-risk sites and the 15 largest check-by-hand sites, and says how many more there are.
2. **The second brief had estimates in it**, such as "~60 sites" where the database has 82. `query_results` returns at most 200 rows, and the model was counting only those. Fix: every aggregate count (the Freestar dependency, the DIRECT/RESELLER split, other OneTag IDs) is now computed in code inside `summarise`. The prompt forbids "~" and currency signs on bid requests.
3. **The main-domain fallback was wrong for some country domains:** `typing.keybr.com.cn` fell back to `com.cn`. Fix: more country suffixes.
