from __future__ import annotations
from pathlib import Path
import sys,unittest,json,struct
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.validate_suite import audit,run_mutation_probes,readcases
from suite.support.wire import request,pack_bits,unpack_bits,word_payload,DEFAULT_ROUTE
class TestSuiteIntegrity(unittest.TestCase):
    def test_all_crosslinks(self):
        result=audit();self.assertEqual([],result['errors'])
    def test_all_34_p0_requirements_covered(self):
        result=audit();self.assertEqual(34,result['p0_requirements_linked'])
    def test_69_baseline_test_ids_exact(self):
        result=audit();self.assertEqual(69,result['legacy_linked'])
    def test_all_risks_linked(self):
        result=audit();self.assertEqual(result['risks'],result['risks_linked'])
    def test_at_least_40_concrete_wire_cases(self):
        result=audit();self.assertGreaterEqual(result['live_executable_spec_count'],40)
    def test_validator_mutation_probes(self):
        self.assertTrue(all(run_mutation_probes().values()))
    def test_d_byte_order(self):
        pkt=request(cmd=0x1401,head=100,points=2,payload=word_payload([0x1234,0xFFFF]))
        self.assertEqual(bytes.fromhex('34 12 FF FF'),pkt[-4:])
    def test_bit_pack_odd(self):
        self.assertEqual(bytes.fromhex('10 10 10'),pack_bits([1,0,1,0,1]))
        self.assertEqual([1,0,1,0,1],unpack_bits(bytes.fromhex('10 10 10'),5))
    def test_bit_pack_even(self):
        self.assertEqual(bytes.fromhex('01 10 11'),pack_bits([0,1,1,0,1,1]))
        self.assertEqual([0,1,1,0,1,1],unpack_bits(bytes.fromhex('01 10 11'),6))
    def test_odd_low_nibble_nonzero_fails(self):
        with self.assertRaises(ValueError):unpack_bits(b'\x11',1)
    def test_no_runtime_success_claim(self):
        st=audit();self.assertFalse(st['actual_server_test_pass']);self.assertFalse(st['actual_protocol_compatibility_verified'])
    def test_wire_fixture_exact_headers(self):
        fixtures=json.loads((ROOT/'suite/fixtures/wire_vectors_baseline.json').read_text(encoding='utf8'))
        for f in fixtures:
            rq=bytes.fromhex(f['request_hex']);rp=bytes.fromhex(f['response_hex'])
            with self.subTest(vector=f['id']):
                self.assertEqual(len(rq)-9,int.from_bytes(rq[7:9],'little'))
                self.assertEqual(len(rp)-9,int.from_bytes(rp[7:9],'little'))
    def test_reference_builder_read_vector(self):
        fixtures=json.loads((ROOT/'suite/fixtures/wire_vectors_baseline.json').read_text(encoding='utf8'))
        self.assertEqual(request(head=100,points=3),bytes.fromhex(fixtures[0]['request_hex']))
    def test_reference_builder_word_write_vector(self):
        fixtures=json.loads((ROOT/'suite/fixtures/wire_vectors_baseline.json').read_text(encoding='utf8'))
        exp=request(cmd=0x1401,head=100,points=3,payload=word_payload([0x1995,0x1202,0x1130]))
        self.assertEqual(exp,bytes.fromhex(fixtures[1]['request_hex']))
    def test_reference_builder_bit_write_vector(self):
        fixtures=json.loads((ROOT/'suite/fixtures/wire_vectors_baseline.json').read_text(encoding='utf8'))
        exp=request(cmd=0x1401,sub=1,head=10,device=0x90,points=5,payload=pack_bits([1,0,1,0,1]))
        self.assertEqual(exp,bytes.fromhex(fixtures[2]['request_hex']))
if __name__=='__main__':unittest.main()
