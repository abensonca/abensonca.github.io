---
layout: page
title: Publications
subtitle: Recent papers — automatically refreshed from NASA ADS
permalink: /publications/
---

The cards below are populated weekly by a GitHub Actions workflow that queries
[my NASA&nbsp;ADS library]({{ site.author.ads }}), generates a short plain-language
summary using a small language model, and extracts a representative figure
from each paper. For the complete publication record see
[my ADS library]({{ site.author.ads }}) or
[my ORCID profile](https://orcid.org/{{ site.author.orcid }}).

{% assign papers = site.data.papers | default: empty %}
{% if papers and papers.size > 0 %}
  <div class="papers-grid">
    {% for paper in papers %}
      {% include paper-card.html paper=paper %}
    {% endfor %}
  </div>
{% else %}
  <div class="callout">
    <p>
      The publications data file (<code>_data/papers.yml</code>) hasn't been
      generated yet. Once the
      <a href="https://github.com/{{ site.author.github }}/{{ site.github.repository_name }}/actions/workflows/update-papers.yml">update-papers</a>
      workflow runs (it requires the <code>ADS_API_TOKEN</code> repo secret),
      this page will populate automatically.
    </p>
    <p>
      For now, browse the full list at
      <a href="{{ site.author.ads }}">NASA&nbsp;ADS</a>.
    </p>
  </div>
{% endif %}
