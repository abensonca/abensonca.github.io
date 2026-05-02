---
layout: page
title: Curriculum Vitae
subtitle: ""
permalink: /cv/
---

{% assign cv = site.data.cv %}

{% if cv.current %}
<p class="section-lead">
  <strong>{{ cv.current.position }}</strong>, {{ cv.current.affiliation }}.
  Full publication list:
  <a href="{{ cv.links.ads }}">NASA ADS</a> ·
  <a href="{{ cv.links.orcid }}">ORCID</a> ·
  <a href="{{ cv.links.arxiv }}">arXiv</a>.
</p>
{% endif %}

{% if cv.positions and cv.positions.size > 0 %}
<section class="cv-section">
  <h2>Positions</h2>
  {% for entry in cv.positions %}
    <div class="cv-entry">
      <div class="cv-date">{{ entry.date }}</div>
      <div class="cv-detail">
        <h4>{{ entry.title }}</h4>
        <p>{{ entry.detail }}</p>
      </div>
    </div>
  {% endfor %}
</section>
{% endif %}

{% if cv.education and cv.education.size > 0 %}
<section class="cv-section">
  <h2>Education</h2>
  {% for entry in cv.education %}
    <div class="cv-entry">
      <div class="cv-date">{{ entry.date }}</div>
      <div class="cv-detail">
        <h4>{{ entry.title }}</h4>
        <p>{{ entry.detail }}</p>
      </div>
    </div>
  {% endfor %}
</section>
{% endif %}

{% if cv.awards and cv.awards.size > 0 %}
<section class="cv-section">
  <h2>Awards</h2>
  {% for entry in cv.awards %}
    <div class="cv-entry">
      <div class="cv-date">{{ entry.date }}</div>
      <div class="cv-detail">
        <h4>{{ entry.title }}</h4>
        <p>{{ entry.detail }}</p>
      </div>
    </div>
  {% endfor %}
</section>
{% endif %}

{% if cv.service and cv.service.size > 0 %}
<section class="cv-section">
  <h2>Service & Collaborations</h2>
  {% for entry in cv.service %}
    <div class="cv-entry">
      <div class="cv-date">{{ entry.date }}</div>
      <div class="cv-detail">
        <h4>{{ entry.title }}</h4>
        <p>{{ entry.detail }}</p>
      </div>
    </div>
  {% endfor %}
</section>
{% endif %}
