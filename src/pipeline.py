"""Run the validated synthetic-data release pipeline without resetting a database."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
from src.database import ROOT

STAGES = (
    ('tests', ('unittest', 'discover', '-s', 'tests', '-v')),
    ('migrate', ('alembic', 'upgrade', 'head')),
    ('load', ('src.load_csvs',)),
    ('validate', ('src.validate_database',)),
    ('dashboard', ('src.build_dashboard',)),
    ('reports', ('src.build_dissertation_report',)),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_artifacts(root=ROOT):
    validation = json.loads((root / 'output/validation/database_validation.json').read_text())
    if validation['status'] != 'passed' or validation['critical_findings'] != 0:
        raise ValueError('Critical database findings prevent release')
    snapshot_text = (root / 'site/dashboard-data.js').read_text()
    prefix = 'window.LEGALTECH_DATA = '
    if not snapshot_text.startswith(prefix):
        raise ValueError('Invalid dashboard snapshot')
    snapshot = json.loads(snapshot_text[len(prefix):].strip().removesuffix(';'))
    if snapshot['metadata']['critical_findings'] != 0 or snapshot['metadata']['validation_status'] != 'passed':
        raise ValueError('Dashboard snapshot is not validated')
    if snapshot['metadata']['core_row_counts'] != validation['core_row_counts']:
        raise ValueError('Dashboard and validation counts differ')
    summaries = {}
    for language in ('en', 'pt-PT'):
        name = f'operacao_legaltech_dissertation_{language}.pdf'
        path = root / 'output/pdf' / name
        reader = PdfReader(path)
        if reader.metadata.author != 'Nubia Aparecida Silva Almeida':
            raise ValueError('Incorrect report author')
        contents = '\n'.join(page.extract_text() or '' for page in reader.pages)
        for expected in ('Nubia Aparecida Silva Almeida', 'Adwiteey Mauriya, Ph.D.', '09:00', '18:00', '10:00'):
            if expected not in contents:
                raise ValueError(f'Missing required report content: {expected}')
        if not reader.pages or any(not (page.extract_text() or '').strip() for page in reader.pages):
            raise ValueError('Report has empty pages')
        if digest(path) != digest(root / 'site/reports' / name):
            raise ValueError('Published report copy differs from built report')
        summaries[language] = {'pages': len(reader.pages), 'sha256': digest(path)}
    expected_alias = digest(root / 'output/pdf/operacao_legaltech_dissertation_en.pdf')
    if digest(root / 'site/reports/operacao_legaltech_dissertation_report.pdf') != expected_alias:
        raise ValueError('Legacy English download alias differs')
    return {'reports': summaries, 'warnings': validation['warnings'],
            'snapshot_generated_at': snapshot['metadata']['generated_at']}


def run_pipeline(root=ROOT, runner=subprocess.run, verifier=verify_artifacts):
    directory = root / 'output/pipeline'
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(), 'stages': []}
    output = directory / 'manifest.json'
    output.write_text(json.dumps(manifest, indent=2)+'\n')
    try:
        for name, module in STAGES:
            command = ['uv', 'run', 'python', '-m', *module]
            print(f'Pipeline stage: {name}', flush=True)
            result = runner(command, cwd=root, check=False)
            manifest['stages'].append({'name': name, 'returncode': result.returncode})
            if result.returncode:
                raise RuntimeError(f'Pipeline stopped at {name} (exit {result.returncode})')
        manifest['verification'] = verifier(root)
        manifest['files'] = {
            str(path.relative_to(root)): digest(path)
            for folder in ('site', 'data/cleaned')
            for path in sorted((root / folder).rglob('*')) if path.is_file()
        }
        revision = runner(['git', 'rev-parse', 'HEAD'], cwd=root, check=False, capture_output=True, text=True)
        manifest['commit'] = revision.stdout.strip() if revision.returncode == 0 else None
        manifest['status'] = 'passed'
    except Exception as exc:
        manifest['status'] = 'failed'
        # Stage names/exception types only: do not copy provider or database secrets into artifacts.
        manifest['error_type'] = type(exc).__name__
        raise
    finally:
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true', help='Show stages without changing files or database')
    args = parser.parse_args()
    if args.plan:
        for name, module in STAGES:
            print(f'{name}: uv run python -m {" ".join(module)}')
        print('verify: inspect PDF content/copies and write SHA-256 release manifest')
        return
    manifest = run_pipeline()
    print(f"Release pipeline: {manifest['status']}; output/pipeline/manifest.json")


if __name__ == '__main__':
    main()
