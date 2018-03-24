# Xapiand docs site

This directory contains the code for the Xapiand docs site, [kronuz.io/Xapiand](https://kronuz.io/Xapiand).


## Contributing

For information about contributing, see the [Contributing page](https://kronuz.io/Xapiand/docs/contributing/).


## Running locally

1. `gem install jekyll bundler`
2. `bundle exec jekyll serve`

You can preview your contributions before opening a pull request by running from within the directory:

1. `bundle install --without test test_legacy benchmark`
2. `bundle exec rake site:preview`


## Updating Font Awesome
Only a handful of fonts are included in the include Font Awesome fonts. To add
more, it's needed to modify `icomoon-selection.json` and regenerate the fonts:

1. Go to <https://icomoon.io/app/>
2. Choose Import Icons and load `icomoon-selection.json`
3. Choose Generate Font → Download
4. Copy the font files and adapt the CSS to the paths we use
