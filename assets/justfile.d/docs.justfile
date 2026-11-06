# Managed by vigOS devkit; installed only with DEVKIT_MODULES="docs".

# Compile declared entries, stamped with the Git revision; accepts --deps.
[group('docs')]
typst *args:
    @typst-guard build {{ args }}

# Compile without a revision stamp for hash comparisons; accepts --deps.
[group('docs')]
typst-canonical *args:
    @typst-guard canonical {{ args }}

# Print the pinned document toolchain's version strings as JSON.
[group('docs')]
typst-probe:
    @typst-guard probe

# List unregistered terminology for agent or reviewer triage (advisory).
[group('docs')]
glossary-candidates:
    @glossary-candidates
