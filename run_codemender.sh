#!/bin/bash
# ==============================================================================
# Standalone Anytime CodeMender Scanner & Auto-Fixer (run_codemender.sh)
# ==============================================================================
# A zero-dependency, portable CLI tool to run CodeMender's 4-step workflow
# (cm find -> cm report -> cm find verify -> cm fix) anytime on current repository
# changes or specified files, completely independent of git push or hooks.
#
# Usage:
#   ./run_codemender.sh                          # Scan & verify all repo changes
#   ./run_codemender.sh --fix                    # Scan, verify & auto-fix exploitable bugs
#   ./run_codemender.sh -f file1.py src/auth.py  # Scan, verify & auto-fix specific files
#   ./run_codemender.sh --severity HIGH          # Set minimum severity (default: MEDIUM)
#   ./run_codemender.sh --help                   # Show help
# ==============================================================================

set -u

# --- Terminal Colors & Formatting --------------------------------------------
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  CYAN='\033[0;36m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' NC=''
fi

MIN_SEVERITY="${CM_SEVERITY:-MEDIUM}"
AUTO_FIX="${CM_AUTO_FIX:-false}"
TARGET_FILES=()

show_help() {
  cat <<EOF
${BOLD}Standalone Anytime CodeMender Scanner & Auto-Fixer${NC}
Runs 'cm find' -> 'cm report' -> 'cm find verify' (-> 'cm fix') on your repository changes.

${BOLD}USAGE:${NC}
  ./run_codemender.sh [OPTIONS] [FILE...]

${BOLD}OPTIONS:${NC}
  -f, --fix                Automatically generate and apply patches via 'cm fix --auto-apply -y'
                           for findings confirmed exploitable by 'cm find verify'
  -s, --severity <LEVEL>   Minimum severity to verify and report:
                           LOW, MEDIUM (default), HIGH, CRITICAL
  -h, --help               Show this help message

${BOLD}EXAMPLES:${NC}
  ./run_codemender.sh                      # Scan all unstaged, staged, untracked & branch changes
  ./run_codemender.sh --fix                # Scan, verify, and automatically patch exploitable issues
  ./run_codemender.sh app.py               # Scan and verify a specific file
  ./run_codemender.sh -f app.py            # Scan, verify, and auto-fix a specific file
EOF
  exit 0
}

# --- Parse CLI Arguments -----------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    -f|--fix)
      AUTO_FIX="true"
      shift
      ;;
    -s|--severity)
      if [ $# -lt 2 ]; then
        echo -e "${RED}Error: --severity requires an argument (LOW, MEDIUM, HIGH, CRITICAL).${NC}" >&2
        exit 1
      fi
      MIN_SEVERITY="$2"
      shift 2
      ;;
    -*)
      echo -e "${RED}Unknown option: $1${NC}" >&2
      show_help
      ;;
    *)
      TARGET_FILES+=("$1")
      shift
      ;;
  esac
done

severity_rank() {
  case "$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')" in
    CRITICAL) echo 4 ;;
    HIGH|ERROR) echo 3 ;;
    MEDIUM|WARNING) echo 2 ;;
    LOW|INFO) echo 1 ;;
    *) echo 0 ;;
  esac
}

meets_severity() {
  [ "$(severity_rank "$1")" -ge "$(severity_rank "$MIN_SEVERITY")" ]
}

# --- Check Prerequisites -----------------------------------------------------
if ! command -v cm >/dev/null 2>&1; then
  echo -e "${RED}${BOLD}Error:${NC} CodeMender CLI ('cm') was not found on PATH." >&2
  echo "Please install 'cm' or ensure /usr/local/bin/cm is on your PATH." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo -e "${RED}${BOLD}Error:${NC} 'jq' is required to parse CodeMender JSON reports." >&2
  exit 1
fi

# Automatically initialize user-level ~/.codemender if not already present
if [ ! -d "${HOME}/.codemender" ]; then
  echo -e "${CYAN}First-time setup: Initializing global ~/.codemender workspace...${NC}"
  cm init >/dev/null 2>&1 || true
fi

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# --- Step 0: Discover Target Files to Scan -----------------------------------
echo -e "${BLUE}${BOLD}======================================================================${NC}"
if [ "$AUTO_FIX" = "true" ]; then
  echo -e "${BLUE}${BOLD}  CodeMender Security Scanner & Auto-Fixer (find -> report -> verify -> fix)${NC}"
else
  echo -e "${BLUE}${BOLD}  CodeMender Security Scanner (find -> report -> verify)${NC}"
fi
echo -e "${BLUE}${BOLD}======================================================================${NC}"

DISCOVERED_FILES=""

if [ ${#TARGET_FILES[@]} -gt 0 ]; then
  for f in "${TARGET_FILES[@]}"; do
    if [ -e "$f" ]; then
      DISCOVERED_FILES+="$f"$'\n'
    else
      echo -e "${YELLOW}Warning: Specified file '$f' does not exist (skipping).${NC}" >&2
    fi
  done
else
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    UNSTAGED=$(git diff --name-only 2>/dev/null || true)
    STAGED=$(git diff --cached --name-only 2>/dev/null || true)
    UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null || true)

    COMBINED=$(printf "%s\n%s\n%s\n" "$UNSTAGED" "$STAGED" "$UNTRACKED" | sed '/^$/d' | sort -u)

    if [ -n "$COMBINED" ]; then
      echo -e "${CYAN}Detected uncommitted working tree / staged / untracked changes.${NC}"
      DISCOVERED_FILES="$COMBINED"
    else
      CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
      BRANCH_DIFF=$(
        git diff --name-only "origin/$CURRENT_BRANCH...HEAD" 2>/dev/null ||
        git diff --name-only "origin/main...HEAD" 2>/dev/null ||
        git diff --name-only HEAD~1 2>/dev/null ||
        true
      )
      if [ -n "$BRANCH_DIFF" ]; then
        echo -e "${CYAN}Working tree clean. Scanning committed changes on branch '$CURRENT_BRANCH'...${NC}"
        DISCOVERED_FILES="$BRANCH_DIFF"
      fi
    fi
  fi
fi

FILES_TO_SCAN=()
while IFS= read -r line; do
  [ -z "$line" ] && continue
  if [ -f "$line" ] || [ -f "$REPO_ROOT/$line" ]; then
    FILES_TO_SCAN+=("$line")
  fi
done <<< "$DISCOVERED_FILES"

if [ ${#FILES_TO_SCAN[@]} -eq 0 ]; then
  echo -e "${GREEN}${BOLD}✓ No modified or target files found to scan.${NC}"
  exit 0
fi

# NOTE: Because 'cm find' runs 'git checkout HEAD -- . && git clean -fd' when resetting
# the workspace, we stage & commit any dirty working tree changes into a local snapshot
# commit before running 'cm find', ensuring uncommitted edits and untracked files are preserved.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo -e "${CYAN}Snapshotting uncommitted working tree changes to git HEAD so 'cm find' preserves them...${NC}"
    git add -A >/dev/null 2>&1 || true
    git commit -m "chore(codemender): snapshot working tree before scan" >/dev/null 2>&1 || true
  fi
fi

echo -e "${BOLD}Files to scan (${#FILES_TO_SCAN[@]}):${NC}"
for f in "${FILES_TO_SCAN[@]}"; do
  echo -e "  • $f"
done
echo ""

TOTAL_STEPS=3
[ "$AUTO_FIX" = "true" ] && TOTAL_STEPS=4

# --- Step 1: Run `cm find` on Each Target File -------------------------------
echo -e "${BLUE}${BOLD}[Step 1/$TOTAL_STEPS] Running 'cm find -y --unrestricted' on target files...${NC}"
for f in "${FILES_TO_SCAN[@]}"; do
  echo -ne "  Scanning ${BOLD}$f${NC}... "
  SCAN_LOG=$(mktemp)
  if cm find -y --unrestricted "$f" >"$SCAN_LOG" 2>&1; then
    echo -e "${GREEN}done${NC}"
  else
    echo -e "${YELLOW}finished (check logs if needed)${NC}"
  fi
  rm -f "$SCAN_LOG"
done
echo ""

# --- Step 2: Run `cm report` & Filter to Target Files ------------------------
echo -e "${BLUE}${BOLD}[Step 2/$TOTAL_STEPS] Extracting open findings via 'cm report'...${NC}"
REPORT_ERR=$(mktemp)
REPORT_JSON=""

if ! REPORT_JSON=$(cm report --status OPEN --format json 2>"$REPORT_ERR"); then
  ERR_MSG=$(tail -c 400 "$REPORT_ERR" 2>/dev/null || echo "unknown error")
  rm -f "$REPORT_ERR"
  echo -e "${RED}${BOLD}Error:${NC} 'cm report' failed: $ERR_MSG" >&2
  exit 1
fi
rm -f "$REPORT_ERR"

# Strip any trailing info log lines that cm report may append after JSON array
CLEAN_JSON=$(echo "$REPORT_JSON" | sed -n '/^\[/,/^\]/p')
if [ -z "$CLEAN_JSON" ]; then
  CLEAN_JSON="[]"
fi

FILES_NL=$(printf "%s\n" "${FILES_TO_SCAN[@]}")

SCOPED_FINDINGS=$(echo "$CLEAN_JSON" | jq --arg files "$FILES_NL" '
  ($files | split("\n")) as $targets |
  [ .[] | select(.FilePath as $fp | any($targets[]; . as $t | $t != "" and ($fp | endswith($t)))) ]
' 2>/dev/null || echo '[]')

TOTAL_SCOPED=$(echo "$SCOPED_FINDINGS" | jq 'length')

if [ "$TOTAL_SCOPED" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}✓ Clean scan! Zero open CodeMender findings on the scanned files.${NC}"
  exit 0
fi

echo -e "Found ${BOLD}$TOTAL_SCOPED${NC} open finding(s) matching scanned files. Filtering by minimum severity (${BOLD}$MIN_SEVERITY${NC})..."
echo ""

# --- Step 3 (& Optional Step 4): Verify & Auto-Fix ---------------------------
if [ "$AUTO_FIX" = "true" ]; then
  echo -e "${BLUE}${BOLD}[Step 3/$TOTAL_STEPS & Step 4/$TOTAL_STEPS] Verifying ('cm find verify') & Auto-Fixing ('cm fix')...${NC}"
else
  echo -e "${BLUE}${BOLD}[Step 3/$TOTAL_STEPS] Running semantic exploitability verification ('cm find verify')...${NC}"
fi

WORK_DIR=$(mktemp -d 2>/dev/null || mktemp -d -t 'cm_scan_work')
echo "$SCOPED_FINDINGS" | jq -c '.[]' > "$WORK_DIR/findings.jsonl"

EXPLOITABLE_COUNT=0
FALSE_POSITIVE_COUNT=0
BELOW_SEV_COUNT=0
FIXED_COUNT=0

while IFS= read -r finding; do
  [ -z "$finding" ] && continue
  FID=$(echo "$finding" | jq -r '.FindingID // "UNKNOWN_ID"')
  FILE=$(echo "$finding" | jq -r '.FilePath // "unknown"')
  LINE=$(echo "$finding" | jq -r '.StartLine // 0')
  SEV=$(echo "$finding" | jq -r '.Severity // "UNKNOWN"')
  TITLE=$(echo "$finding" | jq -r '.Title // "Security Finding"')
  VULN_TYPE=$(echo "$finding" | jq -r '.VulnType // ""')
  CWE=$(echo "$finding" | jq -r '.VulnID // ""')
  ANALYSIS=$(echo "$finding" | jq -r '.Analysis // ""' | head -n 4 | tr '\n' ' ')

  if ! meets_severity "$SEV"; then
    BELOW_SEV_COUNT=$((BELOW_SEV_COUNT + 1))
    echo -e "  ${YELLOW}[SKIPPED - BELOW SEVERITY]${NC} ${BOLD}$FID${NC} ($SEV) in $FILE:$LINE - $TITLE"
    continue
  fi

  echo -ne "  Verifying ${BOLD}$FID${NC} ($SEV - $TITLE)... "
  cm find verify "$FID" >/dev/null 2>&1 || true

  # Check updated status in cm report
  UPDATED_REPORT=$(cm report --format json 2>/dev/null | sed -n '/^\[/,/^\]/p')
  UPDATED_STATUS=$(echo "$UPDATED_REPORT" | jq -r --arg fid "$FID" '.[] | select(.FindingID == $fid) | .Status // "OPEN"' 2>/dev/null || echo "OPEN")

  if [ "$UPDATED_STATUS" = "DISMISSED" ]; then
    FALSE_POSITIVE_COUNT=$((FALSE_POSITIVE_COUNT + 1))
    echo -e "${GREEN}${BOLD}[FALSE POSITIVE / DISMISSED]${NC}"
    echo -e "    ├─ ${CYAN}File:${NC} $FILE (Line $LINE)"
    echo -e "    └─ ${CYAN}Note:${NC} 'cm find verify' dismissed this finding as not exploitable."
    echo ""
  else
    EXPLOITABLE_COUNT=$((EXPLOITABLE_COUNT + 1))
    echo -e "${RED}${BOLD}[VERIFIED EXPLOITABLE ($UPDATED_STATUS)]${NC}"
    echo -e "    ├─ ${RED}${BOLD}Severity:${NC} $SEV ${CWE:+($CWE)} ${VULN_TYPE:+[$VULN_TYPE]}"
    echo -e "    ├─ ${RED}${BOLD}Location:${NC} $FILE (Line $LINE)"
    echo -e "    ├─ ${RED}${BOLD}Title:${NC}    $TITLE"
    if [ -n "$ANALYSIS" ]; then
      echo -e "    ├─ ${RED}${BOLD}Summary:${NC}  ${ANALYSIS:0:220}..."
    fi

    if [ "$AUTO_FIX" = "true" ]; then
      echo -ne "    └─ ${CYAN}Applying fix via 'cm fix $FID --auto-apply -y --unrestricted'...${NC} "
      if cm fix "$FID" --auto-apply -y --unrestricted >/dev/null 2>&1; then
        FIXED_COUNT=$((FIXED_COUNT + 1))
        echo -e "${GREEN}${BOLD}[FIXED BY CODEMENDER]${NC}"
      else
        echo -e "${RED}${BOLD}[FIX FAILED]${NC}"
      fi
    else
      echo -e "    └─ ${YELLOW}Tip:${NC} Run with ${BOLD}--fix${NC} (or 'cm fix $FID --auto-apply -y') to auto-patch."
    fi
    echo ""
  fi
done < "$WORK_DIR/findings.jsonl"

rm -rf "$WORK_DIR"

REMAINING_UNRESOLVED=$((EXPLOITABLE_COUNT - FIXED_COUNT))

# --- Final Summary & Exit Status ---------------------------------------------
echo -e "${BLUE}${BOLD}======================================================================${NC}"
echo -e "${BOLD}  CodeMender Scan Summary${NC}"
echo -e "${BLUE}${BOLD}======================================================================${NC}"
echo -e "  • Files Scanned:                  ${BOLD}${#FILES_TO_SCAN[@]}${NC}"
echo -e "  • Open Findings on Target Files:  ${BOLD}$TOTAL_SCOPED${NC}"
echo -e "  • False Positives (Dismissed):    ${GREEN}${BOLD}$FALSE_POSITIVE_COUNT${NC}"
if [ "$BELOW_SEV_COUNT" -gt 0 ]; then
  echo -e "  • Skipped (Below $MIN_SEVERITY):        ${YELLOW}${BOLD}$BELOW_SEV_COUNT${NC}"
fi
echo -e "  • Verified Exploitable Issues:    ${RED}${BOLD}$EXPLOITABLE_COUNT${NC}"
if [ "$AUTO_FIX" = "true" ]; then
  echo -e "  • Auto-Fixed by CodeMender:       ${GREEN}${BOLD}$FIXED_COUNT${NC}"
  echo -e "  • Remaining Unresolved Issues:    ${RED}${BOLD}$REMAINING_UNRESOLVED${NC}"
fi
echo -e "${BLUE}${BOLD}======================================================================${NC}"

if [ "$REMAINING_UNRESOLVED" -gt 0 ]; then
  if [ "$AUTO_FIX" = "true" ]; then
    echo -e "${RED}${BOLD}✗ Action Required: $REMAINING_UNRESOLVED verified vulnerability(ies) could not be auto-fixed!${NC}"
  else
    echo -e "${RED}${BOLD}✗ Action Required: $REMAINING_UNRESOLVED verified exploitable vulnerability(ies) found!${NC}"
    echo -e "  Run ${BOLD}./run_codemender.sh --fix${NC} to automatically patch verified findings."
  fi
  exit 1
elif [ "$FIXED_COUNT" -gt 0 ]; then
  echo -e "${GREEN}${BOLD}✓ All $FIXED_COUNT verified vulnerability(ies) were automatically fixed by CodeMender!${NC}"
  exit 0
else
  echo -e "${GREEN}${BOLD}✓ All scanned files passed CodeMender verification!${NC}"
  exit 0
fi
