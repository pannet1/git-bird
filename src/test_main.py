import os
import tempfile
import shutil
from pathlib import Path
try:
    from main import is_version_controlled, get_repo_path
except ImportError:
    from src.main import is_version_controlled, get_repo_path

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

if __name__ == "__main__":
    test_is_version_controlled()
    test_get_repo_path()
    print("\nAll tests passed!")
