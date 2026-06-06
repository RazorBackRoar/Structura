import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "Structura.spec"


class BuildEntrypointTest(unittest.TestCase):
    def test_pyinstaller_spec_references_existing_script(self):
        spec_text = SPEC_PATH.read_text(encoding="utf-8")
        match = re.search(r"Analysis\(\s*\[\s*'([^']+)'", spec_text)

        self.assertIsNotNone(match, "Could not find the PyInstaller entry script.")

        entry_script = ROOT / match.group(1)
        self.assertTrue(
            entry_script.is_file(),
            f"PyInstaller entry script does not exist: {entry_script}",
        )

    def test_pyinstaller_spec_uses_source_entrypoint(self):
        spec_text = SPEC_PATH.read_text(encoding="utf-8")
        match = re.search(r"Analysis\(\s*\[\s*'([^']+)'", spec_text)
        self.assertIsNotNone(match, "Could not find the PyInstaller entry script.")
        self.assertEqual(match.group(1), "src/structura/main.py")

    def test_pyinstaller_spec_uses_structura_branding(self):
        spec_text = SPEC_PATH.read_text(encoding="utf-8")
        self.assertIn("name='Structura.app'", spec_text)
        self.assertIn("icon='assets/Structura.icns'", spec_text)
        self.assertIn(
            "bundle_identifier='com.github.razorbackroar.structura'",
            spec_text,
        )

    def test_pyinstaller_spec_does_not_exclude_runtime_stdlib_imports(self):
        spec_text = SPEC_PATH.read_text(encoding="utf-8")
        self.assertNotIn("'html'", spec_text)

    def test_source_entrypoint_delegates_to_structura_main(self):
        module_path = ROOT / "src" / "structura" / "main.py"
        module_spec = importlib.util.spec_from_file_location(
            "structura_source_main",
            module_path,
        )
        self.assertIsNotNone(module_spec, f"Could not load module spec for {module_path}")
        self.assertIsNotNone(module_spec.loader, f"Could not load module loader for {module_path}")
        assert module_spec is not None
        assert module_spec.loader is not None

        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)

        self.assertTrue(callable(module.main), "Entrypoint must expose a callable main().")
        self.assertTrue(
            callable(module._app_main),
            "Entrypoint must delegate to the app's main (imported as _app_main).",
        )


if __name__ == "__main__":
    unittest.main()
