# ha-addons deployment recipes
#
# Usage (for Claude and humans):
#
#   just push "commit message" [files...]
#     Stash local changes, pull --rebase from origin, pop stash,
#     stage specified files (or all if none given), commit with the given message, and push.
#
#   just wait-and-update <addon>
#     Poll the CI workflow for deploy-<addon>.yml until it completes.
#     On success, SSH to Home Assistant and run:
#       ha store refresh
#       ha apps update <detected-slug>
#     On failure or timeout, exit with an error.
#
#   just pushdeploy <addon> "commit message" [files...]
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

# Stash, pull --rebase, pop, add files, commit, push.
# Parameters:
#   message - the git commit message (required)
#   files   - files/dirs to stage (optional, defaults to -A)
# Examples:
#   just push "fix(autoanalyst): handle empty tweet bodies"
#   just push "feat(atomic): add health check" atomic/
push message *files:
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

    FILES="{{files}}"
    if [ -z "$FILES" ]; then
        echo ":: Staging all changes..."
        git add -A
    else
        echo ":: Staging: $FILES"
        git add $FILES
    fi

    echo ":: Committing..."
    git commit -m "{{message}}"

    echo ":: Pushing..."
    git push

    echo ":: Done."

# Monitor CI workflow for an add-on, then update the HA app.
# Finds the CI run matching the given commit SHA (or HEAD if omitted),
# waits for it to complete, then refreshes the HA store and updates the app.
# Parameters:
#   addon - add-on directory name (e.g., autoanalyst, claudecode-ea, atomic)
#   sha   - (optional) commit SHA to match; defaults to current HEAD
# Examples:
#   just wait-and-update autoanalyst
#   just wait-and-update autoanalyst abc1234
wait-and-update addon sha="":
    #!/usr/bin/env bash
    set -euo pipefail

    WORKFLOW="deploy-{{addon}}.yml"
    POLL_INTERVAL={{poll_interval}}
    CI_TIMEOUT={{ci_timeout}}
    HA_HOST="{{ha_host}}"
    HA_USER="{{ha_user}}"

    SHA="{{sha}}"
    if [ -z "$SHA" ]; then
        SHA=$(git rev-parse HEAD)
    fi

    echo ":: Waiting for CI run for ${WORKFLOW} @ ${SHA:0:7}..."
    ELAPSED=0
    RUN_ID=""
    while true; do
        if [ "$ELAPSED" -ge "$CI_TIMEOUT" ]; then
            echo "ERROR: Timed out waiting for CI run to appear after ${ELAPSED}s"
            exit 1
        fi

        RUN_ID=$(gh run list --workflow "$WORKFLOW" --branch master --commit "$SHA" --limit 1 \
            --json databaseId | jq -r '.[0].databaseId // "null"')

        if [ "$RUN_ID" != "null" ] && [ -n "$RUN_ID" ]; then
            break
        fi

        echo "   Waiting for run to appear... (${ELAPSED}s elapsed)"
        sleep "$POLL_INTERVAL"
        ELAPSED=$((ELAPSED + POLL_INTERVAL))
    done

    echo ":: Watching run ${RUN_ID}..."
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
# Captures the HEAD SHA after push and passes it to wait-and-update
# so the correct CI run is tracked regardless of timing.
# Parameters:
#   addon   - add-on directory name (e.g., autoanalyst, claudecode-ea, atomic)
#   message - the git commit message (required)
#   files   - files/dirs to stage (optional, defaults to -A)
# Examples:
#   just pushdeploy autoanalyst "fix(autoanalyst): handle empty tweet bodies"
#   just pushdeploy atomic "feat(atomic): add health check" atomic/
pushdeploy addon message *files:
    just push "{{message}}" {{files}}
    just wait-and-update "{{addon}}" "$(git rev-parse HEAD)"
