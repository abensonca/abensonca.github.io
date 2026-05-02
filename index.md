---
layout: home
title: Andrew Benson
description: Theoretical Astrophysicist · Carnegie Observatories
permalink: /
bio: I am a Staff Scientist at the Carnegie Observatories. My research is focused on
  understanding the nature of dark matter and the process of galaxy formation —
  combining analytic models, numerical simulations, and large astronomical surveys.
---

<section class="section">
  <p class="section-eyebrow">Research focus</p>
  <h2 class="section-title">What I work on</h2>
  <p class="section-lead">
    Three threads tie my research together: building a coherent theoretical model
    of galaxy formation; constraining the microphysics of dark matter; and
    designing the synthetic universes that next-generation surveys need to
    interpret their data.
  </p>

  <div class="highlight-grid">
    {% for h in site.data.highlights %}
      <a class="highlight-card" href="{{ h.url | relative_url }}">
        {% if h.image %}<img class="card-image" src="{{ h.image | relative_url }}" alt="{{ h.title | escape }}">{% endif %}
        <div class="card-body">
          <p class="card-eyebrow">{{ h.eyebrow }}</p>
          <h3>{{ h.title }}</h3>
          <p>{{ h.description }}</p>
          <span class="card-link">Read more &rarr;</span>
        </div>
      </a>
    {% endfor %}
  </div>
</section>

<section class="section">
  <p class="section-eyebrow">Recent work</p>
  <h2 class="section-title">Selected recent papers</h2>
  <p class="section-lead">
    These cards are rebuilt automatically from
    <a href="{{ site.author.ads }}">my NASA&nbsp;ADS library</a>
    on a weekly schedule. Summaries and figures are generated from the paper itself.
  </p>

  {% assign papers = site.data.papers | default: empty %}
  {% if papers and papers.size > 0 %}
    <div class="papers-grid">
      {% for paper in papers limit: 6 %}
        {% include paper-card.html paper=paper %}
      {% endfor %}
    </div>
    <p style="margin-top:1.5rem"><a href="{{ '/publications/' | relative_url }}">See all recent papers &rarr;</a></p>
  {% else %}
    <div class="callout">
      The scheduled fetcher hasn't populated <code>_data/papers.yml</code> yet.
      It will run automatically once the workflow has access to <code>ADS_API_TOKEN</code>.
      Until then, see the full list at <a href="{{ site.author.ads }}">NASA&nbsp;ADS</a>.
    </div>
  {% endif %}
</section>

<section class="section">
  <p class="section-eyebrow">Open source</p>
  <h2 class="section-title">Galacticus</h2>
  <p class="section-lead">
    Most of my modeling work happens inside
    <a href="https://github.com/galacticusorg/galacticus/wiki"><em>Galacticus</em></a>,
    an open-source semi-analytic model of galaxy formation that I wrote and
    continue to develop. It's used by groups around the world to study dark matter,
    galaxy evolution, and forecast observations for upcoming surveys.
    <a href="{{ '/code/' | relative_url }}">See the full software stack &rarr;</a>
  </p>
</section>
