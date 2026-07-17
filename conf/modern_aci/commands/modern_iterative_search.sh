_show_search_result() {
    local result_count=${#SEARCH_RESULTS[@]}
    if [ "$result_count" -eq 0 ]; then
        echo "No active search results. Run search_dir or search_file first."
        return
    fi

    local result_file="${SEARCH_FILES[$SEARCH_INDEX]}"
    local result_line="${SEARCH_RESULTS[$SEARCH_INDEX]}"
    local original_window="$WINDOW"
    export CURRENT_FILE="$result_file"
    export CURRENT_LINE="$result_line"
    export WINDOW=11
    _constrain_line
    echo "[Search result $((SEARCH_INDEX + 1))/$result_count]"
    _print
    export WINDOW="$original_window"
}

# @yaml
# signature: search_dir <search_term> [<dir>]
# docstring: searches for search_term in all files in dir and opens the first match with five surrounding lines on each side. Use next and prev to navigate the reconstructed iterative result list.
# arguments:
#   search_term:
#     type: string
#     description: the term to search for
#     required: true
#   dir:
#     type: string
#     description: the directory to search in (if not provided, searches in the current directory)
#     required: false
search_dir() {
    local search_term
    local dir
    if [ $# -eq 1 ]; then
        search_term="$1"
        dir="./"
    elif [ $# -eq 2 ]; then
        search_term="$1"
        if [ -d "$2" ]; then
            dir="$2"
        else
            echo "Directory $2 not found"
            return
        fi
    else
        echo "Usage: search_dir <search_term> [<dir>]"
        return
    fi

    dir=$(realpath "$dir")
    SEARCH_RESULTS=()
    SEARCH_FILES=()
    while IFS=: read -r file line_number _; do
        if [ -n "$file" ] && [[ $line_number =~ ^[0-9]+$ ]]; then
            SEARCH_FILES+=("$(realpath "$file")")
            SEARCH_RESULTS+=("$line_number")
        fi
    done < <(
        find "$dir" -type f ! -path '*/.*' \
            -exec grep -nIH -- "$search_term" {} + 2>/dev/null \
            | sort -t: -k1,1 -k2,2n
    )
    SEARCH_INDEX=0
    if [ "${#SEARCH_RESULTS[@]}" -eq 0 ]; then
        echo "No matches found for \"$search_term\" in $dir"
        return
    fi
    echo "Found ${#SEARCH_RESULTS[@]} iterative matches for \"$search_term\" in $dir."
    _show_search_result
}

# @yaml
# signature: search_file <search_term> [<file>]
# docstring: searches for search_term in a file and opens the first match with five surrounding lines on each side. Use next and prev to navigate the reconstructed iterative result list.
# arguments:
#   search_term:
#     type: string
#     description: the term to search for
#     required: true
#   file:
#     type: string
#     description: the file to search in (if not provided, searches in the current open file)
#     required: false
search_file() {
    if [ -z "${1:-}" ]; then
        echo "Usage: search_file <search_term> [<file>]"
        return
    fi

    local search_term="$1"
    local file
    if [ -n "${2:-}" ]; then
        if [ -f "$2" ]; then
            file="$2"
        else
            echo "Error: File name $2 not found."
            return
        fi
    elif [ -n "$CURRENT_FILE" ] && [ -f "$CURRENT_FILE" ]; then
        file="$CURRENT_FILE"
    else
        echo "No file open. Use the open command first."
        return
    fi

    file=$(realpath "$file")
    SEARCH_RESULTS=()
    SEARCH_FILES=()
    while IFS=: read -r _ line_number _; do
        if [[ $line_number =~ ^[0-9]+$ ]]; then
            SEARCH_FILES+=("$file")
            SEARCH_RESULTS+=("$line_number")
        fi
    done < <(grep -nH -- "$search_term" "$file" 2>/dev/null | sort -t: -k2,2n)
    SEARCH_INDEX=0
    if [ "${#SEARCH_RESULTS[@]}" -eq 0 ]; then
        echo "No matches found for \"$search_term\" in $file"
        return
    fi
    echo "Found ${#SEARCH_RESULTS[@]} iterative matches for \"$search_term\" in $file."
    _show_search_result
}

# @yaml
# signature: find_file <file_name> [<dir>]
# docstring: finds all files with the given name in dir. If dir is not provided, searches in the current directory
# arguments:
#   file_name:
#     type: string
#     description: the name of the file to search for
#     required: true
#   dir:
#     type: string
#     description: the directory to search in (if not provided, searches in the current directory)
#     required: false
find_file() {
    local file_name
    local dir
    if [ $# -eq 1 ]; then
        file_name="$1"
        dir="./"
    elif [ $# -eq 2 ]; then
        file_name="$1"
        if [ -d "$2" ]; then
            dir="$2"
        else
            echo "Directory $2 not found"
            return
        fi
    else
        echo "Usage: find_file <file_name> [<dir>]"
        return
    fi

    dir=$(realpath "$dir")
    local matches
    matches=$(find "$dir" -type f -name "$file_name")
    if [ -z "$matches" ]; then
        echo "No matches found for \"$file_name\" in $dir"
        return
    fi
    local num_matches
    num_matches=$(echo "$matches" | wc -l | awk '{$1=$1; print $0}')
    echo "Found $num_matches matches for \"$file_name\" in $dir:"
    echo "$matches"
}

# @yaml
# signature: next
# docstring: opens the next result from the active iterative search
next() {
    local result_count=${#SEARCH_RESULTS[@]}
    if [ "$result_count" -eq 0 ]; then
        echo "No active search results. Run search_dir or search_file first."
        return
    fi
    if [ "$SEARCH_INDEX" -ge $((result_count - 1)) ]; then
        echo "Already at the last search result."
    else
        SEARCH_INDEX=$((SEARCH_INDEX + 1))
    fi
    _show_search_result
}

# @yaml
# signature: prev
# docstring: opens the previous result from the active iterative search
prev() {
    if [ "${#SEARCH_RESULTS[@]}" -eq 0 ]; then
        echo "No active search results. Run search_dir or search_file first."
        return
    fi
    if [ "$SEARCH_INDEX" -le 0 ]; then
        echo "Already at the first search result."
    else
        SEARCH_INDEX=$((SEARCH_INDEX - 1))
    fi
    _show_search_result
}
