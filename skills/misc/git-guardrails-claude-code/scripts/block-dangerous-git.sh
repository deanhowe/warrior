#!/bin/bash

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

# git restore --staged / git checkout --staged only move changes between the
# index and the working tree - they never discard working-tree content. Every
# other form of restore/checkout targeting specific files can silently discard
# real, uncommitted, never-staged work with no way back (2026-08-16 incident:
# `git checkout -- composer.json composer.lock` ran on a real project without
# checking git status first, and discarded real changes that were never
# staged - git had no copy anywhere, recovery only worked because an IDE's
# Local History happened to still have it). Checked --staged FIRST, before the
# broader patterns, so the safe form is never caught by the dangerous ones.
if echo "$COMMAND" | grep -qE "git (restore|checkout) .*--staged"; then
  exit 0
fi

DANGEROUS_PATTERNS=(
  "git push"
  "git reset --hard"
  "git clean -fd"
  "git clean -f"
  "git branch -D"
  "git checkout \."
  "git checkout --( |$)"
  "git restore \."
  "git restore( |$)"
  "push --force"
  "reset --hard"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    echo "BLOCKED: '$COMMAND' matches dangerous pattern '$pattern'. The user has prevented you from doing this. If you need to discard specific uncommitted changes, first show the user 'git diff' for the exact file(s) and get explicit confirmation — never assume a change you didn't just make is safe to discard." >&2
    exit 2
  fi
done

exit 0
