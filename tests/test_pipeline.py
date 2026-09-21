import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from src.pipeline import STAGES, run_pipeline


class PipelineTests(unittest.TestCase):
    def test_validation_failure_blocks_all_publication_builds(self):
        calls=[]
        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=1 if 'src.validate_database' in command else 0)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(RuntimeError):
                run_pipeline(root, runner, lambda _: self.fail('Verification must not run'))
            manifest=json.loads((root/'output/pipeline/manifest.json').read_text())
            self.assertEqual(manifest['status'], 'failed')
            self.assertEqual(len(calls), 4)
            self.assertNotIn('src.build_dashboard', str(calls))
            self.assertNotIn('src.build_dissertation_report', str(calls))

    def test_success_records_revision_and_checksums(self):
        calls=[]
        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout='test-revision\n')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'site').mkdir()
            (root/'site/index.html').write_text('synthetic fixture')
            result=run_pipeline(root, runner, lambda _: {'reports': 'verified'})
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['commit'], 'test-revision')
            self.assertEqual(len(result['files']['site/index.html']), 64)
            self.assertEqual([s['name'] for s in result['stages']], [s[0] for s in STAGES])
            self.assertTrue(all(c[:4]==['uv','run','python','-m'] for c in calls[:-1]))

    def test_artifact_failure_does_not_produce_success_manifest(self):
        def runner(*args, **kwargs):
            return SimpleNamespace(returncode=0)
        def verifier(root):
            raise ValueError('Mismatched report copy')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):
                run_pipeline(root, runner, verifier)
            self.assertEqual(json.loads((root/'output/pipeline/manifest.json').read_text())['status'], 'failed')
