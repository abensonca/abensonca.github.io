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

Runs weekly. For each selected paper from the configured ADS library it:

1. Fetches metadata from NASA ADS.
2. Downloads the arXiv PDF, renders the first ~12 pages.
3. Asks a small vision-capable model on
   [GitHub Models](https://docs.github.com/en/github-models) to pick the page
   containing the most representative figure.
4. Crops whitespace and saves the figure to `assets/img/papers/`.
5. Asks the same model for a two-sentence plain-English summary.
6. Writes the result to `_data/papers.yml` and commits it back to the repo.

If a paper already has a figure on disk and a summary in the data file, the
expensive steps are skipped — so re-runs are cheap.

#### Required secret

Create a repo secret named **`ADS_API_TOKEN`** with a NASA ADS API token
([generate one here](https://ui.adsabs.harvard.edu/user/settings/token)). The
default `GITHUB_TOKEN` is wired up for GitHub Models access via the
`models: read` permission declared in the workflow.

#### Manual run

From the **Actions** tab, run *Update papers* with an optional `limit` input.

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
ADS_API_TOKEN=… GITHUB_TOKEN=… python scripts/fetch_papers.py
python scripts/fetch_affiliations.py --check    # dry run
```

## License

Site content is © Andrew Benson. The bundled `_sass/normalize.scss` retains
its original MIT license.
