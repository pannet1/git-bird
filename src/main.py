import os
import json
import subprocess
from pathlib import Path

def is_version_controlled(path):
    git_dir = os.path.join(path, ".git")
    return os.path.isdir(git_dir)

def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()

def get_user():
    return run_command('gh api user --jq ".login"')

def get_orgs():
    output = run_command('gh api user/orgs --jq ".[].login"')
    return output.splitlines() if output else []

def get_repos(owner):
    output = run_command(f'gh repo list {owner} --limit 1000 --json name,isFork,isArchived')
    return json.loads(output) if output else []

def get_repo_path(repo, owner):
    return Path.home() / "programs" / "github.com" / owner / repo['name']

def sync(mock=False):
    user = get_user()
    if not user:
        print("Error: Could not get authenticated user. Please run 'gh auth login'.")
        return

    owners = [user] + get_orgs()
    remote_repos = []
    for owner in owners:
        repos = get_repos(owner)
        for r in repos:
            r['owner'] = owner
            remote_repos.append(r)

    # Filter out forks
    remote_repos = [r for r in remote_repos if not r.get('isFork')]

    local_root = Path.home() / "programs"

    # Map remote repos to their "ideal" paths
    remote_repos_map = {}
    for repo in remote_repos:
        ideal_path = get_repo_path(repo, repo['owner'])
        remote_repos_map[f"{repo['owner']}/{repo['name']}"] = {
            'repo': repo,
            'ideal_path': ideal_path
        }

    # Find all existing local directories in the structure: programs/github.com/<owner>/<repo>
    local_structure = {}
    if local_root.exists():
        for path in local_root.glob("github.com/*/*"):
            if path.is_dir():
                parts = path.parts
                owner_repo = f"{parts[-2]}/{parts[-1]}"
                if owner_repo not in local_structure:
                    local_structure[owner_repo] = []
                local_structure[owner_repo].append(path)

    # Scan home folder for .git repos outside ~/programs/
    pending_clones = []
    orphaned_local = []
    no_git_local = []
    incomplete_local = []
    archived_local = []
    dirty_local = []  # Repos with uncommitted changes

    # Identify pending clones
    for owner_repo, data in remote_repos_map.items():
        if data['repo'].get('isArchived'):
            continue
        if owner_repo not in local_structure:
            pending_clones.append((data['repo'], str(data['ideal_path'])))

    # Categorize local directories
    for owner_repo, paths in local_structure.items():
        for path in paths:
            is_repo = is_version_controlled(path)
            is_dirty = False
            if is_repo:
                # Check for uncommitted changes
                result = subprocess.run(['git', 'diff', '--quiet'], cwd=path, capture_output=True)
                is_dirty = result.returncode != 0
            in_remote = owner_repo in remote_repos_map

            if in_remote and remote_repos_map[owner_repo]['repo'].get('isArchived'):
                archived_local.append(str(path))
                continue

            if not is_repo:
                if not in_remote:
                    # Local folder without .git and not on GitHub
                    no_git_local.append(str(path))
                else:
                    # Local folder without .git but is on GitHub
                    incomplete_local.append(str(path))
            else:
                # It is a repo (has .git)
                if is_dirty:
                    dirty_local.append(str(path))
                elif not in_remote:
                    # Local folder with .git but not on GitHub
                    orphaned_local.append(str(path))

    # Report
    sections = [
        ("Pending Clones", "Remote repos not present locally", pending_clones,
         lambda item: f"   - {item[0]['owner']}/{item[0]['name']} -> {item[1]}"),
        ("WIP Folders", "Local folders not on GitHub & no .git", no_git_local,
         lambda path: f"   - {path}"),
        ("Incomplete Repos", "Local folders on GitHub but no .git", incomplete_local,
         lambda path: f"   - {path}"),
        ("Dirty Repos", "Local repos with uncommitted changes", dirty_local,
         lambda path: f"   - {path}"),
        ("Orphaned Repos", "Local repos not on GitHub", orphaned_local,
         lambda path: f"   - {path}"),
        ("Deleted Repos", "Archived on GitHub", archived_local,
         lambda path: f"   - {path}"),
    ]

    for idx, (title, subtitle, items, fmt) in enumerate(sections, 1):
        if not items:
            continue
        print(f"{idx}. {title} ({subtitle}): {len(items)}")
        for item in items:
            print(fmt(item))

    print("\n" + "="*50)
    print("MANAGEMENT ADVICE")
    print("="*50)
    if no_git_local:
        print("* WIP Folders: Initialize with 'git init' and push to GitHub to backup new work.")
    if incomplete_local:
        print("* Incomplete Repos: Missing '.git'. Consider re-cloning if these should match GitHub.")
    if dirty_local:
        print("* Dirty Repos: Have uncommitted changes. Consider committing or stashing changes.")
    if orphaned_local:
        print("* Orphaned Repos: Exist locally with '.git' but not on GitHub. Verify or push.")
    if not pending_clones:
        print("* Status: All remote repositories are currently synced locally.")
    print("="*50)

    # Execution
    if archived_local:
        for path in archived_local:
            cmd = f"rm -rf {path}"
            if mock:
                print(f"[MOCK] {cmd} (Archived on GitHub)")
            else:
                print(f"Removing archived repo: {path}...")
                subprocess.run(cmd, shell=True)

    if pending_clones:
        print("\nActions:")
        for repo, path in pending_clones:
            clone_url = f"https://github.com/{repo['owner']}/{repo['name']}.git"
            cmd = f"git clone {clone_url} {path}"
            if mock:
                print(f"[MOCK] {cmd}")
            else:
                print(f"Cloning {repo['owner']}/{repo['name']}...")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                subprocess.run(cmd, shell=True)

if __name__ == "__main__":
    import sys
    mock_mode = "--mock" in sys.argv
    sync(mock=mock_mode)
