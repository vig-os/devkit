#!/usr/bin/env bash
# Sourced by both promote gates. Open PRs continue through the existing checks;
# verified merged PRs let the caller skip open-only checks.
# shellcheck disable=SC2034  # PR_JSON is consumed by the sourcing workflow.
set -euo pipefail

find_release_pr() {
  FIELDS=number,state,isDraft,reviewDecision,statusCheckRollup,headRefOid,mergeCommit,mergedBy,mergedAt
  PR_JSON=$(gh pr list --head "release/$VERSION" --base main --state open --json "$FIELDS" --limit 2)
  if [ "$(jq length <<< "$PR_JSON")" = 0 ]; then
    PR_JSON=$(gh pr list --head "release/$VERSION" --base main --state all --json "$FIELDS" --limit 2)
  fi
  PR_COUNT=$(jq length <<< "$PR_JSON")
  if [ "$PR_COUNT" != 1 ]; then
    echo "ERROR: Expected exactly 1 PR from release/$VERSION to main, found $PR_COUNT"
    exit 1
  fi
  PR_NUMBER=$(jq -r '.[0].number' <<< "$PR_JSON")
  echo "pr_number=$PR_NUMBER" >> "$GITHUB_OUTPUT"
  PR_STATE=$(jq -r '.[0].state' <<< "$PR_JSON")
  if [ "$PR_STATE" = OPEN ]; then
    echo 'already_merged=false' >> "$GITHUB_OUTPUT"
    return 0
  fi
  if [ "$PR_STATE" != MERGED ]; then
    echo "ERROR: PR #$PR_NUMBER is closed-unmerged; refusing promotion"
    exit 1
  fi

  verify_merged_pr
}

verify_merged_pr() {
  REVIEW_DECISION=$(jq -r '.[0].reviewDecision' <<< "$PR_JSON")
  if [ "$REVIEW_DECISION" = null ] || [ -z "$REVIEW_DECISION" ]; then
    HEAD_SHA=$(jq -r '.[0].headRefOid' <<< "$PR_JSON")
    APPROVED_COUNT=$(gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER/reviews" |
      jq --arg head "$HEAD_SHA" 'add | map(select(.state == "APPROVED" and .commit_id == $head)) | length')
    if [ "$APPROVED_COUNT" -gt 0 ]; then
      REVIEW_DECISION=APPROVED
    fi
  fi
  if [ "$REVIEW_DECISION" != APPROVED ]; then
    echo "ERROR: Merged PR #$PR_NUMBER is not approved on its final head"
    exit 1
  fi

  # Compare base...main: ahead/identical proves base is an ancestor of main.
  verify_ancestor() {
      local ref=$1 label=$2 status
      status=$(gh api "repos/$GITHUB_REPOSITORY/compare/$ref...main" --jq '.status')
      case "$status" in
        ahead|identical) ;;
        *) echo "ERROR: $label is not an ancestor of main ($status)"; exit 1 ;;
      esac
  }
  MERGE_SHA=$(jq -r '.[0].mergeCommit.oid // empty' <<< "$PR_JSON")
  if [ -z "$MERGE_SHA" ]; then
    echo "ERROR: Merged PR #$PR_NUMBER has no merge commit"
    exit 1
  fi
  verify_ancestor "$MERGE_SHA" 'Release PR merge commit'
  verify_ancestor "$VERSION" "Tag $VERSION"
  echo "already merged by $(jq -r '.[0].mergedBy.login' <<< "$PR_JSON") at $(jq -r '.[0].mergedAt' <<< "$PR_JSON")"
  echo 'Skipping open-only mergeability and CI-pending checks for the verified merged PR'
  echo 'already_merged=true' >> "$GITHUB_OUTPUT"
}
find_release_pr
