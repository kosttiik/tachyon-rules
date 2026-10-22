import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_services import build, verify


class ServicesTest(unittest.TestCase):
    def test_discord_shared_ips_are_udp_and_port_scoped(self):
        rules = build("youtube.com\n", "discord.com\n", "104.16.0.0/12\n66.22.192.0/18\n")
        discord = rules["discord"]
        for rule in discord["rules"]:
            if "ip_cidr" in rule:
                self.assertEqual(rule["network"], "udp")
                self.assertIn(rule["port_range"], [["50000:65535"], ["19000:20000"]])
        verify(discord, discord)
        flattened = copy.deepcopy(discord)
        del flattened["rules"][1]["port_range"]
        with self.assertRaises(ValueError):
            verify(flattened, discord)

    def test_rejects_bad_upstream_data(self):
        for domain, subnet in [("", "104.16.0.0/12"), ("bad domain", "104.16.0.0/12"), ("discord.com", "10.0.0.0/8")]:
            with self.subTest(domain=domain, subnet=subnet), self.assertRaises(ValueError):
                build("youtube.com", domain, subnet)
