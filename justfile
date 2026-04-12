# ha-addons deployment recipes
#
# Usage (for Claude and humans):
#
#   just push "commit message"
#     Stash local changes, pull --rebase from origin, pop stash,
#     stage all changes, commit with the given message, and push.
#
#   just wait-and-update <addon>
#     Poll the CI workflow for deploy-<addon>.yml until it completes.
#     On success, SSH to Home Assistant and run:
#       ha store refresh
#       ha apps update <detected-slug>
#     On failure or timeout, exit with an error.
#
#   just pushdeploy <addon> "commit message"
#     Run push, then wait-and-update sequentially.
#
# Variables (override with `just --set var value`):
#   ha_host         HA CLI SSH host (default: 192.168.0.14)
#   ha_user         HA CLI SSH user (default: root)
#   poll_interval   CI poll frequency in seconds (default: 30)
#   ci_timeout      CI max wait in seconds (default: 1800 = 30 min)

ha_host := "192.168.0.14"
ha_user := "root"
poll_interval := "30"
ci_timeout := "1800"

# Stash, pull --rebase, pop, add all, commit, push.
# Parameters:
#   message - the git commit message (required)
# Example: just push "fix(autoanalyst): handle empty tweet bodies"
push message:
    #!/usr/bin/env bash
    set -euo pipefail

    DIRTY=""
    if [ -n "$(git status --porcelain)" ]; then
        DIRTY=1
        echo ":: Stashing local changes..."
        git stash
    fi

    echo ":: Pulling with rebase..."
    git pull --rebase

    if [ -n "$DIRTY" ]; then
        echo ":: Popping stash..."
        git stash pop
    fi

    echo ":: Staging all changes..."
    git add -A

    echo ":: Committing..."
    git commit -m "{{message}}"

    echo ":: Pushing..."
    git push

    echo ":: Done."

# Monitor CI workflow for an add-on, then update the HA app.
# Parameters:
#   addon - add-on directory name (e.g., autoanalyst, claudecode-ea, atomic)
# Example: just wait-and-update autoanalyst
wait-and-update addon:
    #!/usr/bin/env bash
    set -euo pipefail

    WORKFLOW="deploy-{{addon}}.yml"
    POLL_INTERVAL={{poll_interval}}
    CI_TIMEOUT={{ci_timeout}}
    HA_HOST="{{ha_host}}"
    HA_USER="{{ha_user}}"

    echo ":: Finding latest CI run for ${WORKFLOW}..."
    RUN_JSON=$(gh run list --workflow "$WORKFLOW" --branch master --limit 1 --json databaseId,status,conclusion,url)
    RUN_ID=$(echo "$RUN_JSON" | jq -r '.[0].databaseId')

    if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
        echo "ERROR: No workflow runs found for ${WORKFLOW}"
        exit 1
    fi

    echo ":: Watching run ${RUN_ID}..."
    ELAPSED=0
    while true; do
        VIEW_JSON=$(gh run view "$RUN_ID" --json status,conclusion,url)
        STATUS=$(echo "$VIEW_JSON" | jq -r '.status')
        CONCLUSION=$(echo "$VIEW_JSON" | jq -r '.conclusion')
        URL=$(echo "$VIEW_JSON" | jq -r '.url')

        if [ "$STATUS" = "completed" ]; then
            if [ "$CONCLUSION" = "success" ]; then
                echo ":: CI passed."
                break
            else
                echo "ERROR: CI finished with conclusion: ${CONCLUSION}"
                echo "       Run: ${URL}"
                exit 1
            fi
        fi

        if [ "$ELAPSED" -ge "$CI_TIMEOUT" ]; then
            echo "ERROR: CI timed out after ${ELAPSED}s"
            echo "       Run: ${URL}"
            exit 1
        fi

        echo "   Status: ${STATUS} (${ELAPSED}s elapsed, polling every ${POLL_INTERVAL}s)"
        sleep "$POLL_INTERVAL"
        ELAPSED=$((ELAPSED + POLL_INTERVAL))
    done

    echo ":: Refreshing HA add-on store..."
    ssh "${HA_USER}@${HA_HOST}" "ha store refresh"

    echo ":: Detecting app slug for '{{addon}}'..."
    SLUG=$(ssh "${HA_USER}@${HA_HOST}" "ha apps list --raw-json" | jq -r '.data.addons[] | select(.slug | test("{{addon}}")) | .slug')

    if [ -z "$SLUG" ] || [ "$SLUG" = "null" ]; then
        echo "ERROR: Could not find HA app slug matching '{{addon}}'"
        exit 1
    fi

    echo ":: Updating ${SLUG}..."
    ssh "${HA_USER}@${HA_HOST}" "ha apps update ${SLUG}"

    echo ":: Done. ${SLUG} updated."

# Push changes then wait for CI and update the HA app.
# Parameters:
#   addon   - add-on directory name (e.g., autoanalyst, claudecode-ea, atomic)
#   message - the git commit message (required)
# Example: just pushdeploy autoanalyst "fix(autoanalyst): handle empty tweet bodies"
pushdeploy addon message:
    just push "{{message}}"
    just wait-and-update "{{addon}}"
