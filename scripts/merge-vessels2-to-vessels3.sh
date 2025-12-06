#!/bin/bash
# Merge branches from ohana-garden/vessels2 into ohana-garden/vessels3
# This script provides an idempotent, safe way to merge all branches from vessels2
# into a single branch in vessels3 for review and integration.
#
# Usage:
#   ./merge-vessels2-to-vessels3.sh [--squash] [--branch-name <name>]
#
# Options:
#   --squash         Use squash merges instead of regular merge commits
#   --branch-name    Specify a custom branch name (default: v2-merged-<timestamp>)

set -e  # Exit on error

# Default configuration
SOURCE_REPO="https://github.com/ohana-garden/vessels2.git"
SOURCE_REMOTE_NAME="vessels2"
TARGET_REPO="https://github.com/ohana-garden/vessels3.git"
MERGE_STRATEGY="merge"  # Can be "merge" or "squash"
BRANCH_NAME=""
DEFAULT_BRANCH="claude/docker-falkordb-setup-01WJZfwXzj8JKfrWTVfZ87rc"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --squash)
            MERGE_STRATEGY="squash"
            shift
            ;;
        --branch-name)
            BRANCH_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--squash] [--branch-name <name>]"
            echo ""
            echo "Options:"
            echo "  --squash         Use squash merges instead of regular merge commits"
            echo "  --branch-name    Specify a custom branch name (default: v2-merged-<timestamp>)"
            echo ""
            echo "This script clones vessels3, adds vessels2 as a remote, creates a new branch,"
            echo "and merges every branch from vessels2 into that branch one-by-one."
            echo "The script is idempotent and will stop on conflicts with clear instructions."
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set default branch name if not provided
if [ -z "$BRANCH_NAME" ]; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    BRANCH_NAME="v2-merged-${TIMESTAMP}"
fi

TARGET_BRANCH="$BRANCH_NAME"

log_info "=== Merge vessels2 to vessels3 ==="
log_info "Merge strategy: $MERGE_STRATEGY"
log_info "Target branch: $TARGET_BRANCH"
echo ""

# Step 1: Check if we're already in a vessels3 repository
log_step "Step 1: Checking repository status..."
if [ -d ".git" ]; then
    CURRENT_REPO=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$CURRENT_REPO" == *"vessels3"* ]]; then
        log_info "Already in vessels3 repository: $PWD"
        REPO_DIR="$PWD"
    else
        log_error "Current directory is a git repository but not vessels3"
        log_error "Please run this script from outside a git repository or from vessels3"
        exit 1
    fi
else
    # Clone vessels3 if not in a repository
    log_step "Step 1: Cloning vessels3 repository..."
    REPO_DIR="vessels3-merge-$(date +%Y%m%d-%H%M%S)"
    git clone "$TARGET_REPO" "$REPO_DIR"
    cd "$REPO_DIR"
    log_info "Cloned vessels3 to $REPO_DIR"
fi

# Step 2: Add vessels2 as a remote (idempotent)
log_step "Step 2: Adding vessels2 as remote..."
if git remote | grep -q "^${SOURCE_REMOTE_NAME}$"; then
    log_info "Remote '$SOURCE_REMOTE_NAME' already exists, updating..."
    git remote set-url "$SOURCE_REMOTE_NAME" "$SOURCE_REPO"
else
    log_info "Adding remote '$SOURCE_REMOTE_NAME'..."
    git remote add "$SOURCE_REMOTE_NAME" "$SOURCE_REPO"
fi

# Fetch all branches from vessels2
log_info "Fetching branches from vessels2..."
git fetch "$SOURCE_REMOTE_NAME"
log_info "Fetch complete"

# Step 3: Check if target branch already exists
log_step "Step 3: Setting up target branch..."
if git rev-parse --verify "$TARGET_BRANCH" >/dev/null 2>&1; then
    log_info "Branch '$TARGET_BRANCH' already exists, checking it out..."
    git checkout "$TARGET_BRANCH"
    log_info "Continuing from existing state (idempotent)"
else
    log_info "Creating new branch '$TARGET_BRANCH' from '$DEFAULT_BRANCH'..."
    git checkout -b "$TARGET_BRANCH" "$DEFAULT_BRANCH"
    log_info "Created branch '$TARGET_BRANCH'"
fi

# Step 4: Get list of branches from vessels2
log_step "Step 4: Getting list of branches from vessels2..."
VESSELS2_BRANCHES=$(git branch -r | grep "^  $SOURCE_REMOTE_NAME/" | sed "s|^  $SOURCE_REMOTE_NAME/||" | grep -v "HEAD")

if [ -z "$VESSELS2_BRANCHES" ]; then
    log_error "No branches found in $SOURCE_REMOTE_NAME remote"
    exit 1
fi

BRANCH_COUNT=$(echo "$VESSELS2_BRANCHES" | wc -l)
log_info "Found $BRANCH_COUNT branches to merge:"
echo "$VESSELS2_BRANCHES" | sed 's/^/  - /'
echo ""

# Step 5: Merge each branch one by one
log_step "Step 5: Merging branches..."
CURRENT_BRANCH_NUM=0

for branch in $VESSELS2_BRANCHES; do
    CURRENT_BRANCH_NUM=$((CURRENT_BRANCH_NUM + 1))
    log_info "[$CURRENT_BRANCH_NUM/$BRANCH_COUNT] Processing branch: $branch"
    
    # Check if this branch was already merged
    MERGE_BASE=$(git merge-base HEAD "remotes/$SOURCE_REMOTE_NAME/$branch" 2>/dev/null || echo "")
    HEAD_COMMIT=$(git rev-parse HEAD)
    BRANCH_COMMIT=$(git rev-parse "remotes/$SOURCE_REMOTE_NAME/$branch")
    
    # Check if branch is already merged (HEAD contains all commits from branch)
    if git merge-base --is-ancestor "remotes/$SOURCE_REMOTE_NAME/$branch" HEAD 2>/dev/null; then
        log_info "Branch '$branch' already merged, skipping..."
        continue
    fi
    
    # Perform the merge
    if [ "$MERGE_STRATEGY" = "merge" ]; then
        # Regular merge with history preservation
        log_info "Merging $branch with history..."
        git merge --no-edit --allow-unrelated-histories "remotes/$SOURCE_REMOTE_NAME/$branch" -m "Merge $SOURCE_REMOTE_NAME/$branch into $TARGET_BRANCH" || {
            log_error "Merge conflict detected while merging $branch!"
            echo ""
            log_warn "To resolve conflicts:"
            echo "  1. Fix conflicts in the affected files"
            echo "  2. Stage the resolved files: git add <files>"
            echo "  3. Complete the merge: git commit"
            echo "  4. Re-run this script (it will pick up from current state)"
            echo ""
            exit 2
        }
    else
        # Squash merge
        log_info "Squash merging $branch..."
        git merge --squash --allow-unrelated-histories "remotes/$SOURCE_REMOTE_NAME/$branch" || {
            log_error "Squash merge conflict detected while merging $branch!"
            echo ""
            log_warn "To resolve conflicts:"
            echo "  1. Fix conflicts in the affected files"
            echo "  2. Stage the resolved files: git add <files>"
            echo "  3. Complete the merge: git commit -m \"Squash merge $SOURCE_REMOTE_NAME/$branch\""
            echo "  4. Re-run this script (it will pick up from current state)"
            echo ""
            exit 2
        }
        git commit -m "Squash merge $SOURCE_REMOTE_NAME/$branch into $TARGET_BRANCH"
    fi
    
    log_info "Successfully merged $branch"
done

echo ""
log_info "=== All merges completed successfully! ==="
echo ""
log_info "Next steps:"
echo "  1. Review the merged changes:"
echo "     git log --oneline --graph --decorate $TARGET_BRANCH"
echo ""
echo "  2. Push the branch to origin:"
echo "     git push origin $TARGET_BRANCH"
echo ""
echo "  3. Open a Pull Request on GitHub:"
echo "     - From: $TARGET_BRANCH"
echo "     - Into: $DEFAULT_BRANCH"
echo "     - For review and integration"
echo ""
log_info "Branch '$TARGET_BRANCH' is ready for review!"
