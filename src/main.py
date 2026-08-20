import os
import re
import json
import subprocess
from pathlib import Path

def sanitize_lang(lang):
    if not lang or lang == 'unknown':
        return 'unknown'
    return re.sub(r'[^a-z0-9]+', '-', lang.lower())

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
    output = run_command(f'gh repo list {owner} --limit 1000 --json name,primaryLanguage,isFork,isArchived')
    return json.loads(output) if output else []

def get_repo_path(repo, owner):
    lang = repo.get('primaryLanguage')
    if isinstance(lang, dict):
        lang = lang.get('name')
    lang_dir = sanitize_lang(lang)
    return Path.home() / "programs" / lang_dir / "github.com" / owner / repo['name']

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

    # Find all existing local directories in the structure: programs/<lang>/github.com/<owner>/<repo>
    local_structure = {}
    if local_root.exists():
        for path in local_root.glob("*/github.com/*/*"):
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
    duplicate_names = []  # Repos with same name in different language folders
    dirty_local = []  # Repos with uncommitted changes

    # Build a map of repo names (just name, not owner) to existing paths
    # This helps detect duplicates across languages
    repo_name_to_paths = {}
    for owner_repo, paths in local_structure.items():
        repo_name = owner_repo.split('/')[-1]  # Just the repo name
        if repo_name not in repo_name_to_paths:
            repo_name_to_paths[repo_name] = []
        repo_name_to_paths[repo_name].extend(paths)

    # Identify pending clones
    for owner_repo, data in remote_repos_map.items():
        if data['repo'].get('isArchived'):
            continue
        repo_name = data['repo']['name']
        ideal_path = str(data['ideal_path'])
        # Check if this repo name already exists in another language folder
        if repo_name in repo_name_to_paths:
            existing_paths = repo_name_to_paths[repo_name]
            existing_path_strs = [str(p) for p in existing_paths]
            # Get the language folder from ideal_path (e.g., 'python' from /home/.../programs/python/...)
            ideal_lang_folder = Path(ideal_path).parts[-4]  # .../programs/<lang>/github.com/...
            # Check if any existing path is in a DIFFERENT language folder
            different_lang_paths = [p for p in existing_path_strs if Path(p).parts[-4] != ideal_lang_folder]
            if different_lang_paths:
                duplicate_names.append({
                    'repo': data['repo'],
                    'ideal_path': ideal_path,
                    'existing_paths': different_lang_paths  # Only show the paths in different language folders
                })
                continue
        if owner_repo not in local_structure:
            pending_clones.append((data['repo'], str(data['ideal_path'])))
        else:
            # It exists locally, check if any of the instances are version controlled
            exists_as_repo = any(is_version_controlled(p) for p in local_structure[owner_repo])
            if not exists_as_repo:
                # If it exists but NONE are repos, it might be a WIP or we might want to clone
                # But the user said "Never overwrite existing local content"
                # and "local folders not in version control" are WIP.
                # So we skip cloning if the folder exists.
                pass

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
         lambda repo, path: f"   - {repo['owner']}/{repo['name']} -> {path}"),
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
        ("Duplicate Repo Names", "exist in different language folder", duplicate_names,
         lambda dup: (f"   - {dup['repo']['owner']}/{dup['repo']['name']} (would be: {dup['ideal_path']})"
                      + f"\n     Already exists: {dup['existing_paths']}")),
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
    if duplicate_names:
        print("* Duplicate Names: Repos with same name exist in different language folders.")
        print("  Review and resolve manually - consider merging or deleting duplicates.")
    if not pending_clones and not duplicate_names:
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

    if duplicate_names:
        print("\n" + "="*50)
        print("DUPLICATE RESOLUTION NEEDED")
        print("="*50)
        for dup in duplicate_names:
            repo = dup['repo']
            lang_data = repo.get('primaryLanguage')
            lang = lang_data.get('name', 'unknown') if isinstance(lang_data, dict) else 'unknown'
            ideal_path = dup['ideal_path']
            ideal_lang = Path(ideal_path).parts[-4]
            print(f"\nRepo: {repo['owner']}/{repo['name']}")
            print(f"  GitHub primary language: {lang}")
            print(f"  Correct folder (based on GitHub): programs/{ideal_lang}/github.com/{repo['owner']}/{repo['name']}")
            print(f"  WRONG folder (needs to be moved):")
            for p in dup['existing_paths']:
                p_lang = Path(p).parts[-4]
                print(f"    - {p} (language: {p_lang})")
                parent = str(Path(ideal_path).parent)
                print(f"      mkdir -p {parent} && mv {p} {ideal_path}")
            print(f"\n  Action: Move the WRONG folder to the correct location, then re-run sync.")
        print("\n" + "="*50)

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