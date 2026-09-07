# Steady State Games / 10,000 font styles

500 refined Core, 250 Balanced and 9,250 Experimental styles. These branch from ten original drawing roots. All font software uses OFL 1.1. Commercial and noncommercial font use are free under the license.

The core has 184 supported characters and additional proportion/counter/spacing/raster checks. Experimental fonts have 107 characters and intentional display effects. Individual optical sign-off, broad language coverage and long-reading validation remain pending.

## Browse and download
The GitHub Pages catalog previews only 20 visible fonts at a time. Releases hold the installable fonts, source archive, and 400 family/treatment groups of 25 styles each.

Release: https://github.com/SteadyStateGames/10kFonts/releases/tag/v0.4.0

The initial repository LICENSE is preserved. Font files and drawing sources are distributed under OFL.txt; each font download includes that license.

## Rebuild
Download SSG-10000-Source.zip from the release; it includes the exact previous 2,000-style baseline input. Follow its README. Python 3.14 and workbench/requirements.txt reproduce the pipeline; no third-party font outlines are used.

The Pages workflow consumes the validated SSG-10000-Site.zip release asset, verifies its SHA-256, and deploys that static payload. Font generation is separate from publishing. Download binaries stay in Releases; the Git repository stays focused on editable source.

## Review
Use the catalog's review flags and export them as JSON when reporting problem glyphs. Include font name, text, size, platform, and a screenshot if possible.
