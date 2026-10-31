from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pcbknowledge.v2.cli import derived_path
from pcbknowledge.v2.drc import _derived, _inputs


class AliasSpellingTests(unittest.TestCase):
    def test_alias_and_canonical_root_requested_cross_product(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder).resolve()
            actual = parent / 'actual'
            root = actual / 'repository'
            (root / 'build').mkdir(parents=True)
            alias = parent / 'system-alias'
            original = Path.resolve
            def resolve(path, *args, **kwargs):
                if path.is_relative_to(alias):
                    path = actual / path.relative_to(alias)
                return original(path, *args, **kwargs)
            with patch.object(Path, 'resolve', resolve), patch.object(
                    Path, 'is_symlink', lambda path: path == alias):
                for checker in (derived_path, _derived):
                    for root_spelling in (root, alias / 'repository'):
                        for requested in (root / 'build/out', alias / 'repository/build/out', 'build/out'):
                            with self.subTest(root=root_spelling, requested=requested):
                                self.assertEqual(checker(root_spelling, requested), root / 'build/out')

    def test_repeated_root_alias_cannot_hide_a_descendant_redirect(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / 'repository'
            root.mkdir()
            link = root / 'build/up'
            original = Path.resolve
            def resolve(path, *args, **kwargs):
                if path.is_relative_to(link):
                    path = root.parent / path.relative_to(link)
                return original(path, *args, **kwargs)
            with patch.object(Path, 'resolve', resolve), patch.object(Path, 'is_symlink', lambda p: p == link):
                for checker in (derived_path, _derived):
                    with self.assertRaisesRegex(ValueError, 'symlink'):
                        checker(root, link / 'repository/build/out')

    def test_reparse_and_build_traversal_remain_forbidden(self):
        import stat
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            original = Path.lstat
            for target in (root, root / 'build', root / 'build/junction'):
                def attributes(path):
                    if path == target:
                        return SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
                    return original(path)
                with patch.object(Path, 'is_symlink', return_value=False), patch.object(Path, 'lstat', attributes):
                    for checker in (derived_path, _derived):
                        with self.assertRaises(ValueError):
                            checker(root, 'build/junction/file')
            for value in ('build', 'build/../../outside', '../outside', 'knowledge/file'):
                for checker in (derived_path, _derived):
                    with self.assertRaises(ValueError):
                        checker(root, value)

    def test_drc_keeps_external_inputs_but_rejects_external_parent_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder).resolve()
            root = parent / 'repo'
            root.mkdir()
            board = parent / 'external/board.kicad_pcb'
            board.parent.mkdir()
            for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
                board.with_suffix(suffix).write_text('synthetic', encoding='utf-8')
            self.assertEqual(_inputs(root, board)[0], board)
            original = Path.is_symlink
            with patch.object(Path, 'is_symlink', lambda p: p == board.parent or original(p)):
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    _inputs(root, board)

    def test_selected_repository_junction_cannot_be_classified_as_external(self):
        import stat
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder).resolve()
            root = parent / 'repo'
            root.mkdir()
            junction = root / 'build/junction'
            board = junction / 'board.kicad_pcb'
            resolve, lstat = Path.resolve, Path.lstat
            def resolved(path, *args, **kwargs):
                if path.is_relative_to(junction):
                    path = parent / 'outside' / path.relative_to(junction)
                return resolve(path, *args, **kwargs)
            def attributes(path):
                if path == junction:
                    return SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
                return lstat(path)
            with patch.object(Path, 'resolve', resolved), patch.object(Path, 'lstat', attributes), \
                    patch.object(Path, 'is_symlink', return_value=False):
                with self.assertRaisesRegex(ValueError, 'reparse'):
                    _inputs(root, board)

    def test_selected_repository_inputs_allow_alias_ancestors(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder).resolve()
            root = parent / 'repo'
            root.mkdir()
            board = root / 'board.kicad_pcb'
            for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
                board.with_suffix(suffix).write_text('synthetic', encoding='utf-8')
            original = Path.is_symlink
            with patch.object(Path, 'is_symlink', lambda p: p == parent or original(p)):
                self.assertEqual(_inputs(root, board)[0], board)
            with patch.object(Path, 'is_symlink', lambda p: p == board.with_suffix('.kicad_pro') or original(p)):
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    _inputs(root, board)


if __name__ == '__main__':
    unittest.main()
