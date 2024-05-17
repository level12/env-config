set -gx ENV_CONFIG_SHELL fish

function env-config
    # Call the env-config bin which should be on the path with all arguments passed to this function
    # Use split0 as a hack to get the output read as a string and not a variable array
    set stdout (command env-config $argv | string split0)
    if string match -q '# FISH SOURCE*' $stdout
        echo $stdout | source
        echo ''
        echo 'Fish: sourced env-config commands from stdout'
    else
        echo -n $stdout
    end
end
