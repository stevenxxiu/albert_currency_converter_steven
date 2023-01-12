# Albert Launcher Currency Converter Extension
## Install
To install, copy or symlink this directory to `~/.local/share/albert/org.albert.extension.python/modules/currency_converter_steven/`.

## Config
Config is stored in `~/.config/albert/albert.currency_converter_steven/settings.json`.

Aliases are supported. As an example:

```json
{
  "aliases": {
    "EUR": ["eu"],
    "USD": ["us"],
    "AUD": ["au"],
    "GBP": ["uk", "pound"],
    "CNY": ["cn", "rmb"],
    "JPY": ["ja", "jp", "yen"]
  }
}
```

These are case-insensitive.

## Development Setup
To setup the project for development, run:

    $ cd currency_converter_steven/
    $ pre-commit install --hook-type pre-commit --hook-type commit-msg

To lint and format files, run:

    $ pre-commit run --all-files
