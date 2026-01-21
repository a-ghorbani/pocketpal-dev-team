#!/bin/bash
# Hook script to block git commits to main/master branch
# Exit code 2 = block the operation
# Exit code 0 = allow the operation

# Get current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    echo "BLOCKED: Cannot commit directly to '$CURRENT_BRANCH' branch."
    echo "Please work on a feature branch in a worktree."
    exit 2
fi

# Allow the commit
exit 0
