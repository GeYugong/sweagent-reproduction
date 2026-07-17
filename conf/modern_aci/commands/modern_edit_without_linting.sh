# @yaml
# signature: |-
#   edit <start_line>:<end_line>
#   <replacement_text>
#   end_of_edit
# docstring: replaces lines <start_line> through <end_line> (inclusive) with the given text in the open file. The replacement text is terminated by a line with only end_of_edit on it. This reconstructed variant applies the edit directly and does not run the linting guardrail.
# end_name: end_of_edit
# arguments:
#   start_line:
#     type: integer
#     description: the line number to start the edit at
#     required: true
#   end_line:
#     type: integer
#     description: the line number to end the edit at (inclusive)
#     required: true
#   replacement_text:
#     type: string
#     description: the text to replace the current selection with
#     required: true
edit() {
    if [ -z "$CURRENT_FILE" ]; then
        echo 'No file open. Use the `open` command first.'
        return
    fi

    local start_line="$(echo "$1:" | cut -d: -f1)"
    local end_line="$(echo "$1:" | cut -d: -f2)"
    if [ -z "$start_line" ] || [ -z "$end_line" ]; then
        echo "Usage: edit <start_line>:<end_line>"
        return
    fi

    local re='^[0-9]+$'
    if ! [[ $start_line =~ $re ]]; then
        echo "Usage: edit <start_line>:<end_line>"
        echo "Error: start_line must be a number"
        return
    fi
    if ! [[ $end_line =~ $re ]]; then
        echo "Usage: edit <start_line>:<end_line>"
        echo "Error: end_line must be a number"
        return
    fi
    local zero_based_start=$((start_line - 1))
    local replacement=()
    while IFS= read -r line; do
        replacement+=("$line")
    done

    mapfile -t lines < "$CURRENT_FILE"
    local new_lines=(
        "${lines[@]:0:$zero_based_start}"
        "${replacement[@]}"
        "${lines[@]:$end_line}"
    )
    printf "%s\n" "${new_lines[@]}" >| "$CURRENT_FILE"

    export CURRENT_LINE="$start_line"
    _constrain_line
    _print
    echo "File updated without linting. Please review the applied changes."
}
