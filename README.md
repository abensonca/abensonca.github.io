# abensonca.github.io

Source for [abensonca.github.io](https://abensonca.github.io) — Andrew Benson's
research site. Built with Jekyll on GitHub Pages.

## Layout

```
.
├── _config.yml             Site config + author metadata
├── _data/
│   ├── navigation.yml      Top-nav items
│   ├── highlights.yml      Front-page research-area cards
│   ├── members.yml         Group-member manifest (single source of truth)
│   ├── code.yml            Software/projects on /code/
│   ├── cv.yml              CV entries
│   └── papers.yml          AUTO-GENERATED — recent ADS papers
├── _layouts/               default / page / home
├── _includes/              nav, footer, paper-card, member-card
├── _sass/main.scss         Custom theme (no parent theme, light + dark mode)
├── assets/
│   ├── css/style.scss      Loads _sass/main.scss
│   └── img/                Static figures + auto-generated paper figures
├── scripts/
│   ├── fetch_papers.py     ADS query → AI summary + figure → _data/papers.yml
│   └── fetch_affiliations.py ORCID employments → members.yml
└── .github/workflows/
    ├── update-papers.yml         Weekly
    └── update-affiliations.yml   Monthly
```

## Updating content

### Day to day

| Want to change… | Edit |
|---|---|
| Hero bio, links, contact info | `_config.yml` (`author:`) and `index.md` (front matter `bio:`) |
| Front-page research-area cards | `_data/highlights.yml` |
| Long-form research descriptions | `research.md` |
| Software / open-source projects | `_data/code.yml` |
| CV entries (positions, education, awards) | `_data/cv.yml` |
| Group members (current + alumni) | `_data/members.yml` |
| Top-nav items | `_data/navigation.yml` |

Recent papers and (where ORCID iDs are listed) alumni affiliations refresh
themselves on a schedule — see below.

### Adding a group member

Append an entry to `_data/members.yml`:

```yaml
- name: Jane Doe
  role: Graduate student (USC)
  status: current             # or "alumni"
  website: https://example.com
  orcid: 0000-0000-0000-0000  # optional; enables auto-updated affiliations
```

Set `affiliation_locked: true` to prevent the scheduled job from overwriting
that member's `current_affiliation`.

## Automation

### Recent-papers pipeline (`update-papers.yml`)

Runs weekly in GitHub Actions. For each selected paper from the configured ADS
library it:

1. Fetches metadata from NASA ADS (title, authors, venue, DOI, abstract).
2. Downloads the arXiv PDF and renders its first few pages.
3. Picks the page whose dominant graphical region covers the most area, and
   crops to that figure — see *How the figure is found* below.
4. Saves the figure to `assets/img/papers/`.
5. Writes the result to `_data/papers.yml` and commits it back to the repo.

**No model is called here**, so the only secret it needs is the ADS token:

| Secret | Purpose |
| ------ | ------- |
| `NASA_ADS_API_KEY` | NASA ADS API token ([generate one here](https://ui.adsabs.harvard.edu/user/settings/token)) |

New papers land with `summary: ''`; the summaries are written separately (next
section). Run it by hand from the **Actions** tab — *Update papers*, with an
optional `limit` input.

#### The durable cache

`_data/papers_cache.yml` holds each paper's summary, abstract, and figure path
keyed by bibcode, and is **never pruned**. `papers.yml` only holds the six
papers currently on the front page, so without this cache a paper that rotated
out and later rotated back in would lose its summary and need it rewritten.
That is exactly what used to produce blank cards.

#### How the figure is found

A figure page is identified from PDF geometry, with no model involved.
`figure_bbox_in_page()` counts how many drawing paths cover each row of the
page: a plot is hundreds of overlapping paths (axes, ticks, grid, data) stacked
in one band, while the stray clip and background paths that PDFs are full of
are lone rects that can span a whole column. The densest band is the figure;
the box is then grown back over the figure's own axes and tick labels, and
trimmed clear of running heads and `Figure N.` captions. Each page is scored by
how much of it that figure covers, and the best-scoring page wins.

### Paper summaries (`/refresh-summaries`)

Summaries are written by Claude Code on the Claude subscription — there is no
API key and no per-call billing anywhere in this pipeline.

```bash
python3 scripts/summaries.py pending    # what still needs a summary
/refresh-summaries                      # in Claude Code: write and commit them
```

`scripts/summaries.py pending` lists front-page papers that have a cached
abstract but no summary. `apply` writes summaries into both
`_data/papers_cache.yml` and `_data/papers.yml`; `sync` re-copies cached
summaries into `papers.yml` if the two drift apart.

`scripts/refresh_summaries.sh` is the unattended entry point: it refuses to run
on a dirty tree, pulls, exits immediately if nothing is pending, and otherwise
invokes `/refresh-summaries`. Weekly, a few hours after the Action:

```cron
#Write summaries for new publication-page cards
20 9 * * 0	"/home/abensonca/Work/Communication/Home Pages/abensonca.github.io/scripts/refresh_summaries.sh" > /home/abensonca/.refresh-summaries.log 2>&1
```

### Affiliations pipeline (`update-affiliations.yml`)

Runs monthly. Calls the public ORCID API for every member that has an
`orcid:` field set, finds their most recent employment, and updates
`current_affiliation:` in `_data/members.yml`. Members without an ORCID iD,
or with `affiliation_locked: true`, are left alone.

> **Why not LinkedIn?** LinkedIn's terms of service prohibit scraping and they
> aggressively block unauthenticated traffic. ORCID is the practical
> alternative for academics — it has a public API and many alumni already have
> profiles.

## Running locally

```bash
bundle install
bundle exec jekyll serve --livereload
```

Then visit <http://127.0.0.1:4000/>.

To preview the auto-generation pipelines locally:

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_papers.py                  # reads ~/.ads/dev_key, or $ADS_API_TOKEN
python scripts/summaries.py pending             # papers still needing a summary
python scripts/fetch_affiliations.py --check    # dry run
```

## License

Site content is © Andrew Benson. The bundled `_sass/normalize.scss` retains
its original MIT license.
