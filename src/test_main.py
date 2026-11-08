import os
import tempfile
import shutil
from pathlib import Path
try:
    from main import is_version_controlled, get_repo_path, sync
    import main
except ImportError:
    from src.main import is_version_controlled, get_repo_path, sync
    import src.main as main
from unittest.mock import patch

def test_is_version_controlled():
    tmp = tempfile.mkdtemp()
    try:
        real = os.path.join(tmp, "real-repo")
        os.makedirs(os.path.join(real, ".git"))
        assert is_version_controlled(real) == True

        mock = os.path.join(tmp, "mock-repo")
        os.makedirs(mock)
        assert is_version_controlled(mock) == False
    finally:
        shutil.rmtree(tmp)
    print("PASS: test_is_version_controlled")

def test_get_repo_path():
    repo = {'name': 'test-repo'}
    owner = 'user1'
    path = get_repo_path(repo, owner)
    expected = Path.home() / "programs" / "github.com" / "user1" / "test-repo"
    assert path == expected

    print("PASS: test_get_repo_path")

def test_sync_execution():
    with patch.object(main, "get_user", return_value="user1"), \
         patch.object(main, "get_orgs", return_value=[]), \
         patch.object(main, "get_repos", return_value=[
             {"name": "missing-repo", "isFork": False, "isArchived": False},
         ]), \
         patch("subprocess.run") as mock_subproc, \
         patch("os.makedirs") as mock_makedirs:

        # Test mock mode - no clone or rm commands
        sync(mock=True)
        assert not any("git clone" in str(c) for c in mock_subproc.call_args_list)
        assert not any("rm -rf" in str(c) for c in mock_subproc.call_args_list)
        assert mock_makedirs.call_count == 0

        # Test live mode
        sync(mock=False)
        assert mock_makedirs.call_count == 1
        assert any("git clone" in str(c) for c in mock_subproc.call_args_list)

    print("PASS: test_sync_execution")

def test_sync_includes_local_owners():
    queried_owners = []
    def fake_get_repos(owner):
        queried_owners.append(owner)
        return []

    with patch.object(main, "get_user", return_value="pannet1"), \
         patch.object(main, "get_orgs", return_value=["test-org"]), \
         patch.object(main, "get_repos", side_effect=fake_get_repos):

        sync(mock=True)

        assert "pannet1" in queried_owners
        assert "test-org" in queried_owners
        # ecomsense exists locally in ~/programs/github.com/
        assert "ecomsense" in queried_owners

    print("PASS: test_sync_includes_local_owners")

if __name__ == "__main__":
    test_is_version_controlled()
    test_get_repo_path()
    test_sync_execution()
    test_sync_includes_local_owners()
    print("\nAll tests passed!")
