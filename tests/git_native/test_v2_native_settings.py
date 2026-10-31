"""Native board saves must not synthesize or overwrite authoritative project settings."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pcbknowledge.v2.kicad_bridge import operate


class SettingsTests(unittest.TestCase):
    def test_merge_and_fill_skip_native_settings_then_source_rules_can_be_copied(self):
        for action in ('merge-session', 'fill'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / 'build/source.kicad_pcb'
                source.parent.mkdir()
                source.write_text('source-board')
                source.with_suffix('.kicad_pro').write_text('source-project')
                source.with_suffix('.kicad_dru').write_text('source-rules')
                session = root / 'build/router.ses'
                session.write_text('session')
                output = root / 'build/final.kicad_pcb'
                mock = MagicMock()
                def save(name, board, skip):
                    self.assertTrue(skip)
                    Path(name).write_text('saved-board')
                    return True
                mock.SaveBoard.side_effect = save
                with patch.dict('sys.modules', {'pcbnew': mock}):
                    operate(root, action, source, output, session if action == 'merge-session' else None)
                self.assertFalse(output.with_suffix('.kicad_pro').exists())
                self.assertEqual(source.with_suffix('.kicad_pro').read_text(), 'source-project')
                self.assertEqual(source.with_suffix('.kicad_dru').read_text(), 'source-rules')
                self.assertEqual(source.read_text(), 'source-board')

    def test_existing_or_symlink_sidecar_is_rejected_before_native_import(self):
        for suffix in ('.kicad_pro', '.kicad_dru', '.kicad_prl'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / 'build/source.kicad_pcb'
                source.parent.mkdir()
                source.write_text('source')
                output = root / 'build/final.kicad_pcb'
                target = output.with_suffix(suffix)
                target.write_text('existing-authority')
                mock = MagicMock()
                with patch.dict('sys.modules', {'pcbnew': mock}), self.assertRaisesRegex(ValueError, 'fresh'):
                    operate(root, 'fill', source, output)
                mock.LoadBoard.assert_not_called()
                self.assertEqual(target.read_text(), 'existing-authority')
                target.unlink()
                target.symlink_to(source)
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    operate(root, 'fill', source, output)
