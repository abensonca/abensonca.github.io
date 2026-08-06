---
layout: page
title: Publications
subtitle: Recent papers — automatically refreshed from NASA ADS
permalink: /publications/
---

The cards below are refreshed weekly from
[my NASA&nbsp;ADS library]({{ site.author.ads }}), with a representative figure
extracted from each paper and a short plain-language summary of its abstract.
For the complete publication record see
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
      workflow runs (it requires the <code>NASA_ADS_API_KEY</code> repo secret),
      this page will populate automatically.
    </p>
    <p>
      For now, browse the full list at
      <a href="{{ site.author.ads }}">NASA&nbsp;ADS</a>.
    </p>
  </div>
{% endif %}
