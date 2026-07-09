# Opt-in Python starter

Adds a Python package layout (`pyproject.toml`, `src/`, `tests/`) to a vigOS
workspace whose scaffold is language-neutral (#929).

```bash
nix flake init -t github:vig-os/devcontainer#python
```

`nix flake init -t` copies these files verbatim (no placeholder substitution),
so rename the concrete `example_pkg` to your package name in four places:

1. `pyproject.toml` -> `[project] name`
2. `pyproject.toml` -> `[tool.hatch.build.targets.wheel] packages`
3. `src/example_pkg/` -> `src/<your_pkg>/`
4. `tests/test_example.py` -> `import <your_pkg>`

Then `just sync` and `just test`.
