# git-bird

A command-line tool that synchronizes your GitHub repositories (for the authenticated user and their organizations) into a structured local directory layout. It reports discrepancies between your local filesystem and GitHub, then can clone missing repos and clean up stale ones.

## What It Does

`git-bird` answers two questions:

1. **What's missing?** Remote repos that exist on GitHub but haven't been cloned locally yet.
2. **What's stale?** Local repo directories that are orphaned, dirty (uncommitted changes), or archived.

It then performs automated actions where safe (cloning missing repos, removing archived ones) and prints manual resolution steps where needed (dirty repos).

## Requirements

- **Python 3.12+**
- **[GitHub CLI (`gh`) installed and authenticated](https://cli.github.com/manual/gh_auth_login)** — the tool uses `gh api` to query your repos. Run `gh auth login` first.
- **`git`** available on `PATH` (for cloning and dirty-state detection).

## Installation

```bash
# Using uv (recommended — project uses uv for dependency management)
uv sync

# Or install directly
pip install .
```

This exposes a `sync` console-script entry point.

## Usage

```bash
# Run a full sync (clones missing repos, removes archived repos)
sync

# Dry-run mode — shows what would happen without making changes
sync --mock
```

Or run via Python directly:

```bash
python -m src.main        # live sync
python -m src.main --mock # dry-run
```

## Local Directory Structure

Repos live in a flat, language-agnostic layout:

```
~/programs/github.com/<owner>/<repoName>/
```

**Example:**

```
~/programs/github.com/pannet1/git-bird/
~/programs/github.com/pannet1/make-videos/
~/programs/github.com/org-name/some-repo/
```

- `<owner>` — the GitHub username or organization name.
- `<repoName>` — the repository name.

## Sync Rules

| Rule | Behavior |
|------|----------|
| **Forks** | Skipped — fork repos are not tracked. |
| **Existing local content** | Never overwritten. If a folder exists at the target path (even without `.git`), it is left alone. |
| **Archived repos** | Listed for removal; in live mode the local directory is deleted (`rm -rf`). |
| **Pending clones** | `git clone` is run into the ideal path, creating parent directories as needed. |

## Report Categories

After scanning, the tool prints a categorized report. Sections with **zero findings are hidden** — only relevant categories appear:

| # | Category | Description |
|---|----------|-------------|
| 1 | **Pending Clones** | Remote repos (active, non-fork) not present locally. |
| 2 | **WIP Folders** | Local directories without `.git` that don't exist on GitHub — new work to be committed. |
| 3 | **Incomplete Repos** | Local directories that exist on GitHub but have no `.git` folder. |
| 4 | **Dirty Repos** | Local git repos with uncommitted changes. |
| 5 | **Orphaned Repos** | Local git repos (with `.git`) that no longer exist on GitHub. |
| 6 | **Deleted Repos** | Local directories whose GitHub repo is archived. |

### Management Advice

A condensed advice section summarizes actions you should take for each non-empty problematic category (WIP, incomplete, dirty, orphaned). If everything is clean, it prints an "all synced" status.

## Mock Mode

`--mock` prints all `git clone` and `rm -rf` commands that would be executed, prefixed with `[MOCK]`, without making any filesystem changes. Use this to preview the sync before running for real.

## How It Works (Internally)

1. **Fetch identity** — gets the authenticated user via `gh api user`.
2. **Enumerate owners** — the user plus all organizations they belong to (`gh api user/orgs`).
3. **List remote repos** — `gh repo list <owner>` for each owner, fetching `name`, `isFork`, `isArchived`.
4. **Map ideal paths** — computes the expected local directory for each remote repo.
5. **Scan local filesystem** — globs `~/programs/github.com/*/*` to discover existing local directories.
6. **Classify** — compares remote and local, categorizing each into one of the report buckets above.
7. **Report & act** — prints the categorized report, then executes safe automated actions (clones, archive removals) in live mode.

## Project Layout

```
git-bird/
├── src/
│   └── main.py      # All logic — sync, report, and action code
├── SPEC.md          # Original specification (high-level objectives & workflow)
├── pyproject.toml   # Project metadata, entry point, and uv config
├── uv.lock          # Locked dependencies
└── README.md        # This file
```

## Limitations

- Only supports GitHub (via `gh CLI`). Not designed for other git hosts.
- Repo listing is limited to 1000 repos per owner via `gh repo list --limit 1000`.
- Dirty-repo handling requires **manual intervention** — the tool reports but does not auto-fix these.
