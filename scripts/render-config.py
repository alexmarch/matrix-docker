#!/usr/bin/env python3
import json
import ipaddress
import os
import re
from pathlib import Path

import yaml


ROOT = Path("/templates")
GENERATED = Path("/generated")
DATA = Path("/data")


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("REPLACE_WITH_"):
        raise SystemExit(f"Set a real value for {name} in .env")
    return value


def secret(name: str) -> str:
    value = required(name)
    if not re.fullmatch(r"[0-9a-fA-F]{64,}", value):
        raise SystemExit(f"{name} must be at least 32 bytes of hexadecimal text")
    return value


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", json.dumps(value))
    leftovers = re.findall(r"@[A-Z0-9_]+@", template)
    if leftovers:
        raise SystemExit(f"Unresolved template values: {', '.join(sorted(set(leftovers)))}")
    return template


def render_plain(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        if not re.fullmatch(r"[A-Za-z0-9./:_-]+", value):
            raise SystemExit(f"Unsafe characters in {key}")
        template = template.replace(f"@{key}@", value)
    leftovers = re.findall(r"@[A-Z0-9_]+@", template)
    if leftovers:
        raise SystemExit(f"Unresolved template values: {', '.join(sorted(set(leftovers)))}")
    return template


matrix_server = required("MATRIX_SERVER_NAME")
element_domain = required("ELEMENT_DOMAIN")
admin_domain = required("ADMIN_DOMAIN")
turn_domain = required("TURN_DOMAIN")
try:
    turn_public_ip = ipaddress.IPv4Address(required("TURN_PUBLIC_IP"))
except ValueError as exc:
    raise SystemExit(
        "TURN_PUBLIC_IP must be set to the server's public IPv4 address "
        "(replace the example value in .env)"
    ) from exc
if not turn_public_ip.is_global:
    raise SystemExit(
        f"TURN_PUBLIC_IP={turn_public_ip} is not a globally routable IPv4 address. "
        "Set it to the server's public IPv4 address, not a private/Docker IP "
        "or the documentation example 203.0.113.10."
    )

postgres_password = secret("POSTGRES_PASSWORD")
turn_secret = secret("TURN_SHARED_SECRET")
registration_secret = secret("REGISTRATION_SHARED_SECRET")

values = {
    "MATRIX_BASE_URL": f"https://{matrix_server}/",
    "MATRIX_SERVER_NAME": matrix_server,
    "ELEMENT_ORIGIN": f"https://{element_domain}",
    "ADMIN_ORIGIN": f"https://{admin_domain}",
    "POSTGRES_PASSWORD": postgres_password,
    "REGISTRATION_SHARED_SECRET": registration_secret,
    "TURN_SHARED_SECRET": turn_secret,
    "TURN_DOMAIN": turn_domain,
    "TURN_EXTERNAL_IP": f"{turn_public_ip}/172.29.0.10",
    "TURN_URI_UDP": f"turn:{turn_domain}:3478?transport=udp",
    "TURN_URI_TCP": f"turn:{turn_domain}:3478?transport=tcp",
}

config_path = DATA / "homeserver.yaml"
if not config_path.exists():
    raise SystemExit("Synapse config is missing. Run the synapse-generate step first.")

config = yaml.safe_load(config_path.read_text())
if not isinstance(config, dict):
    raise SystemExit("Generated Synapse config is not a YAML mapping.")

settings = yaml.safe_load(render((ROOT / "synapse-settings.yaml").read_text(), values))
config.update(settings)
config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))

element = render((ROOT / "element-config.json").read_text(), values)
json.loads(element)
(GENERATED / "element-config.json").write_text(element)
(GENERATED / "turnserver.conf").write_text(render_plain(
    (ROOT / "turnserver.conf").read_text(),
    {
        "TURN_SHARED_SECRET": turn_secret,
        "TURN_DOMAIN": turn_domain,
        "TURN_EXTERNAL_IP": f"{turn_public_ip}/172.29.0.10",
    },
))
