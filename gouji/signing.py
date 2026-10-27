"""Ed25519 keys for the two parties that can authorise money: the controller, who signs the payment
policy, and the notary, which signs execution contracts.

A private key lives in keys/<name>.key (git-ignored) and stays with the party that owns it; the public
half in keys/<name>.pub is all anyone else needs. The agent holds neither private key, and the payment
gateway holds only the notary's public key.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def keys_dir() -> Path:
    return Path(os.environ.get("GOUJI_KEYS", "keys"))


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_hex(pub: Ed25519PublicKey) -> str:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def fingerprint(pub: Ed25519PublicKey) -> str:
    return sha256(bytes.fromhex(public_hex(pub)))[:16]


def private_key(name: str, *, create: bool = True, keys: Path | None = None) -> Ed25519PrivateKey:
    """Load keys/<name>.key, or make a fresh key pair when there is none and `create` is set."""
    d = keys or keys_dir()
    path = d / f"{name}.key"
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{path} is not an Ed25519 key")
    elif create:
        key = Ed25519PrivateKey.generate()
        d.mkdir(parents=True, exist_ok=True)
        path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    else:
        raise FileNotFoundError(f"no private key {path}")
    pub = d / f"{name}.pub"
    if not pub.exists() or pub.read_text(encoding="ascii").strip() != public_hex(key.public_key()):
        pub.write_text(public_hex(key.public_key()) + "\n", encoding="ascii")
    return key


def public_key(name: str, keys: Path | None = None) -> Ed25519PublicKey:
    path = (keys or keys_dir()) / f"{name}.pub"
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(path.read_text(encoding="ascii").strip()))


def trusted_publics(name: str, keys: Path | None = None) -> list[Ed25519PublicKey]:
    """The public keys a verifier trusts for a party: keys/<name>.pub, if this machine has one, and every
    keys/trusted/<name>-*.pub (for instance the notary that signed the example proofs in the repository)."""
    d = keys or keys_dir()
    paths = [d / f"{name}.pub"] + sorted((d / "trusted").glob(f"{name}-*.pub"))
    return [Ed25519PublicKey.from_public_bytes(bytes.fromhex(p.read_text(encoding="ascii").strip()))
            for p in paths if p.exists()]


def sign(key: Ed25519PrivateKey, data: bytes) -> str:
    return key.sign(data).hex()


def verify(pub: Ed25519PublicKey, data: bytes, signature: str) -> bool:
    try:
        pub.verify(bytes.fromhex(signature), data)
        return True
    except (InvalidSignature, ValueError):
        return False


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def cell_text(value: Any) -> str:
    """A cell value as text that is the same whichever backend read it (DuckDB or Zetaris)."""
    s = str(value)
    return s[:19].replace("T", " ") if isinstance(value, datetime) or _ISO.match(s) else s
