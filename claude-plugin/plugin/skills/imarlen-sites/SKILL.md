---
name: imarlen-sites
description: Use when the user asks about their iMARLEN websites (Planit/checker.imarlen.kz, iMARLEN ID, Ustaz, Testileu, EnGame, iEngl, Zoomera, Mario, Scheduling, Nexus) — reading pages, checking Planit assessments, results, analytics or the review queue.
---

# iMARLEN сайттары

The `imarlen` MCP server exposes tools named `<site>__<action>`:

- `<site>__fetch_page` — read any page of that site as text (`path` like `/` or `/pricing`). Use it to check what a page says, whether it is up, or to answer content questions.
- `planit__dashboard`, `planit__list_assessments`, `planit__get_assessment`, `planit__assessment_results`, `planit__assessment_analytics`, `planit__review_queue`, `planit__list_classes` — read-only Planit data, as the Planit bot account sees it.
- Tools marked destructive (for example `planit__approve_confident`) change data. Before calling one, say exactly what will change and wait for the user's go-ahead.

Guidelines:
- Reply in the user's language (usually Kazakh).
- Prefer the site's API tools over `fetch_page` when both can answer.
- Do not paste students' personal data into replies unless the user asks for that specific record.
- If a tool returns `HTTP 401`, the bot account in the server's `.env` is wrong or blocked; say so.
