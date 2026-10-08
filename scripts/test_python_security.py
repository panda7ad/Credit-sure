"""Exploit regression checks for upstream CPython security backports."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if '--vendored' in sys.argv:
    sys.path.insert(0, str(ROOT / 'vendor/cpython_security'))
    sys.argv.remove('--vendored')

import contextlib
import hashlib
import io
import json
import os
import poplib
import shutil
import tarfile
import tempfile
import unittest
from unittest import mock

class SecurityTests(unittest.TestCase):
    def test_module_hashes(self):
        manifest = json.loads((ROOT / 'vendor/cpython_security/manifest.json').read_text())
        for module in (poplib, tarfile, tempfile, shutil):
            self.assertEqual(hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                             manifest['modules'][module.__name__ + '.py']['patched'])

    def test_pop3_command_injection(self):
        client = object.__new__(poplib.POP3)
        client._debugging = 0
        client.encoding = 'utf-8'
        client._putline = mock.Mock()
        for char in [chr(c) for c in range(32)] + [chr(127)]:
            with self.assertRaises(ValueError):
                client._putcmd('USER alice' + char + 'PASS injected')
        client._putline.assert_not_called()
        client._putcmd('USER alice')
        client._putline.assert_called_once_with(b'USER alice')

    def test_tar_filter_rejection(self):
        with tarfile.open(fileobj=io.BytesIO(), mode='w') as archive:
            link = tarfile.TarInfo('blocked-link')
            link.type = tarfile.LNKTYPE
            link.linkname = 'original'
            link._link_target = 'unused'
            original = tarfile.TarInfo('original')
            archive._find_link_target = mock.Mock(return_value=original)
            archive._extract_member = mock.Mock()
            filter_member = mock.Mock(side_effect=[None, original])
            with mock.patch.object(os.path, 'exists', return_value=False):
                archive.makelink_with_filter(link, 'target', filter_member, 'root')
            archive._extract_member.assert_not_called()
            self.assertEqual(filter_member.call_count, 1)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux deployment regression')
    def test_cleanup_symlink_race(self):
        self.assertNotEqual(os.geteuid(), 0, 'Run as the non-root container user')
        self.assertTrue(shutil.rmtree.avoids_symlink_attacks)
        self.assertTrue(tempfile._rmtree_use_dir_fd)
        with tempfile.TemporaryDirectory() as target:
            outside = Path(target) / 'outside'
            outside.write_text('keep')
            original_mode = outside.stat().st_mode
            temporary = tempfile.TemporaryDirectory()
            directory = Path(temporary.name) / 'restricted'
            directory.mkdir()
            (directory / 'inside').write_text('inside')
            directory.chmod(0o500)
            unlink = os.unlink
            raced = False
            def race(path, *, dir_fd=None):
                nonlocal raced
                try:
                    return unlink(path, dir_fd=dir_fd)
                except PermissionError:
                    if not raced:
                        directory.rename(str(directory) + '_moved')
                        directory.symlink_to(target, target_is_directory=True)
                        raced = True
                    raise
            try:
                with mock.patch('os.unlink', race):
                    with contextlib.suppress(OSError):
                        temporary.cleanup()
                self.assertTrue(raced, 'The exploit path must actually execute')
                self.assertEqual(outside.read_text(), 'keep')
                self.assertEqual(outside.stat().st_mode, original_mode)
            finally:
                if directory.is_symlink():
                    directory.unlink()
                    Path(str(directory) + '_moved').rename(directory)
                if directory.exists():
                    directory.chmod(0o700)
                temporary.cleanup()

if __name__ == '__main__':
    unittest.main()
