# SPEC.md

## Objective
Sync GitHub repositories for the authenticated user and their organizations to a structured local directory.

## Workflow
1. **Get Authenticated User**: Fetch username via `gh api user --jq ".login"` or fallback to API.
2. **Get Organizations**: List orgs the user belongs to via `gh api users/<user>/orgs --jq ".[].login"`.
3. **List Repositories**:
   - For user: `gh repo list <user> --limit 1000 --json name,isFork,isArchived`
   - For each org: `gh repo list <org> --limit 1000 --json name,isFork,isArchived`
4. **Local Path Structure**: `~/programs/<gitDomain>/<owner>/<repoName>/`
   - Example: `~/programs/github.com/pannet1/Scripts`
   - `<gitDomain>`: Fixed as `github.com`
   - `<owner>`: User or organization name
5. **Sync Rules**:
   - Ignore forked remote repos (skip forks)
   - Ignore local-only files (only consider directories as repos)
   - Clone remote repos missing locally to the target path (not just create folders)
   - Never overwrite existing local content
   - Skip existing local repos (no updates)
   - Use `git clone https://github.com/<owner>/<repo>.git` for cloning
6. **Difference Report**:
   - Remote repos not present locally (pending clone)
   - Local repos not present remotely (orphaned, directories only)
7. **Mock Mode**:
   - Print what would be done without actually cloning
   - Show `git clone` commands that would be executed
