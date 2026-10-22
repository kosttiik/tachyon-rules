import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("update_rules", Path(__file__).resolve().parents[1] / "scripts/update_rules.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.source = {"createDate": "2026-10-22-00-00-00", "syncToken": "1", "prefixes": [
            {"service": "EC2", "region": "eu-west-1", "ip_prefix": "8.8.8.0/25"},
            {"service": "EC2", "region": "us-east-1", "ip_prefix": "8.8.8.128/25"},
            {"service": "GLOBALACCELERATOR", "region": "GLOBAL", "ip_prefix": "1.1.1.0/24"},
            {"service": "S3", "region": "eu-west-1", "ip_prefix": "9.9.9.0/24"},
        ]}

    def test_filters_collapses_and_preserves_transport(self):
        rule, metadata = update.prepare(self.source)
        self.assertEqual(rule["rules"], [{"network": "udp", "ip_cidr": ["1.1.1.0/24", "8.8.8.0/24"], "port_range": ["1024:65535"]}])
        self.assertEqual(metadata["collapsed_prefix_count"], 2)
        actual = copy.deepcopy(rule)
        actual["version"] = 2
        actual["rules"][0]["port_range"] = "1024:65535"
        update.verify_roundtrip(actual, rule)
        actual["rules"][0]["network"] = "tcp"
        with self.assertRaises(ValueError):
            update.verify_roundtrip(actual, rule)

    def test_qos_only_matches_udp_7770_on_selected_aws_prefixes(self):
        rule, _ = update.prepare(self.source)
        qos = update.qos_rule(rule)
        self.assertEqual(qos["rules"][0]["network"], "udp")
        self.assertEqual(qos["rules"][0]["port_range"], ["7770:7770"])
        self.assertEqual(qos["rules"][0]["ip_cidr"], rule["rules"][0]["ip_cidr"])
        update.verify_roundtrip(qos, qos)
        with self.assertRaises(ValueError):
            update.verify_roundtrip(rule, qos)

    def test_rejects_empty_private_and_malformed_sources(self):
        for prefixes in [[], [{"service": "EC2", "ip_prefix": "10.0.0.0/8"}], [{"service": "EC2", "ip_prefix": "broken"}]]:
            with self.subTest(prefixes=prefixes), self.assertRaises(ValueError):
                update.prepare({**self.source, "prefixes": prefixes})
