#!/usr/bin/env bash
# Managed by vigOS devkit — regenerated on upgrade; local edits are lost.
# Customize in justfile.project. Bugs / missing tools: https://github.com/vig-os/devkit/issues

# Source from the promote PR gates. A plan-limited response is terminal;
# other API errors retain the standard retry policy (#1851).
if [ "${1:-}" = --query ]; then
  if rules=$(gh api "repos/${GITHUB_REPOSITORY}/rules/branches/main" 2>"$RUNNER_TEMP/rules.err"); then
    printf "%s\n" "$rules"
  elif grep -Fq "HTTP 403" "$RUNNER_TEMP/rules.err" &&
    grep -Fq "Upgrade to GitHub Pro" "$RUNNER_TEMP/rules.err"; then
    echo PLAN_LIMIT
  else
    cat "$RUNNER_TEMP/rules.err" >&2
    exit 1
  fi
  exit 0
fi
RULES_JSON=$(retry --retries 3 --backoff 5 --max-backoff 30 -- \
  bash "${BASH_SOURCE[0]}" --query)
if [ "$RULES_JSON" = PLAN_LIMIT ]; then
  REQUIRED_APPROVALS=${DEVKIT_RELEASE_REQUIRED_APPROVALS:-1}
  if ! [[ "$REQUIRED_APPROVALS" =~ ^[0-9]+$ ]]; then
    echo "ERROR: DEVKIT_RELEASE_REQUIRED_APPROVALS must be a non-negative integer" >&2
    exit 1
  fi
  echo "GitHub plan limit: rulesets unavailable; requiring $REQUIRED_APPROVALS approving review(s)"
  # GitHub has no reviewDecision without protection. Count reviews explicitly
  # to enforce the fallback count even if a decision is supplied.
  export REVIEW_DECISION=null
else
  REQUIRED_APPROVALS=$(echo "$RULES_JSON" | jq '[.[] | select(.type == "pull_request") | .parameters.required_approving_review_count // 0] | max // 0')
fi

# Used by both gates when reviewDecision is unavailable (including plan limits).
count_release_approvals() {
  local head author
  head=$(echo "$PR_JSON" | jq -r '.[0].headRefOid')
  author=$(echo "$PR_JSON" | jq -r '.[0].author.login | ascii_downcase')
  retry --retries 3 --backoff 5 --max-backoff 30 -- gh api --paginate --slurp \
    "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews" | jq \
    --arg head "$head" --arg author "$author" '
      add | map(select(.user.login != null))
      | map(select(.state == "APPROVED" or .state == "CHANGES_REQUESTED"
          or .state == "DISMISSED"))
      | group_by(.user.login | ascii_downcase)
      | map(max_by(.submitted_at, .id))
      | map(select(.state == "APPROVED" and .commit_id == $head
          and (.user.login | ascii_downcase) != $author)) | length'
}
