#!/usr/bin/env python3
"""Refresh the scoped AWS rule set; publish files only after a verified build."""
import hashlib
import ipaddress
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://ip-ranges.amazonaws.com/ip-ranges.json"
SERVICES = {"EC2", "GLOBALACCELERATOR"}


def prepare(source):
    # Reject malformed/empty responses before replacing the last working list.
    prefixes = source["prefixes"]
    if not isinstance(prefixes, list):
        raise ValueError("AWS prefixes must be an array")
    networks = []
    for service in sorted(SERVICES):
        selected = [ipaddress.IPv4Network(p["ip_prefix"]) for p in prefixes if p["service"] == service]
        if not selected or any(not n.is_global for n in selected):
            raise ValueError(f"Missing or non-public IPv4 prefixes for {service}")
        networks.extend(selected)
    cidrs = [str(n) for n in ipaddress.collapse_addresses(networks)]
    rule = {"version": 3, "rules": [{"network": "udp", "ip_cidr": cidrs, "port_range": ["1024:65535"]}]}
    metadata = {
        "source": SOURCE,
        "source_create_date": source["createDate"],
        "source_sync_token": str(source["syncToken"]),
        "services": sorted(SERVICES),
        "regions": "all",
        "address_family": "IPv4",
        "collapsed_prefix_count": len(cidrs),
        "network": "udp",
        "destination_ports": "1024-65535",
        "format_version": 3,
    }
    return rule, metadata


def verify_roundtrip(actual, expected):
    rules = actual["rules"]
    if len(rules) != 1 or set(rules[0]) != {"network", "ip_cidr", "port_range"}:
        raise ValueError("Compiled rule set has unexpected conditions")
    rule = rules[0]
    network = rule["network"] if isinstance(rule["network"], list) else [rule["network"]]
    ports = rule["port_range"] if isinstance(rule["port_range"], list) else [rule["port_range"]]
    if network != ["udp"] or ports != ["1024:65535"] or set(rule["ip_cidr"]) != set(expected["rules"][0]["ip_cidr"]):
        raise ValueError("Compiled rule set did not preserve UDP, ports or prefixes")


def main():
    with urllib.request.urlopen(SOURCE, timeout=60) as response:
        rule, metadata = prepare(json.load(response))
    current = ROOT / "games/aws-udp.json"
    if current.exists() and json.loads(current.read_text()) == rule:
        print("Selected AWS prefixes unchanged; no rebuild or commit needed.")
        return
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        (stage / "games").mkdir()
        (stage / "games/aws-udp.json").write_text(json.dumps(rule, indent=2) + "\n")
        (stage / "games/aws-cidrs.txt").write_text("\n".join(rule["rules"][0]["ip_cidr"]) + "\n")
        (stage / "sources.json").write_text(json.dumps(metadata, indent=2) + "\n")
        subprocess.run(["sing-box", "rule-set", "compile", str(stage / "games/aws-udp.json"), "-o", str(stage / "games/aws-udp.srs")], check=True)
        subprocess.run(["sing-box", "rule-set", "decompile", str(stage / "games/aws-udp.srs"), "-o", str(stage / "roundtrip.json")], check=True)
        verify_roundtrip(json.loads((stage / "roundtrip.json").read_text()), rule)
        files = ["games/aws-cidrs.txt", "games/aws-udp.json", "games/aws-udp.srs", "sources.json"]
        (stage / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((stage / name).read_bytes()).hexdigest()}  {name}\n" for name in files))
        for name in [*files, "SHA256SUMS"]:
            shutil.copyfile(stage / name, ROOT / name)
    print(f"Updated {len(rule['rules'][0]['ip_cidr'])} IPv4 prefixes from AWS {metadata['source_create_date']}.")


if __name__ == "__main__":
    main()
