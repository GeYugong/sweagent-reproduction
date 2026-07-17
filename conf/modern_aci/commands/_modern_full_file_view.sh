_print() {
    local total_lines
    total_lines=$(awk 'END {print NR}' "$CURRENT_FILE")
    echo "[File: $(realpath "$CURRENT_FILE") ($total_lines lines total; full-file view)]"
    grep -n '^' "$CURRENT_FILE"
}
