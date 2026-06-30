#!/bin/bash

# --- Configuration ---
# Set the project root to the script's directory for consistency.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT" || exit

# --- Defaults ---
UPGRADE_FLAG=false
MESSAGE=""

# --- Argument Parsing ---
# Separate the --upgrade flag from the migration message.
for arg in "$@"; do
  if [[ "$arg" == "--upgrade" ]]; then
    UPGRADE_FLAG=true
  else
    # Treat all other arguments as part of the message.
    if [[ -z "$MESSAGE" ]]; then
      MESSAGE="$arg"
    else
      # Append with a space for multi-word messages.
      MESSAGE="$MESSAGE $arg"
    fi
  fi
done

# Use a default message if none was provided.
if [[ -z "$MESSAGE" ]]; then
  MESSAGE="auto migration"
fi

# --- Execution ---
# 1. Generate a new migration with the specified message.
echo "Creating migration with message: \"$MESSAGE\""
alembic revision --autogenerate -m "$MESSAGE"

# 2. Apply the migration if the --upgrade flag is set.
if [[ "$UPGRADE_FLAG" == true ]]; then
  echo "Applying migration..."
  alembic upgrade head
  echo "Database upgrade complete."
else
  echo "Migration file created. To apply it, run 'alembic upgrade head' or use the --upgrade flag."
fi