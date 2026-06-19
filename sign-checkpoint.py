#!/usr/bin/env python3
"""
sign-checkpoint.py — Opalyx signed-checkpoint tool.

WHAT THIS IS
    Opalyx supports operator-signed "sync checkpoints": a node can be told
    (via -synccheckpoint=HEIGHT:BLOCKHASH:SIGHEX) that a particular block hash
    is canonical at a particular height, signed by a project master key. The
    daemon verifies the signature against a compiled-in master public key
    (g_strCheckpointMasterPubKey in src/checkpointsync.cpp) and then refuses
    blocks that conflict with the checkpoint at that height. See SECURITY.md.

    This tool does two jobs:
      genkey   -> create a new secp256k1 master keypair. Print the PUBLIC key
                  to paste into src/checkpointsync.cpp before mainnet, and the
                  PRIVATE key to store OFFLINE (hardware token / air-gapped).
      sign     -> given the private key, a height and a block hash, emit the
                  exact -synccheckpoint=... string to hand to node operators.

    The signature scheme matches the daemon:
        payload = int32_le(height) || reverse(bytes.fromhex(blockhash))
        digest  = SHA256(SHA256(payload))        (Bitcoin "Hash")
        sig     = ECDSA(privkey, digest)         (DER, low-S)
    The daemon calls CPubKey::Verify(Hash(payload), sig).

DEPENDENCY
    Requires the `coincurve` package (libsecp256k1 bindings), which produces
    DER-encoded, low-S signatures compatible with the daemon's verifier:
        pip install coincurve

USAGE
    ./sign-checkpoint.py genkey
    ./sign-checkpoint.py sign --privkey HEX --height 50000 --blockhash HEX

SECURITY
    * The private key signs authority over the chain tip selection. Treat it
      like a release-signing key: generate on an air-gapped machine, never
      commit it, never paste it into a shell on a networked box if avoidable.
    * Rotating the key requires shipping a new binary (the pubkey is compiled
      in). That is intentional — see ROADMAP.md for planned P2P relay + RPC.
"""
import argparse
import hashlib
import struct
import sys


def dsha256(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def checkpoint_payload(height: int, blockhash_hex: str) -> bytes:
    # int32 little-endian height, then the block hash in internal byte order
    # (RPC/explorer display is big-endian, so reverse it).
    raw = bytes.fromhex(blockhash_hex)
    if len(raw) != 32:
        raise SystemExit(f"blockhash must be 32 bytes (64 hex chars), got {len(raw)}")
    internal = raw[::-1]
    return struct.pack("<i", height) + internal


def need_coincurve():
    try:
        import coincurve  # noqa: F401
        return coincurve
    except ImportError:
        raise SystemExit(
            "This command needs the 'coincurve' package:\n"
            "    pip install coincurve\n"
            "coincurve wraps libsecp256k1 and emits DER/low-S signatures that\n"
            "match the daemon's CPubKey::Verify()."
        )


def cmd_genkey(_args):
    cc = need_coincurve()
    priv = cc.PrivateKey()
    privkey_hex = priv.secret.hex()
    # compressed public key (33 bytes) — this is what CPubKey expects
    pub_hex = priv.public_key.format(compressed=True).hex()
    print("# --- Opalyx checkpoint master keypair ---")
    print("# 1. Store this PRIVATE key offline. Never commit it.")
    print(f"PRIVKEY={privkey_hex}")
    print()
    print("# 2. Paste this PUBLIC key into src/checkpointsync.cpp:")
    print(f'#    std::string g_strCheckpointMasterPubKey = "{pub_hex}";')
    print(f"PUBKEY={pub_hex}")
    print()
    print("# (66 hex chars = 33-byte compressed pubkey. The shipped default is")
    print("#  all-zeros and is intentionally INVALID so unsigned chains can't be")
    print("#  spoofed before you set a real key.)")


def cmd_sign(args):
    cc = need_coincurve()
    payload = checkpoint_payload(args.height, args.blockhash)
    digest = dsha256(payload)
    priv = cc.PrivateKey(bytes.fromhex(args.privkey))
    # sign the 32-byte digest directly (no extra hashing) with low-S DER output,
    # matching CPubKey::Verify(Hash(payload), sig).
    der_sig = priv.sign(digest, hasher=None)
    sig_hex = der_sig.hex()

    # sanity: verify locally before emitting
    pub = priv.public_key
    if not pub.verify(der_sig, digest, hasher=None):
        raise SystemExit("internal error: signature failed self-verify")

    arg = f"{args.height}:{args.blockhash}:{sig_hex}"
    print("# Hand this to node operators (opalyx.conf or command line):")
    print(f"synccheckpoint={arg}")
    print()
    print("# Equivalent CLI flag:")
    print(f"-synccheckpoint={arg}")


def main():
    ap = argparse.ArgumentParser(description="Opalyx signed-checkpoint tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("genkey", help="generate a new master keypair")

    sp = sub.add_parser("sign", help="sign a height:blockhash checkpoint")
    sp.add_argument("--privkey", required=True, help="master private key (hex)")
    sp.add_argument("--height", type=int, required=True)
    sp.add_argument("--blockhash", required=True,
                    help="block hash as shown by getblockhash (big-endian hex)")

    args = ap.parse_args()
    if args.cmd == "genkey":
        cmd_genkey(args)
    elif args.cmd == "sign":
        cmd_sign(args)


if __name__ == "__main__":
    main()
