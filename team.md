---
layout: page
title: Research Group
subtitle: Current members and alumni
permalink: /team/
---

This page is generated automatically from
[`_data/members.yml`](https://github.com/{{ site.author.github }}/{{ site.github.repository_name }}/blob/main/_data/members.yml).
For alumni who provided an ORCID iD, current affiliations are refreshed on a
schedule from their ORCID profile.

{% assign current = site.data.members | where: "status", "current" %}
{% assign alumni  = site.data.members | where: "status", "alumni" %}

<section class="section">
  <h2 class="section-title">Current</h2>
  <div class="members-grid">
    {% for m in current %}
      {% if m.website and m.website != '' %}{% assign link = m.website %}
      {% elsif m.linkedin %}{% assign link = m.linkedin %}
      {% else %}{% assign link = nil %}{% endif %}
      <article class="member-card">
        <h3 class="member-name">
          {% if link %}<a href="{{ link }}">{{ m.name }}</a>{% else %}{{ m.name }}{% endif %}
        </h3>
        {% if m.role %}<p class="member-role">{{ m.role }}</p>{% endif %}
      </article>
    {% endfor %}
  </div>
</section>

<section class="section">
  <h2 class="section-title">Alumni</h2>
  <div class="members-grid">
    {% for m in alumni %}
      {% if m.website and m.website != '' %}{% assign link = m.website %}
      {% elsif m.linkedin %}{% assign link = m.linkedin %}
      {% else %}{% assign link = nil %}{% endif %}
      <article class="member-card">
        <h3 class="member-name">
          {% if link %}<a href="{{ link }}">{{ m.name }}</a>{% else %}{{ m.name }}{% endif %}
        </h3>
        {% if m.role %}<p class="member-role">{{ m.role }}</p>{% endif %}
        {% if m.current_affiliation %}<p class="member-current">Now: {{ m.current_affiliation }}</p>{% endif %}
      </article>
    {% endfor %}
  </div>
</section>
