#!/bin/bash
# Shared preserved-config block ranges and splices (#1654, #1994).

hook_block_range() {
    awk -v id="$2" '
        # Exact id, never a prefix (#1727): the token after the marker is
        # extracted and compared as a STRING, so on this sentinel path `id` is
        # never interpolated into a regex and a metacharacter in a hook id cannot
        # change what matches. (The structural branch below still builds its
        # `- id:` pattern from `id`; hook ids are plain words.)
        function sentinel(line, dir,    tok) {
            if (!match(line, /^[[:space:]]*# (>>>|<<<) devkit:[^[:space:]]+/)) return 0
            tok = substr(line, RSTART, RLENGTH)
            sub(/^[[:space:]]*/, "", tok)
            return tok == "# " dir " devkit:" id
        }
        { L[NR] = $0 }
        sentinel($0, ">>>") { ss = NR }
        sentinel($0, "<<<") { se = NR }
        END {
            if (ss && se && se >= ss) { print ss, se; exit 0 }
            for (i = 1; i <= NR; i++) {
                if (L[i] ~ /^[[:space:]]*-[[:space:]]+repo:/) cur = i
                if (cur && L[i] ~ ("^[[:space:]]*-[[:space:]]+id:[[:space:]]+" id "[[:space:]]*$")) {
                    entry = cur
                    break
                }
            }
            if (!entry) exit 1
            e = NR
            for (i = entry + 1; i <= NR; i++)
                if (L[i] ~ /^[[:space:]]*-[[:space:]]+repo:/) { e = i - 1; break }
            while (e > entry && (L[e] ~ /^[[:space:]]*$/ || L[e] ~ /^[[:space:]]*#/)) e--
            start = entry
            while (start > 1 && L[start - 1] ~ /^[[:space:]]*#/ &&
                   !index(L[start - 1], "# >>> devkit:") &&
                   !index(L[start - 1], "# <<< devkit:"))
                start--
            print start, e
        }
    ' "$1"
}

splice_lines() {
    local file="$1" start="$2" end="$3" text="$4"
    local tmp
    tmp="$(mktemp)"
    if [[ "$start" -gt 1 ]]; then
        head -n "$((start - 1))" "$file" > "$tmp"
    else
        : > "$tmp"
    fi
    printf '%s\n' "$text" >> "$tmp"
    tail -n +"$((end + 1))" "$file" >> "$tmp"
    cat "$tmp" > "$file"
    rm -f "$tmp"
}

delete_lines() {
    local file="$1" start="$2" end="$3"
    local tmp
    tmp="$(mktemp)"
    {
        head -n "$((start - 1))" "$file"
        tail -n +"$((end + 1))" "$file"
    } > "$tmp"
    cat "$tmp" > "$file"
    rm -f "$tmp"
}
