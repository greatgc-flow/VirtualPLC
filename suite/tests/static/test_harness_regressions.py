"""Regression tests for BUG-01 / BUG-02: no substring-based fake green."""
import subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.gate_report import parse_junit

class HarnessRegressions(unittest.TestCase):
    def _xml(self,content):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'junit.xml';p.write_text('<testsuite>'+content+'</testsuite>')
            return parse_junit(p,{'CASE-0158','CASE-0159'})
    def test_exact_property_only(self):
        seen,dup,unknown,anonymous=self._xml('<testcase name="CASE-0158-this-is-a-fake-pass" />')
        self.assertEqual(seen,{})
        self.assertEqual(anonymous,1)
    def test_exact_identity_accepted(self):
        seen,dup,unknown,anonymous=self._xml('<testcase name="irrelevant"><properties><property name="case_id" value="CASE-0158" /></properties></testcase>')
        self.assertEqual(seen,{'CASE-0158':'PASS'})
    def test_duplicate_cannot_pass(self):
        tc='<testcase name="t"><properties><property name="case_id" value="CASE-0158" /></properties></testcase>'
        seen,dup,unknown,anonymous=self._xml(tc+tc)
        self.assertEqual(seen,{})
        self.assertEqual(dup,['CASE-0158'])
    def test_unknown_case_rejected(self):
        seen,dup,unknown,anonymous=self._xml('<testcase><properties><property name="case_id" value="CASE-9999" /></properties></testcase>')
        self.assertEqual(seen,{})
        self.assertEqual(unknown,['CASE-9999'])
    def test_run_pymc_option_is_registered_and_skips_without_server(self):
        p=subprocess.run([sys.executable,'-m','pytest','suite/tests/live/test_pymc_compat.py',
            '-q','--run-pymc'],cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertNotIn('unrecognized arguments',p.stdout+p.stderr)
        self.assertIn('MC_PINNED_PYMC_VERSION',p.stdout+p.stderr)

if __name__=='__main__':unittest.main()
