"""Commit discipline and explicit, content-bound readability guard regressions."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import check_code_style as style
from configs import check_commits as commits


class CommitGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic tester')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.commit('historical subject intentionally not rewritten', {'README.md': 'original'})
        self.base = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args]).decode()

    def commit(self, message, files):
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8', newline='\n')
        self.git('add', '.')
        self.git('commit', '--allow-empty', '-qm', message)

    def test_new_range_accepts_separate_data_and_code_without_rewriting_history(self):
        self.commit('[data]: add original metadata', {'knowledge/parts/synthetic.json': '{}'})
        self.commit('[feat]: add consumer behavior', {'src/example.py': 'x = 1\n'})
        selected, errors = commits.check(self.root, self.base + '..HEAD')
        self.assertEqual(len(selected), 2)
        self.assertEqual(errors, [])
        self.assertEqual(commits.check(self.root, 'HEAD..HEAD'), ([], []))

    def test_subject_and_knowledge_scope_are_enforced(self):
        cases = [
            ('feat: missing brackets', {'code.py': '1'}, 'subject'),
            ('[invented]: invalid type', {'code.py': '2'}, 'subject'),
            ('[feat]: wrong data type', {'knowledge/test.json': '{}'}, 'only [data]'),
            ('[data]: mixed paths', {'knowledge/test.json': '[]', 'code.py': '3'}, 'MIXED'),
            ('[data]: software only', {'code.py': '4'}, 'DATA_ONLY'),
            ('[data]: empty data commit', {}, 'DATA_ONLY'),
        ]
        for message, files, reason in cases:
            previous = self.git('rev-parse', 'HEAD').strip()
            self.commit(message, files)
            errors = commits.check(self.root, previous + '..HEAD')[1]
            self.assertTrue(any(reason in item for item in errors), errors)

    def test_subject_length_and_wording_apply_only_to_new_commits(self):
        for subject in ('[feat]: honest result', '[fix]: BOUNDED result',
                        '[docs]: not a guarantee', '[feat]: honestly report',
                        '[feat]: unbounded model', '[feat]: ' + 'x' * 65):
            with self.subTest(subject=subject):
                previous = self.git('rev-parse', 'HEAD').strip()
                self.commit(subject, {'code.py': subject})
                errors = commits.check(self.root, previous + '..HEAD')[1]
                self.assertTrue(any('subject' in item for item in errors), errors)
        previous = self.git('rev-parse', 'HEAD').strip()
        self.commit('[feat]: ' + 'x' * 64, {'code.py': 'at limit'})
        self.assertEqual(commits.check(self.root, previous + '..HEAD')[1], [])
        self.assertEqual(commits.check(self.root, 'HEAD..HEAD'), ([], []))

    def test_rename_cannot_hide_mixed_scope(self):
        old = self.git('rev-parse', 'HEAD').strip()
        (self.root / 'knowledge').mkdir()
        self.git('mv', 'README.md', 'knowledge/copied.md')
        self.git('commit', '-qm', '[data]: relocate original')
        errors = commits.check(self.root, old + '..HEAD')[1]
        self.assertTrue(any('MIXED' in item for item in errors))

    def test_merge_changes_are_checked_against_first_parent(self):
        original_branch = self.git('branch', '--show-current').strip()
        self.git('checkout', '-qb', 'data-side')
        self.commit('[data]: add catalog on side', {'knowledge/side.json': '{}'})
        self.git('checkout', '-q', original_branch)
        self.commit('[feat]: add software on main', {'software.py': 'x = 1'})
        previous = self.git('rev-parse', 'HEAD').strip()
        self.git('merge', '--no-ff', '-qm', '[feat]: merge catalog', 'data-side')
        errors = commits.check(self.root, previous + '..HEAD')[1]
        self.assertTrue(any('only [data]' in item for item in errors), errors)

    def test_unusual_path_names_cannot_hide_knowledge_changes(self):
        # Git trees can contain names that Windows cannot materialize. Construct
        # real objects directly so every platform exercises the same path bytes.
        def git_input(arguments, payload):
            return subprocess.check_output(
                ['git', '-C', str(self.root), *arguments], input=payload).decode().strip()
        blob = git_input(['hash-object', '-w', '--stdin'], b'{}')
        previous = self.git('rev-parse', 'HEAD').strip()
        readme = self.git('rev-parse', 'HEAD:README.md').strip()
        for name in ('caf\u00e9.json', 'tab\tname.json'):
            entry = f'100644 blob {blob}\t{name}\0'.encode('utf-8')
            knowledge = git_input(['mktree', '-z'], entry)
            root_tree = git_input(['mktree', '-z'], (
                f'100644 blob {readme}\tREADME.md\0'
                f'040000 tree {knowledge}\tknowledge\0').encode())
            current = git_input(['commit-tree', root_tree, '-p', previous],
                                b'[feat]: wrong knowledge scope\n')
            errors = commits.check(self.root, previous + '..' + current)[1]
            self.assertTrue(any('only [data]' in item for item in errors), errors)

    def test_event_ranges_are_exact_and_fail_closed(self):
        self.assertEqual(commits.event_range({'before': 'a'*40, 'after': 'b'*40}, 'push'),
                         'a'*40 + '..' + 'b'*40)
        event = {'pull_request': {'base': {'sha': 'a'}, 'head': {'sha': 'b'}}}
        self.assertEqual(commits.event_range(event, 'pull_request'), 'a..b')
        self.assertEqual(commits.event_range({}, 'workflow_dispatch'), 'HEAD^..HEAD')
        with self.assertRaises(ValueError):
            commits.event_range({}, 'issue_comment')
        with self.assertRaisesRegex(ValueError, 'explicit validated'):
            commits.event_range({'before': '0'*40, 'after': 'b'*40}, 'push')
        for invalid in ('HEAD', '--all..HEAD', '..HEAD', 'HEAD...', 'HEAD..'):
            with self.assertRaises(ValueError):
                commits.check(self.root, invalid)


class CodeStyleGuardTests(unittest.TestCase):
    def test_line_statement_and_function_limits_have_negative_cases(self):
        valid = 'def f():\n    text = "semicolon; inside string"\n    return text\n'
        self.assertEqual(style.inspect_source(valid, 'src/pcbknowledge/example.py'), [])
        cases = [
            ('x = "' + 'a'*121 + '"\n', 'line-length'),
            ('x = 1; y = 2\n', 'multiple-statements'),
            ('if True: pass\n', 'multiple-statements'),
            ('if True:\n    pass\nelse: pass\n', 'multiple-statements'),
            ('def f():\n' + '    x = 1\n'*80, 'function-length'),
        ]
        for source, expected in cases:
            self.assertTrue(any(item['rule'] == expected for item in style.inspect_source(source, 'x.py')))
        self.assertEqual(style.inspect_source('def f():\n' + '    x = 1\n'*79, 'x.py'), [])

    def test_allowance_is_exact_content_and_count_not_a_blanket_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            path = root / 'src/pcbknowledge/example.py'
            path.parent.mkdir(parents=True)
            source = 'x = 1; y = 2\n'
            path.write_text(source)
            finding = style.inspect_source(source, 'src/pcbknowledge/example.py')[0]
            entry = {key: finding[key] for key in ('path', 'rule', 'fingerprint')}
            allowlist = root / 'allowlist.json'
            allowlist.write_text(json.dumps({'temporary_until': 'Stage 6c', 'entries': [{**entry, 'count': 1}]}))
            self.assertEqual(style.check(root, allowlist)[1], [])
            path.write_text('\n' + source)
            self.assertEqual(style.check(root, allowlist)[1], [])
            path.write_text(source + source)
            self.assertEqual(len(style.check(root, allowlist)[1]), 1)
            path.write_text('x = 3; y = 4\n')
            self.assertEqual(len(style.check(root, allowlist)[1]), 1)
            allowlist.write_text(json.dumps({'temporary_until': 'Stage 6c', 'entries': []}))
            self.assertEqual(len(style.check(root, allowlist)[1]), 1)

    def test_nested_source_directory_symlink_cannot_escape_scan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / 'src/pcbknowledge'
            source.mkdir(parents=True)
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'hidden.py').write_text('x = 1; y = 2\n')
            (source / 'nested').symlink_to(outside, target_is_directory=True)
            allowlist = root / 'allowlist.json'
            allowlist.write_text(json.dumps({'temporary_until':'Stage 6c','entries':[]}))
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                style.check(root, allowlist)

    def test_bad_allowlist_and_syntax_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            path = root / 'src/pcbknowledge/example.py'
            path.parent.mkdir(parents=True)
            path.write_text('x = 1\n')
            allowlist = root / 'allowlist.json'
            allowlist.write_text('{}')
            with self.assertRaises(ValueError):
                style.check(root, allowlist)
        with self.assertRaises(SyntaxError):
            style.inspect_source('def broken(:\n', 'broken.py')
