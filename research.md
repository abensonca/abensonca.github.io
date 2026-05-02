---
layout: page
title: Research
subtitle: Three threads — galaxy formation, dark matter, and synthetic surveys
permalink: /research/
---

My research aims to build a coherent theoretical picture of how galaxies form
inside the dark matter web, and to use that picture to constrain the
fundamental physics of dark matter itself. Most of this work happens through a
single open-source modeling framework, *Galacticus*, that I have been
developing for over a decade.

<section class="section" id="galacticus">
  <p class="section-eyebrow">Theory & modeling</p>
  <h2 class="section-title">Galacticus — an open model of galaxy formation</h2>

  <p>
    <a href="https://github.com/galacticusorg/galacticus/wiki"><em>Galacticus</em></a>
    is a semi-analytic model that follows the assembly of dark matter halos and the
    formation of the galaxies inside them — gas cooling, star formation, feedback,
    chemical evolution, mergers, and the many environmental processes that act on
    satellite galaxies. It is fully open-source, written in modern Fortran with a
    Python and shell tooling layer, and is used by groups around the world.
  </p>
  <p>
    Because <em>Galacticus</em> is fast and modular it can explore the consequences
    of new physics — alternative dark matter models, modified initial conditions,
    new feedback prescriptions — across enormous parameter spaces. That makes it
    well suited to the inverse problems that dominate modern cosmology: given a
    set of observations, what microphysics is allowed?
  </p>
</section>

<section class="section" id="dark-matter">
  <p class="section-eyebrow">Fundamental physics</p>
  <h2 class="section-title">Constraining the microphysics of dark matter</h2>

  <p>
    On large scales dark matter behaves like a cold, collisionless fluid — but on
    the scales of galaxies and their substructure, the underlying particle
    physics matters. My group uses several complementary probes to test models
    beyond cold dark matter (CDM):
  </p>

  <h3>Self-interacting dark matter and the gravothermal instability</h3>
  <img src="{{ '/assets/img/gravothermal.png' | relative_url }}" alt="gravothermal solutions" style="width:280px; float: right; margin: 0 0 1rem 1.5rem; border-radius: 8px;">
  <p>
    If dark matter particles scatter from each other, halos undergo a runaway
    core-collapse driven by the gravothermal instability. In
    <a href="https://ui.adsabs.harvard.edu/abs/2022arXiv220502957Y">Yang, Benson et&nbsp;al. (2022)</a>
    we derive a universal scaling solution for this evolution that agrees with
    full N-body simulations to high accuracy while being orders of magnitude
    faster — opening up parameter-space studies that simulations cannot reach.
  </p>

  <h3>Tidal evolution of subhalos</h3>
  <img src="{{ '/assets/img/tidal_tracks.png' | relative_url }}" alt="tidal tracks" style="width:280px; float: left; margin: 0 1.5rem 1rem 0; border-radius: 8px;">
  <p>
    Subhalos lose mass and reshape as they orbit a host. In
    <a href="https://ui.adsabs.harvard.edu/abs/2022MNRAS.517.1398B">Benson &amp; Du (2022)</a>
    we developed a fast semi-analytic model of this evolution that reproduces
    high-resolution simulations — a key ingredient for predicting the abundance
    and structure of the substructure that dark-matter probes target.
  </p>

  <h3>Constraining warm dark matter with strong lensing</h3>
  <img src="{{ '/assets/img/lensing.png' | relative_url }}" alt="strong lens model" style="width:280px; float: right; margin: 0 0 1rem 1.5rem; border-radius: 8px;">
  <p>
    Tens of millions of model lensing systems generated with <em>Galacticus</em>
    were used in <a href="https://ui.adsabs.harvard.edu/abs/2020MNRAS.491.6077G/abstract">Gilman, Benson et&nbsp;al. (2020)</a>
    to translate observed gravitational quad-lens flux ratios into a constraint on
    the warm-dark-matter particle mass.
  </p>

  <h3>Constrained merger trees</h3>
  <img src="{{ '/assets/img/brownian_bridge.png' | relative_url }}" alt="Brownian bridge excursions" style="width:280px; float: left; margin: 0 1.5rem 1rem 0; border-radius: 8px;">
  <p>
    For predicting the Milky Way's substructure population it matters that we
    condition on the host being a Milky Way that hosts an LMC.
    <a href="https://ui.adsabs.harvard.edu/abs/2023MNRAS.tmp..639N">Nadler, Benson et&nbsp;al. (2023)</a>
    introduced a Brownian-bridge approach for constructing merger trees that
    automatically satisfy these kinds of physical constraints.
  </p>

  <h3>How baryons reshape the dark-matter halo mass function</h3>
  <p>
    Even within ΛCDM, baryons suppress small-halo formation in subtle but
    quantifiable ways. <a href="https://ui.adsabs.harvard.edu/abs/2020MNRAS.493.1268B/abstract">Benson (2020)</a>
    quantifies that effect — a critical input for any program that aims to use
    small-scale structure to test dark-matter physics.
  </p>
</section>

<section class="section" id="surveys">
  <p class="section-eyebrow">Surveys & forecasts</p>
  <h2 class="section-title">Synthetic universes for next-generation surveys</h2>

  <h3>Roman Space Telescope — High-Latitude Spectroscopic Survey</h3>
  <img src="{{ '/assets/img/elgCounts.png' | relative_url }}" alt="ELG number counts" style="width:280px; float: right; margin: 0 0 1rem 1.5rem; border-radius: 8px;">
  <p>
    I am a member of the
    <a href="https://roman.gsfc.nasa.gov/">Roman</a> Galaxy Redshift Survey
    Project Infrastructure Team (GRS PIT). We use <em>Galacticus</em> to build
    the synthetic emission-line galaxy populations that drive Roman's
    cosmological forecasts — predictions that have to fold together emission-line
    physics, dust attenuation, redshift completeness, and selection.
    See <a href="https://ui.adsabs.harvard.edu/abs/2019MNRAS.490.3667Z/abstract">Zhai, Benson et&nbsp;al. (2019)</a>
    for our [O&nbsp;II] forecasts.
  </p>

  <h3>NASA Open Universe</h3>
  <p>
    As part of the NASA <a href="https://openuniverse.us/">Open Universe</a>
    initiative, my group contributes the galaxy-formation modeling needed to
    tie together joint synthetic surveys for Rubin, Roman, and Euclid — making
    sure the same underlying galaxy populations appear consistently across each
    instrument's mock observations.
  </p>

  <h3>Synthetic skies for Rubin LSST</h3>
  <img src="{{ '/assets/img/colors.png' | relative_url }}" alt="LSST galaxy color distribution" style="width:280px; float: left; margin: 0 1.5rem 1rem 0; border-radius: 8px;">
  <p>
    A <em>Galacticus</em>-based synthetic survey for the
    <a href="https://www.lsst.org/">Rubin Observatory</a> Legacy Survey of Space
    and Time, covering galaxy colors, lensing, and clustering, was published in
    <a href="https://ui.adsabs.harvard.edu/abs/2019ApJS..245...26K/abstract">Korytov et&nbsp;al. (2019)</a>.
  </p>
</section>

<section class="section" id="galaxies">
  <p class="section-eyebrow">Galaxy physics</p>
  <h2 class="section-title">Selected galaxy-formation results</h2>

  <h3>The mass–metallicity relation of Milky Way dwarfs</h3>
  <img src="{{ '/assets/img/mass_metallicity.png' | relative_url }}" alt="mass-metallicity relation" style="width:280px; float: right; margin: 0 0 1rem 1.5rem; border-radius: 8px;">
  <p>
    Dwarf galaxies are the most dark-matter-dominated systems we know.
    <a href="https://ui.adsabs.harvard.edu/abs/2022arXiv220913663W">Weerasooriya, Benson et&nbsp;al. (2022)</a>
    used <em>Galacticus</em> to predict the mass–metallicity relation of Milky Way
    satellites; the agreement with observations puts strong constraints on
    feedback and outflows in low-mass halos.
  </p>

  <h3>Dust extinction curves from radiative transfer</h3>
  <img src="{{ '/assets/img/extinction_curves.png' | relative_url }}" alt="dust extinction curves" style="width:280px; float: left; margin: 0 1.5rem 1rem 0; border-radius: 8px;">
  <p>
    Survey forecasts need realistic dust attenuation. In
    <a href="https://ui.adsabs.harvard.edu/abs/2018RNAAS...2..188B/abstract">Benson (2018)</a>
    I computed extinction curves for a population of model galaxies using a Monte
    Carlo radiative transfer treatment.
  </p>
</section>
