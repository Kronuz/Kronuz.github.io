# Kronuz.io site

This directory contains the code for the Kronuz.io site, [kronuz.io](https://kronuz.io).


## Running locally

1. `gem install bundler`
2. `bundle exec jekyll serve --livereload`


## Updating Font Awesome
Only a handful of fonts are included in the include Font Awesome fonts. To add
more, it's needed to modify `icomoon-selection.json` and regenerate the fonts:

1. Go to <https://icomoon.io/app/>
2. Choose Import Icons and load `icomoon-selection.json`
3. Choose Generate Font → Download
4. Copy the font files and adapt the CSS to the paths we use
