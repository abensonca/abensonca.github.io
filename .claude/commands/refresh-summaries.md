---
description: Write plain-English summaries for publication cards that are missing one
allowed-tools: Bash(python3 scripts/summaries.py:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git status:*), Bash(git pull:*), Read, Write
---

Fill in the missing summaries on the Publications page.

1. Run `python3 scripts/summaries.py pending`. It prints a YAML list of papers
   that are on the front page, have a cached abstract, and have no summary yet.
   If it reports that everything has a summary, say so and stop — do not
   rewrite existing summaries.

2. For each pending paper, write a summary from its abstract:
   - Two sentences maximum.
   - Plain English aimed at a scientifically literate non-specialist. Expand or
     avoid jargon ("subhalo", "free-streaming length") where a plain phrase works.
   - Lead with what was found, not what was done.
   - No hype, no first person, no quotation marks, no "This paper...".
   - Match the voice of the summaries already in `_data/papers_cache.yml`.

3. Write them to a scratch file as a YAML mapping of bibcode to summary, then
   apply it:

   ```
   python3 scripts/summaries.py apply /tmp/summaries.yml
   ```

   `apply` updates both `_data/papers_cache.yml` and `_data/papers.yml`. It
   rejects summaries over 600 characters — if one is rejected, shorten it and
   re-apply rather than raising the limit.

4. Commit and push:

   ```
   git add _data/papers.yml _data/papers_cache.yml
   git commit -m "chore: add summaries for N papers"
   git push
   ```

   Only commit those two files. If the working tree has other uncommitted
   changes, leave them alone and mention them.

Report which papers you summarized. If nothing was pending, just say so.
