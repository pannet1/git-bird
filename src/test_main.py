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

def test_sync_does_not_clone_or_delete():
    with patch.object(main, "get_user", return_value="user1"), \
         patch.object(main, "get_orgs", return_value=[]), \
         patch.object(main, "get_repos", return_value=[
             {"name": "missing-repo", "isFork": False, "isArchived": False},
             {"name": "archived-repo", "isFork": False, "isArchived": True},
         ]), \
         patch("subprocess.run") as mock_subproc, \
         patch("os.makedirs") as mock_makedirs:

        # Even with mock=False (live mode), it should NOT run clone or rm -rf
        sync(mock=False)

        # Check all subprocess calls
        for call_args in mock_subproc.call_args_list:
            cmd = call_args[0][0] if call_args[0] else ""
            if isinstance(cmd, list):
                cmd_str = " ".join(cmd)
            else:
                cmd_str = str(cmd)
            assert "git clone" not in cmd_str, f"Unexpected clone executed: {cmd_str}"
            assert "rm -rf" not in cmd_str, f"Unexpected deletion executed: {cmd_str}"

        # Check os.makedirs was not called for missing repos
        assert mock_makedirs.call_count == 0, "os.makedirs should not be called to create clone destinations"

    print("PASS: test_sync_does_not_clone_or_delete")

if __name__ == "__main__":
    test_is_version_controlled()
    test_get_repo_path()
    test_sync_does_not_clone_or_delete()
    print("\nAll tests passed!")
