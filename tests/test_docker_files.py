# tests/test_docker_files.py
# Checks the Docker setup can't leak secrets or break the app. Run from the fx-hedging root:
#   python -m unittest discover tests -v
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestDockerFiles(unittest.TestCase):
    def setUp(self):
        if not (ROOT / "Dockerfile").exists():
            self.skipTest("Dockerfile not present (e.g. inside the image, where it's excluded)")
        self.dockerfile = (ROOT / "Dockerfile").read_text()
        self.ignore = (ROOT / ".dockerignore").read_text().splitlines()

    def test_secrets_and_venv_are_excluded(self):
        for entry in [".env", "venv/", ".git/"]:
            self.assertIn(entry, self.ignore)

    def test_key_is_not_baked_in(self):
        for line in self.dockerfile.splitlines():
            if line.strip().startswith(("ENV", "ARG")) or line.startswith("    "):
                self.assertNotIn("CHAT_API_KEY", line)

    def test_data_the_app_needs_is_not_excluded(self):
        for needed in ["data/", "outputs/", "models/", "README.md"]:
            self.assertFalse(any(line.strip() == needed for line in self.ignore), needed)

    def test_runs_as_non_root_on_8501(self):
        self.assertIn("USER appuser", self.dockerfile)
        self.assertIn("EXPOSE 8501", self.dockerfile)


if __name__ == "__main__":
    unittest.main()
