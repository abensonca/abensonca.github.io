---
layout: page
title: Code & Software
subtitle: Open-source tools that power the science
permalink: /code/
---

I believe research code should be open. The list below covers the projects I
lead or maintain; smaller utilities and forks live on
[my GitHub profile](https://github.com/{{ site.author.github }}).

<div class="highlight-grid">
  {% for project in site.data.code %}
    <article class="highlight-card">
      {% if project.image %}<img class="card-image" src="{{ project.image | relative_url }}" alt="{{ project.name | escape }}">{% endif %}
      <div class="card-body">
        <p class="card-eyebrow">{{ project.language }} &middot; {{ project.role }}</p>
        <h3>{{ project.name }}</h3>
        <p>{{ project.description }}</p>
        <p style="margin-top:auto">
          {% if project.url %}<a href="{{ project.url }}">Source</a>{% endif %}
          {% if project.docs %} &middot; <a href="{{ project.docs }}">Docs</a>{% endif %}
          {% if project.paper %} &middot; <a href="{{ project.paper }}">Paper</a>{% endif %}
        </p>
      </div>
    </article>
  {% endfor %}
</div>
