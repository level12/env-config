export ENV_CONFIG_SHELL=bash

env-config() {
    local stdout
    stdout=$(command env-config "$@")

    if echo "$stdout" | grep -q "# BASH SOURCE"; then
        eval "$stdout"
        echo ''
        echo 'Bash: sourced env-config commands from stdout'
    else
        echo -n "$stdout"
        echo ''
        echo 'Did not source commands'
    fi
}
