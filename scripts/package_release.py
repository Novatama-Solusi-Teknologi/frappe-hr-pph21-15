"""Create a source ZIP suitable for uploading to a new GitHub repository."""
from hashlib import sha256
from pathlib import Path
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from frappe_hr_pph21 import __version__

out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'dist'
out.mkdir(parents=True, exist_ok=True)
archive = out / f'frappe-hr-pph21-v{__version__}-source.zip'
excluded = {'.git', '.venv', 'dist', '__pycache__', '.pytest_cache', '.ruff_cache', '.DS_Store'}
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for file in sorted(root.rglob('*')):
        relative = file.relative_to(root)
        if not file.is_file() or set(relative.parts) & excluded or file.suffix in ('.pyc', '.pyo'):
            continue
        z.write(file, Path('frappe-hr-pph21') / relative)
digest = sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert 'frappe-hr-pph21/pyproject.toml' in z.namelist()
    assert 'frappe-hr-pph21/README.md' in z.namelist()
print(f'{archive}\nSHA256 {digest}\nSize {archive.stat().st_size:,} bytes')
