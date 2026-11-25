#!/usr/bin/env python3
"""Write a CycloneDX 1.5 SBOM for an ENVY BLACK VEIL image from its RPM database.

    rpm -qa --root <image root> --qf '%{NAME}\\t%{EPOCHNUM}\\t%{VERSION}\\t%{RELEASE}\\t%{ARCH}\\t%{LICENSE}\\t%{VENDOR}\\n' \\
        | python3 ci/sbom.py --version 0.1.0 --arch x86_64 > envy-black-veil-0.1.0-x86_64.cdx.json

Every installed package becomes a component with a package URL (purl) naming
where it comes from: AlmaLinux, EPEL (Fedora Project) or ENVY. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

NAMESPACES = {"AlmaLinux": "almalinux", "Fedora Project": "fedora"}


def component(fields: list[str]) -> dict:
    name, epoch, version, release, arch, licence, vendor = (fields + [""] * 7)[:7]
    namespace = NAMESPACES.get(vendor) or ("envy" if name.startswith("envy-") else "almalinux")
    full = f"{version}-{release}"
    qualifiers = [f"arch={arch}"] + ([f"epoch={epoch}"] if epoch not in ("", "0", "(none)") else [])
    item = {
        "type": "library",
        "bom-ref": f"rpm:{name}.{arch}",
        "name": name,
        "version": f"{epoch}:{full}" if epoch not in ("", "0", "(none)") else full,
        "purl": f"pkg:rpm/{namespace}/{quote(name)}@{quote(full)}?{'&'.join(qualifiers)}",
    }
    if vendor and vendor != "(none)":
        item["supplier"] = {"name": vendor}
    if licence and licence != "(none)":
        item["licenses"] = [{"license": {"name": licence}}]
    return item


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", required=True)
    ap.add_argument("--arch", required=True)
    args = ap.parse_args()
    rows = [line.rstrip("\n").split("\t") for line in sys.stdin if line.strip() and not line.startswith("gpg-pubkey\t")]
    components = sorted((component(r) for r in rows), key=lambda c: c["bom-ref"])
    if not components:
        print("sbom.py: no packages on stdin", file=sys.stderr)
        return 1
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "operating-system",
                "bom-ref": "envy-black-veil",
                "name": "ENVY BLACK VEIL",
                "version": f"{args.version} ({args.arch})",
                "description": "AlmaLinux 10 + KDE Plasma 6 live and installable OS image",
                "externalReferences": [{"type": "vcs", "url": "https://github.com/xzchick/envy-black-veil"}],
            },
        },
        "components": components,
    }
    json.dump(bom, sys.stdout, indent=1)
    sys.stdout.write("\n")
    print(f"sbom.py: {len(components)} packages", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
