#!/usr/bin/env python3
"""Build source-derived service lists without flattening Discord UDP conditions."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "itdoginfo/allow-domains"


def fetch(url):
    headers = {"User-Agent": "tachyon-rules-updater"}
    if url.startswith("https://api.github.com/") and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return response.read()


def domains(text):
    values = sorted({line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")})
    if not values or any(len(d) > 253 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", d) or "." not in d for d in values):
        raise ValueError("Invalid or empty upstream domain list")
    return values


def build(youtube, discord, subnets):
    networks = [ipaddress.IPv4Network(line.strip()) for line in subnets.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not networks or any(not n.is_global for n in networks):
        raise ValueError("Invalid or empty Discord IPv4 list")
    cidrs = [str(n) for n in ipaddress.collapse_addresses(networks)]
    return {
        "youtube": {"version": 3, "rules": [{"domain_suffix": domains(youtube)}]},
        "discord": {"version": 3, "rules": [
            {"domain_suffix": domains(discord)},
            {"network": "udp", "ip_cidr": cidrs, "port_range": ["50000:65535"]},
            {"network": "udp", "ip_cidr": ["104.16.0.0/12"], "port_range": ["19000:20000"]},
        ]},
    }


def verify(actual, expected):
    def normalized(rules):
        return [{k: sorted(v if isinstance(v, list) else [v]) for k, v in rule.items()} for rule in rules]
    if normalized(actual["rules"]) != normalized(expected["rules"]):
        raise ValueError("Compiled service list changed domain/UDP/IP/port conditions")


def main():
    commit = json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/commits/main"))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid upstream commit")
    paths = ["Services/youtube.lst", "Services/discord.lst", "Subnets/IPv4/discord.lst"]
    bodies = {p: fetch(f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{p}") for p in paths}
    lists = build(*(bodies[p].decode() for p in paths))
    changed = [name for name, rule in lists.items() if not (ROOT / f"services/{name}.json").exists() or json.loads((ROOT / f"services/{name}.json").read_text()) != rule]
    if not changed:
        print("Service conditions unchanged; no rebuild or commit needed.")
        return
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        (stage / "services").mkdir()
        files = []
        for name, rule in lists.items():
            source = stage / f"services/{name}.json"
            source.write_text(json.dumps(rule, indent=2) + "\n")
            binary = source.with_suffix(".srs")
            subprocess.run(["sing-box", "rule-set", "compile", str(source), "-o", str(binary)], check=True)
            subprocess.run(["sing-box", "rule-set", "decompile", str(binary), "-o", str(stage / "roundtrip.json")], check=True)
            verify(json.loads((stage / "roundtrip.json").read_text()), rule)
            files += [f"services/{name}.json", f"services/{name}.srs"]
        (stage / "services/sources.json").write_text(json.dumps({
            "repository": f"https://github.com/{REPOSITORY}", "commit": commit,
            "files": {p: hashlib.sha256(body).hexdigest() for p, body in bodies.items()},
            "discord_port_policy": "Upstream convert.py: UDP 50000-65535 for Discord IPv4; UDP 19000-20000 for 104.16.0.0/12. No unrestricted IP rule.",
            "ipv6": False,
        }, indent=2) + "\n")
        files.append("services/sources.json")
        (stage / "services/SHA256SUMS").write_text("".join(f"{hashlib.sha256((stage / name).read_bytes()).hexdigest()}  {name}\n" for name in files))
        (ROOT / "services").mkdir(exist_ok=True)
        for name in [*files, "services/SHA256SUMS"]:
            shutil.copyfile(stage / name, ROOT / name)
    print(f"Updated service lists from {commit}: {', '.join(changed)}")


if __name__ == "__main__":
    main()
