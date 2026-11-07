#!/usr/bin/env python3
"""Build a Voxy jar with the macOS ARM64 native libraries it omits.

Voxy (all-rights-reserved, https://github.com/MCRcortex/voxy) ships a RocksDB
jar stripped of every native library except linux64 and win64 (see the
`makeExcludedRocksDB` task in its build.gradle), and it ships the LWJGL lmdb
and zstd natives for linux and windows only. On macOS arm64 the mod therefore
dies during world join with:

    java.lang.RuntimeException: librocksdbjni-osx-arm64.jnilib was not found inside JAR.

Once that is fixed, the default ZSTD compressor (LWJGL zstd) is the next
UnsatisfiedLinkError. Both are one missing native library each, and both are
libraries Voxy already declares as its own dependencies.

This tool downloads the official Voxy build from Modrinth, adds the three
official macOS natives, and writes the result into dist/. It builds an
installable jar and nothing else: it never looks for, opens, or modifies any
Minecraft installation, and installing the result is a separate step done by
hand. That keeps the tool a producer of a file rather than something that
reaches into other people's instances.

It also applies a local render workaround for Zink/KosmicKrisp: Voxy's
AsyncNodeManager packs scatter-write locations with the buffer select in
the top bit, and on this stack every compute store selected that way is
lost, so no section metadata ever reaches the GPU and no LOD draws are
built. The patched jar packs the select in the low bit instead (three
instructions in AsyncNodeManager) with the matching two-line change in
voxy:util/scatter.comp; that packing is verified headless to land every
write exactly. Same rules as the natives: local machine only, never
redistributed.

Nothing is redistributed: Voxy is all-rights-reserved with "do not
redistribute", and its Modrinth page permits bundling only the unmodified
release and explicitly excludes unofficial versions. The jar this produces is
for the machine that built it.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import socket
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# ----------------------------------------------------------------- upstream

# The exact build this tool knows how to patch. A new Voxy release can move the
# nested jar layout, so every download is hash-checked rather than assumed.
VOXY_FILENAME = "voxy-0.2.19-beta.jar"
VOXY_VERSION = "0.2.19-beta"
VOXY_URL = (
    "https://cdn.modrinth.com/data/fxxUqruK/versions/LzyXnE51/"
    "voxy-0.2.19-beta.jar"
)
VOXY_SHA512 = (
    "9071acefff00f952b049134f7ee8b5c8be27646ade992274f9a32e4adf7ad0932"
    "f9755530fa212a8e65cc23b3ed5dc643af139be83fcb89c778d8c8e723b9c3a"
)

# Native libraries that Voxy already depends on, from their own upstreams.
# rocksdbjni is dual Apache-2.0 / GPL-2.0 (see the artifact pom); LWJGL is BSD-3.
NESTED_ROCKSDB = "META-INF/jars/rocksdbjni-10.2.1.jar"
ROCKSDB_URL = (
    "https://repo1.maven.org/maven2/org/rocksdb/rocksdbjni/10.2.1/"
    "rocksdbjni-10.2.1-osx.jar"
)
ROCKSDB_SHA512 = (
    "f728d5702d2477e976e9a93e8a6be2c86cc3693f8d411408e490026714fde1c354"
    "e8be6ee3b447df7b3ea5ac7d519cc03a6f083dee65007f7ee0c6954e087e36"
)
ROCKSDB_NATIVE = "librocksdbjni-osx-arm64.jnilib"

ZSTD_URL = (
    "https://repo1.maven.org/maven2/org/lwjgl/lwjgl-zstd/3.4.1/"
    "lwjgl-zstd-3.4.1-natives-macos-arm64.jar"
)
ZSTD_SHA512 = (
    "6645fb87e80a9611f20a6dc5cb7a72c459978b7e9ef1859b9b747a2b64312e3163"
    "ca7315c86e16a340f8018b5633e432de2ddf06e3f913b73e105a62ae912621"
)
ZSTD_ENTRY = "META-INF/jars/lwjgl-zstd-3.4.1-natives-macos-arm64.jar"

LMDB_URL = (
    "https://repo1.maven.org/maven2/org/lwjgl/lwjgl-lmdb/3.4.1/"
    "lwjgl-lmdb-3.4.1-natives-macos-arm64.jar"
)
LMDB_SHA512 = (
    "146d6cca64ac12d796c89b14121886a23bcdd06c3a82ec2049cbfb79146b9de8b63"
    "55c6a538593fe61c6766e6c4f149e978dc81c64c6a9d7f95424239c1aa0aa"
)
LMDB_ENTRY = "META-INF/jars/lwjgl-lmdb-3.4.1-natives-macos-arm64.jar"

# How a patched build is recognised, by this tool and by anyone reading the jar.
MARKER_KEY = "macos_arm64_native_patch"
MARKER_VALUE = "rocksdbjni osx-arm64 jni + lwjgl zstd/lmdb macos natives"
SCATTER_MARKER_KEY = "scatter_lsb_workaround"
SCATTER_MARKER_VALUE = (
    "AsyncNodeManager scatter locations use low-bit buffer select "
    "(scatter.comp reads loc&1 / loc>>1); works around lost "
    "top-bit-conditional SSBO stores on Zink/KosmicKrisp"
)

# Display metadata for the patched build. The mod id ("voxy") and version stay
# exactly as upstream shipped them: Fabric resolves dependencies, mixins and
# configs by id, and other mods may pin the version. Only the human-facing
# fields change, so the build is visibly not the official one. Authorship is
# split truthfully rather than merged: Cortex wrote Voxy, glmtlmc only added
# the missing natives, and neither endorses the other.
PATCH_NAME = "Voxy GLMTLMC Patches"
PATCH_AUTHORS = [
    {"name": "MCRcortex", "contact": {"sources": "https://github.com/MCRcortex/voxy"}},
    {"name": "glmtlmc (unofficial macOS native patch)"},
]
PATCH_DESCRIPTION = (
    "Unofficial macOS ARM64 build of Voxy: the official mod plus the Apple "
    "Silicon native libraries it omits, plus a local scatter-upload workaround "
    "for Zink/KosmicKrisp (low-bit buffer select; see scatter_lsb_workaround). "
    "Do not redistribute. Not affiliated "
    "with, endorsed by, or supported by Cortex (MCRcortex), the author of Voxy."
)

# Entries this tool rewrites (everything else is copied untouched).
SCATTER_COMP_PATH = "assets/voxy/shaders/util/scatter.comp"
ASYNC_NODE_MANAGER = (
    "me/cortex/voxy/client/core/rendering/hierachical/AsyncNodeManager.class"
)
ASYNC_NODE_MANAGER_SYNC_RESULTS = (
    "me/cortex/voxy/client/core/rendering/hierachical/"
    "AsyncNodeManager$SyncResults.class"
)

# The two derivation lines of voxy:util/scatter.comp, before and after.
# Only these lines change; the branch itself is identical. The low-bit form
# is the one verified headless against this stack (all metadata and node
# writes land exactly); the top-bit form loses every write whose selector
# has the top bit set.
SCATTER_OLD_DERIVE = (
    "    uint writeBuffer = writeLocation>>31;//Top bit indicates what buffer to write to\n"
    "    writeLocation &= (1u<<31)-1;//Remove the buffer bit\n"
)
SCATTER_NEW_DERIVE = (
    "    uint writeBuffer = writeLocation & 1u;//Low bit indicates what buffer to write to\n"
    "    writeLocation = writeLocation >> 1;//Remove the buffer bit\n"
)

# Every jar this tool writes is bit-for-bit reproducible: entries that already
# exist keep their own timestamp and compression, and the new ones get this one.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)

OUTPUT_NAME = "voxy-0.2.19-beta-macos-arm64.jar"


def log(message: str = "") -> None:
    print(message, flush=True)


def sha512_hex(data: bytes) -> str:
    return hashlib.sha512(data).hexdigest()


# ------------------------------------------------- class-file patching
# Voxy's AsyncNodeManager packs scatter-write locations with the buffer select
# in the top bit: meta halves go to (val<<1)|(1<<31) and +(that)+1, node writes
# go to val unwrapped, and voxy:util/scatter.comp splits on writeLocation>>31.
# On this stack a compute store whose index derives from a top-bit-set value,
# inside a branch taken on that top bit, never lands (verified headless down
# to the exact shader and packing: every metadata write is lost, so Voxy
# builds zero draw commands and renders nothing). The low-bit packing below
# is verified headless to land every write exactly: meta halves go to
# (val<<2)|1 and (val<<2)|3, node writes go to (val<<1), and the shader
# splits on loc&1 / loc>>1. Nothing else reads this encoding: the TLN
# add/remove and cleaner bit-31 markers live in separate CPU-side sets and
# are left alone.
#
# Three sites, all in AsyncNodeManager's output section except the tiny
# single-arg getScatterWritePtr overload in SyncResults:
#   P1  int scatterAddr = (val<<1)|(1<<31)  ->  (val<<2)|1
#   P2  getScatterWritePtr(scatterAddr+1, 0) -> getScatterWritePtr(scatterAddr+2, 0)
#   P3  getScatterWritePtr(val)              -> getScatterWritePtr(val<<1)
# P1 and P2 are same-size byte swaps (P1 pads with two nops). P3 grows one
# tiny branch-free method by two bytes; that method has no exception table
# and no stack map, so nothing else needs adjusting. Every pattern is
# required to occur exactly once and every referenced constant/method is
# checked, so an unexpected upstream build fails loudly instead of patching
# the wrong bytes.

def _u16(data: bytes, off: int) -> int:
    return (data[off] << 8) | data[off + 1]


def _u32(data: bytes, off: int) -> int:
    return (data[off] << 24) | (data[off + 1] << 16) | (data[off + 2] << 8) | data[off + 3]


def _parse_constant_pool(data: bytes):
    """Return (entries, end_off). entries is 1-based; long/double leave a None hole."""
    if data[0:4] != b"\xca\xfe\xba\xbe":
        raise RuntimeError("not a Java class file (bad magic)")
    count = _u16(data, 8)
    entries: list = [None]
    off = 10
    i = 1
    while i < count:
        tag = data[off]
        if tag == 1:
            ln = _u16(data, off + 1)
            entries.append(("Utf8", data[off + 3:off + 3 + ln]))
            off += 3 + ln
        elif tag in (3, 4):
            entries.append(("IntOrFloat", tag, _u32(data, off + 1)))
            off += 5
        elif tag in (5, 6):
            entries.append(("LongOrDouble", tag, data[off + 1:off + 9]))
            off += 9
            entries.append(None)
            i += 1
        elif tag in (7, 8, 16, 19, 20):
            entries.append(("Idx1", tag, _u16(data, off + 1)))
            off += 3
        elif tag in (9, 10, 11, 12, 17, 18):
            entries.append(("Idx2", tag, _u16(data, off + 1), _u16(data, off + 3)))
            off += 5
        elif tag == 15:
            entries.append(("Handle", data[off + 1], _u16(data, off + 2)))
            off += 4
        else:
            raise RuntimeError(f"unknown constant-pool tag {tag} at index {i}")
        i += 1
    return entries, off


def _cp_utf8(entries, idx: int) -> bytes:
    entry = entries[idx]
    if entry is None or entry[0] != "Utf8":
        raise RuntimeError(f"constant-pool #{idx} is not a Utf8")
    return entry[1]


def _iter_methods(data: bytes, entries, cp_end):
    """Yield dicts with name/desc bytes and attribute spans for each method."""
    off = cp_end + 6
    n_if = _u16(data, off)
    off += 2 + 2 * n_if
    n_fields = _u16(data, off)
    off += 2
    for _ in range(n_fields):
        n_attrs = _u16(data, off + 6)
        off += 8
        for _ in range(n_attrs):
            off += 6 + _u32(data, off + 2)
    n_methods = _u16(data, off)
    off += 2
    methods = []
    for _ in range(n_methods):
        name_idx = _u16(data, off + 2)
        desc_idx = _u16(data, off + 4)
        n_attrs = _u16(data, off + 6)
        off += 8
        attrs = []
        for _ in range(n_attrs):
            attrs.append((_u16(data, off), off, _u32(data, off + 2)))
            off += 6 + _u32(data, off + 2)
        methods.append({"name": _cp_utf8(entries, name_idx),
                        "desc": _cp_utf8(entries, desc_idx), "attrs": attrs})
    return methods


def _code_spans(data: bytes, entries, method):
    """Parse one method's Code attribute; return offsets of its parts."""
    code_attr = None
    for name_idx, off, _ in method["attrs"]:
        if _cp_utf8(entries, name_idx) == b"Code":
            code_attr = off
            break
    if code_attr is None:
        raise RuntimeError(f"method {method['name']} has no Code attribute")
    max_stack = _u16(data, code_attr + 6)
    code_length = _u32(data, code_attr + 10)
    code_start = code_attr + 14
    p = code_start + code_length
    n_exc = _u16(data, p)
    p += 2
    exc = []
    for _ in range(n_exc):
        exc.append((_u16(data, p), _u16(data, p + 2), _u16(data, p + 4)))
        p += 8
    n_attrs = _u16(data, p)
    p += 2
    sub: dict = {}
    for _ in range(n_attrs):
        sub[_cp_utf8(entries, _u16(data, p))] = (p, _u32(data, p + 2))
        p += 6 + _u32(data, p + 2)
    return {"attr_off": code_attr, "max_stack": max_stack,
            "code_start": code_start, "code_length": code_length,
            "exc": exc, "sub": sub}


def _skip_vti(data: bytes, p: int) -> int:
    """Skip one verification_type_info at p; return the next offset."""
    tag = data[p]
    p += 1
    if tag in (7, 8):
        p += 2
    elif tag > 8:
        raise RuntimeError(f"bad verification_type_info tag {tag}")
    return p


def _stack_map_targets(data: bytes, spans) -> list:
    """Absolute code offsets of every StackMapTable frame in a Code attribute."""
    if b"StackMapTable" not in spans["sub"]:
        return []
    off, _ = spans["sub"][b"StackMapTable"]
    n = _u16(data, off + 6)
    p = off + 8
    deltas = []
    for _ in range(n):
        frame = data[p]
        p += 1
        if frame <= 63:
            deltas.append(frame)
        elif frame <= 127:
            deltas.append(frame - 64)
            p = _skip_vti(data, p)
        elif frame == 247:
            deltas.append(_u16(data, p))
            p = _skip_vti(data, p + 2)
        elif 248 <= frame <= 251:
            # chop_frame (248..250) and same_frame_extended (251): both carry
            # only an offset_delta.
            deltas.append(_u16(data, p))
            p += 2
        elif 252 <= frame <= 254:
            # append_frame with frame-251 additional locals.
            deltas.append(_u16(data, p))
            p += 2
            for _ in range(frame - 251):
                p = _skip_vti(data, p)
        elif frame == 255:
            deltas.append(_u16(data, p))
            p += 2
            n_locals = _u16(data, p)
            p += 2
            for _ in range(n_locals):
                p = _skip_vti(data, p)
            n_stack = _u16(data, p)
            p += 2
            for _ in range(n_stack):
                p = _skip_vti(data, p)
        else:
            raise RuntimeError(f"bad StackMapTable frame_type {frame}")
    targets = []
    cur = -1
    for delta in deltas:
        cur += delta + 1
        targets.append(cur)
    if len(targets) != n:
        raise RuntimeError("StackMapTable parse miscounted frames")
    return targets


def _find_method(data: bytes, entries, name: bytes, desc: bytes):
    methods = _iter_methods(data, entries, _parse_constant_pool(data)[1])
    found = [m for m in methods if m["name"] == name and m["desc"] == desc]
    if len(found) != 1:
        raise RuntimeError(f"expected one method {name!r} {desc!r}, found {len(found)}")
    return found[0]


def _patch_async_node_manager(class_bytes: bytes) -> bytes:
    out = bytearray(class_bytes)
    entries, _ = _parse_constant_pool(class_bytes)

    # P1: iload 8; iconst_1; ishl; ldc_w <int -2147483648>; ior; istore 9
    p1 = []
    for i in range(len(out) - 10):
        if (out[i] == 0x15 and out[i + 1] == 0x08 and out[i + 2] == 0x04
                and out[i + 3] == 0x78 and out[i + 4] == 0x13
                and out[i + 7] == 0x80 and out[i + 8] == 0x36 and out[i + 9] == 0x09):
            p1.append(i)
    if len(p1) != 1:
        raise RuntimeError(f"P1 scatter-addr pattern found {len(p1)} times, need exactly 1")
    const_idx = (out[p1[0] + 5] << 8) | out[p1[0] + 6]
    const_entry = entries[const_idx]
    if const_entry[0] != "IntOrFloat" or const_entry[1] != 3 or const_entry[2] != 0x80000000:
        raise RuntimeError("P1 constant is not int -2147483648; refusing to patch")
    _assert_range_clear(class_bytes, entries, p1[0], p1[0] + 10)
    # (val<<2)|1 with two nop pads: same 10 bytes, no offset moves.
    out[p1[0] + 2:p1[0] + 8] = bytes([0x05, 0x78, 0x04, 0x80, 0x00, 0x00])

    # P2: iload 9; iconst_1; iadd; iconst_0; invokevirtual getScatterWritePtr(II)J
    p2 = []
    for i in range(len(out) - 8):
        if (out[i] == 0x15 and out[i + 1] == 0x09 and out[i + 2] == 0x04
                and out[i + 3] == 0x60 and out[i + 4] == 0x03 and out[i + 5] == 0xB6):
            p2.append(i)
    if len(p2) != 1:
        raise RuntimeError(f"P2 scatter-addr+1 pattern found {len(p2)} times, need exactly 1")
    method_idx = (out[p2[0] + 6] << 8) | out[p2[0] + 7]
    ref = entries[method_idx]
    cls_name = _cp_utf8(entries, entries[ref[2]][2])
    nat = ref[3]
    meth_name = _cp_utf8(entries, entries[nat][2])
    meth_desc = _cp_utf8(entries, entries[nat][3])
    if (cls_name != b"me/cortex/voxy/client/core/rendering/hierachical/AsyncNodeManager$SyncResults"
            or meth_name != b"getScatterWritePtr" or meth_desc != b"(II)J"):
        raise RuntimeError("P2 call target is not SyncResults.getScatterWritePtr(II)J")
    out[p2[0] + 2] = 0x05  # iconst_1 -> iconst_2: scatterAddr+1 becomes +2
    return bytes(out)


def _assert_range_clear(class_bytes: bytes, entries, start: int, end: int) -> None:
    """No exception range, branch target, or stack-map frame may begin inside
    (start, end): the P1 rewrite keeps the size but changes which offsets are
    instruction starts, so interior references would go stale."""
    methods = _iter_methods(class_bytes, entries, _parse_constant_pool(class_bytes)[1])
    for method in methods:
        code_attrs = [a for a in method["attrs"]
                      if _cp_utf8(entries, a[0]) == b"Code"]
        for _, attr_off, _ in code_attrs:
            spans = _code_spans(class_bytes, entries,
                                {"name": method["name"], "desc": method["desc"],
                                 "attrs": method["attrs"]})
            for frm, to, target in spans["exc"]:
                for edge in (frm, to, target):
                    if start < edge < end:
                        raise RuntimeError(
                            f"exception-table edge {edge} inside patch range")
            for target in _stack_map_targets(class_bytes, spans):
                if start < target < end:
                    raise RuntimeError(
                        f"stack-map frame at {target} inside patch range")
            # Branch targets: every branch opcode's destination must also
            # avoid the interior. Scan the code linearly with operand widths.
            code = class_bytes[spans["code_start"]:spans["code_start"] + spans["code_length"]]
            base = spans["code_start"]
            for absolute in _branch_targets(code):
                if start < base + absolute < end:
                    raise RuntimeError(
                        f"branch target {base + absolute} inside patch range")


def _branch_targets(code: bytes) -> list:
    """Code-relative destinations of all branches/switches in raw bytecode."""
    targets = []
    i = 0
    n = len(code)
    while i < n:
        op = code[i]
        if 0x99 <= op <= 0xA8 or op in (0xC6, 0xC7):  # if*, goto, jsr + null checks
            dest = i + int.from_bytes(code[i + 1:i + 3], "big", signed=True)
            targets.append(dest)
            i += 3
        elif op == 0xC8 or op == 0xC9:  # goto_w, jsr_w
            dest = i + int.from_bytes(code[i + 1:i + 5], "big", signed=True)
            targets.append(dest)
            i += 5
        elif op == 0xAA:  # tableswitch
            pad = (4 - ((i + 1) % 4)) % 4
            j = i + 1 + pad
            default = int.from_bytes(code[j:j + 4], "big", signed=True)
            targets.append(i + default)
            low = int.from_bytes(code[j + 4:j + 8], "big", signed=True)
            high = int.from_bytes(code[j + 8:j + 12], "big", signed=True)
            j += 12
            for _ in range(high - low + 1):
                targets.append(i + int.from_bytes(code[j:j + 4], "big", signed=True))
                j += 4
            i = j
        elif op == 0xAB:  # lookupswitch
            pad = (4 - ((i + 1) % 4)) % 4
            j = i + 1 + pad
            targets.append(i + int.from_bytes(code[j:j + 4], "big", signed=True))
            pairs = int.from_bytes(code[j + 4:j + 8], "big", signed=True)
            j += 8
            for _ in range(pairs):
                targets.append(i + int.from_bytes(code[j + 4:j + 8], "big", signed=True))
                j += 8
            i = j
        else:
            i += 1 + _operand_width(code, i)
    return targets


def _operand_width(code: bytes, i: int) -> int:
    """Immediate-operand bytes after the opcode at i (0 if none)."""
    op = code[i]
    if op == 0xB9:  # invokeinterface
        return 4
    if op in (0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xBB, 0xBD,
              0xC0, 0xC1, 0xC3, 0xC5):
        # field/method/invoke refs, class ops, checkcast, instanceof,
        # new, anewarray, multianewarray prefix
        if op == 0xC5:
            return 3
        return 2
    if op in (0x13, 0x14):  # ldc_w, ldc2_w
        return 2
    if op == 0x12:  # ldc
        return 1
    if op == 0x10:  # bipush
        return 1
    if op == 0x11:  # sipush
        return 2
    if op == 0xBC:  # newarray
        return 1
    if op in (0x15, 0x16, 0x17, 0x18, 0x19, 0x36, 0x37, 0x38, 0x39, 0x3A, 0xA9):
        return 1
    if op == 0x84:  # iinc
        return 2
    if op == 0xC4:  # wide: variable width, refuse to guess
        raise RuntimeError("wide opcode inside scanned code; refusing to scan")
    return 0


def _patch_sync_results(class_bytes: bytes) -> bytes:
    """getScatterWritePtr(int) delegates to the (int,int) overload with
    ensureExtra 0. Shift the location left by one (node flag 0) inside the
    delegate: the method is seven branch-free bytes with no exception table
    and no stack map, so growing it by two bytes moves nothing else."""
    out = bytearray(class_bytes)
    entries, _ = _parse_constant_pool(class_bytes)
    method = _find_method(class_bytes, entries, b"getScatterWritePtr", b"(I)J")
    spans = _code_spans(class_bytes, entries, method)
    if spans["code_length"] != 7:
        raise RuntimeError("P3 method body is not the expected 7 bytes")
    code = bytes(out[spans["code_start"]:spans["code_start"] + 7])
    if not (code[0] == 0x2A and code[1] == 0x1B and code[2] == 0x03
            and code[3] == 0xB6 and code[6] == 0xAD):
        raise RuntimeError("P3 method body is not aload_0/iload_1/iconst_0/invoke/lreturn")
    ref_idx = (code[4] << 8) | code[5]
    ref = entries[ref_idx]
    nat = ref[3]
    if (_cp_utf8(entries, entries[nat][2]) != b"getScatterWritePtr"
            or _cp_utf8(entries, entries[nat][3]) != b"(II)J"):
        raise RuntimeError("P3 delegate is not getScatterWritePtr(II)J")
    if spans["exc"]:
        raise RuntimeError("P3 method has an exception table; refusing to grow it")
    if b"StackMapTable" in spans["sub"]:
        raise RuntimeError("P3 method has a stack map; refusing to grow it")
    if spans["max_stack"] < 3:
        raise RuntimeError("P3 method stack depth is under 3")
    # Debug tables first (same-size edits). LineNumberTable entries are
    # (start_pc, line) pairs with no length field, so the asserted single
    # entry at start_pc 0 needs no change (the insertion point sits after
    # it); LocalVariableTable lengths go 7 -> 9.
    sub = spans["sub"]
    if b"LineNumberTable" in sub:
        off, _ = sub[b"LineNumberTable"]
        count = _u16(out, off + 6)
        if count != 1:
            raise RuntimeError("P3 LineNumberTable shape changed; refusing to grow it")
        if _u16(out, off + 8) != 0:
            raise RuntimeError("P3 LineNumberTable shape changed; refusing to grow it")
    if b"LocalVariableTable" in sub:
        off, _ = sub[b"LocalVariableTable"]
        count = _u16(out, off + 6)
        for k in range(count):
            base = off + 8 + 10 * k
            if _u16(out, base) != 0 or _u16(out, base + 2) != 7:
                raise RuntimeError("P3 LocalVariableTable shape changed")
            out[base + 2] = 0
            out[base + 3] = 9
    # Insert iconst_1/ishl after iload_1 (code offset 2). The slice assignment
    # grows the buffer by two, shifting the method tail automatically; nothing
    # else in the file references these offsets (no exception table, no stack
    # map, asserted above).
    insert_at = spans["code_start"] + 2
    out[insert_at:insert_at] = bytes([0x04, 0x78])
    attr_len = _u32(out, spans["attr_off"] + 2)
    out[spans["attr_off"] + 2:spans["attr_off"] + 6] = (
        (attr_len + 2).to_bytes(4, "big"))
    out[spans["attr_off"] + 10:spans["attr_off"] + 14] = (9).to_bytes(4, "big")
    return bytes(out)


def _patch_scatter_comp(source: bytes) -> bytes:
    text = source.decode("utf-8")
    if text.count(SCATTER_OLD_DERIVE) != 1:
        raise RuntimeError(
            "scatter.comp derivation lines not found exactly once; "
            "unexpected upstream shader")
    return text.replace(SCATTER_OLD_DERIVE, SCATTER_NEW_DERIVE).encode("utf-8")


# One stalled download looks exactly like a stuck tool, so downloads are
# chatty: progress lines while bytes arrive, a bounded wait when they don't,
# and retries on a fresh connection (which usually lands on a healthy CDN
# edge) before giving up.
CONNECT_TIMEOUT = 20
READ_TIMEOUT = 30
RETRIES = 3
CHUNK = 256 * 1024


def _prefer_ipv4() -> None:
    """Resolve IPv4 addresses first.

    Python's http client takes the first address getaddrinfo returns and
    never falls back; on networks with broken IPv6 egress that means hanging
    on an unreachable Fastly edge instead of using working IPv4. Sorting
    IPv4 first keeps these plain artifact downloads off the broken path.
    """
    original = socket.getaddrinfo

    def ipv4_first(host, port, family=0, *args, **kwargs):
        results = original(host, port, family, *args, **kwargs)
        results.sort(key=lambda entry: entry[0] != socket.AF_INET)
        return results

    socket.getaddrinfo = ipv4_first


def _read_with_progress(response, description: str) -> bytes:
    try:
        total = int(response.getheader("Content-Length") or 0)
    except (TypeError, ValueError):
        total = 0
    received = bytearray()
    started = last_report = time.monotonic()
    while True:
        try:
            chunk = response.read(CHUNK)
        except (socket.timeout, TimeoutError) as error:
            raise RuntimeError(
                f"download of {description} stalled with "
                f"{len(received)} of {total or '?'} bytes received"
            ) from error
        if not chunk:
            break
        received += chunk
        now = time.monotonic()
        if now - last_report >= 2.0:
            last_report = now
            elapsed = max(now - started, 0.001)
            rate = len(received) / elapsed / 1e6
            if total:
                log(f"    {len(received) / 1e6:.1f}/{total / 1e6:.1f} MB "
                    f"({100 * len(received) // total}%) @ {rate:.1f} MB/s")
            else:
                log(f"    {len(received) / 1e6:.1f} MB @ {rate:.1f} MB/s")
    return bytes(received)


def _download_once(url: str, description: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "glmtlmc-voxy-macos-patch/1"}
    )
    # urlopen's timeout only bounds connecting; bound the body reads too via
    # the socket default (this tool is single-purpose, nothing else shares it).
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(READ_TIMEOUT)
    try:
        with urllib.request.urlopen(request, timeout=CONNECT_TIMEOUT) as response:
            return _read_with_progress(response, description)
    finally:
        socket.setdefaulttimeout(previous_timeout)


def download(url: str, expected_sha512: str, description: str) -> bytes:
    """Fetch url, or fail loudly rather than patch the wrong bytes."""
    log(f"  downloading {description}")
    log(f"    {url}")
    _prefer_ipv4()
    data = None
    for attempt in range(1, RETRIES + 1):
        try:
            data = _download_once(url, description)
            break
        except (urllib.error.URLError, OSError, RuntimeError) as error:
            if attempt == RETRIES:
                raise RuntimeError(
                    f"could not download {description} after {RETRIES} "
                    f"attempts: {error}"
                ) from error
            log(f"    attempt {attempt} failed ({error}), retrying...")
            time.sleep(2 * attempt)
    assert data is not None

    digest = sha512_hex(data)
    if digest != expected_sha512:
        raise RuntimeError(
            f"{description} is not the build this tool pins\n"
            f"    expected sha512 {expected_sha512}\n"
            f"    downloaded sha512 {digest}\n"
            "  update the pins in build.py when a new voxy release needs patching"
        )
    log(f"    verified ({len(data)} bytes)")
    return data


def build_patched(
    voxy_bytes: bytes,
    rocksdb_native: bytes,
    zstd_bytes: bytes,
    lmdb_bytes: bytes,
) -> bytes:
    """The whole patch: three upstream libraries in, patched mod jar out."""
    with zipfile.ZipFile(io.BytesIO(voxy_bytes)) as archive:
        if NESTED_ROCKSDB not in archive.namelist():
            raise RuntimeError(
                f"{VOXY_FILENAME} contains no {NESTED_ROCKSDB}; this build is not "
                "the one this tool knows about"
            )
        metadata = json.loads(archive.read("fabric.mod.json").decode("utf-8"))

        # 1. the nested rocksdb jar gains the macOS arm64 jnilib it should carry
        nested = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive.read(NESTED_ROCKSDB))) as source, \
                zipfile.ZipFile(nested, "w") as target:
            for info in source.infolist():
                target.writestr(info, source.read(info.filename))
            # the nested jar is stored uncompressed upstream; keep it that way
            info = zipfile.ZipInfo(ROCKSDB_NATIVE, ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            target.writestr(info, rocksdb_native)

        # 2. the nested jars list has to name the two LWJGL natives jars
        presented = {entry.get("file") for entry in metadata.get("jars", [])}
        for entry in (ZSTD_ENTRY, LMDB_ENTRY):
            if entry not in presented:
                metadata.setdefault("jars", []).append({"file": entry})
        metadata.setdefault("custom", {})[MARKER_KEY] = MARKER_VALUE
        metadata["custom"].setdefault("patched_by", "glmtlmc mod-tools/VoxyMacPatch")
        metadata["custom"][SCATTER_MARKER_KEY] = SCATTER_MARKER_VALUE

        # 3. label the build honestly: same mod id and version (required), but a
        # distinct display name, truthful authorship, and a redistribution warning.
        metadata["name"] = PATCH_NAME
        metadata["authors"] = PATCH_AUTHORS
        metadata["description"] = PATCH_DESCRIPTION

        # 4. scatter-upload workaround (local render fix, see SCATTER_* above):
        # low-bit buffer select in the shader plus matching location packing
        # in AsyncNodeManager. Patched entries get the fixed timestamp so the
        # build stays reproducible.
        scatter_patched = _patch_scatter_comp(archive.read(SCATTER_COMP_PATH))
        manager_patched = _patch_async_node_manager(archive.read(ASYNC_NODE_MANAGER))
        sync_results_patched = _patch_sync_results(archive.read(ASYNC_NODE_MANAGER_SYNC_RESULTS))

        # 5. reassemble: every upstream entry untouched, metadata plus six
        # files changed.
        # writestr() honours the ZipInfo it is handed, not the archive's default
        # compression, so the compression is stated outright for the new ones.
        # Only the container around the nested jar is deflated: its entries
        # keep the uncompressed form upstream ships them in.
        rewritten = {
            "fabric.mod.json": (
                json.dumps(metadata, indent=4).encode("utf-8"),
                zipfile.ZIP_DEFLATED,
            ),
            NESTED_ROCKSDB: (nested.getvalue(), zipfile.ZIP_DEFLATED),
            SCATTER_COMP_PATH: (scatter_patched, zipfile.ZIP_DEFLATED),
            ASYNC_NODE_MANAGER: (manager_patched, zipfile.ZIP_DEFLATED),
            ASYNC_NODE_MANAGER_SYNC_RESULTS: (
                sync_results_patched, zipfile.ZIP_DEFLATED),
        }
        patched = io.BytesIO()
        with zipfile.ZipFile(patched, "w", zipfile.ZIP_DEFLATED) as target:
            for info in archive.infolist():
                if info.filename in rewritten:
                    continue
                target.writestr(info, archive.read(info.filename))
            for filename, (payload, _) in rewritten.items():
                target.writestr(
                    zipfile.ZipInfo(filename, ZIP_DATE),
                    payload,
                    compress_type=zipfile.ZIP_DEFLATED,
                )
            for entry, payload in ((ZSTD_ENTRY, zstd_bytes), (LMDB_ENTRY, lmdb_bytes)):
                target.writestr(
                    zipfile.ZipInfo(entry, ZIP_DATE),
                    payload,
                    compress_type=zipfile.ZIP_DEFLATED,
                )

    return patched.getvalue()


def _audit_scatter_classes(manager_bytes: bytes, sync_results_bytes: bytes) -> None:
    """Re-check patched classes: new patterns present exactly once each,
    old patterns gone, structural shapes as asserted during patching."""
    anm = bytearray(manager_bytes)
    old_p1 = bytes([0x15, 0x08, 0x04, 0x78, 0x13])
    new_p1 = bytes([0x15, 0x08, 0x05, 0x78, 0x04, 0x80, 0x00, 0x00])
    if _count_overlapping(anm, old_p1) != 0:
        raise RuntimeError("audit: old P1 scatter-addr sequence still present")
    if _count_overlapping(anm, new_p1) != 1:
        raise RuntimeError("audit: new P1 scatter-addr sequence not present exactly once")
    old_p2 = bytes([0x15, 0x09, 0x04, 0x60, 0x03, 0xB6])
    new_p2 = bytes([0x15, 0x09, 0x05, 0x60, 0x03, 0xB6])
    if _count_overlapping(anm, old_p2) != 0:
        raise RuntimeError("audit: old P2 scatter-addr+1 sequence still present")
    if _count_overlapping(anm, new_p2) != 1:
        raise RuntimeError("audit: new P2 scatter-addr+2 sequence not present exactly once")
    entries, _ = _parse_constant_pool(sync_results_bytes)
    method = _find_method(sync_results_bytes, entries, b"getScatterWritePtr", b"(I)J")
    spans = _code_spans(sync_results_bytes, entries, method)
    code = sync_results_bytes[spans["code_start"]:spans["code_start"] + spans["code_length"]]
    if not (len(code) == 9 and code[0] == 0x2A and code[1] == 0x1B
            and code[2] == 0x04 and code[3] == 0x78 and code[4] == 0x03
            and code[5] == 0xB6 and code[8] == 0xAD):
        raise RuntimeError("audit: P3 delegate is not aload/iload/iconst_1/ishl/iconst_0/invoke/lreturn")


def _count_overlapping(data: bytes, pattern: bytes) -> int:
    count = 0
    start = 0
    while True:
        hit = data.find(pattern, start)
        if hit < 0:
            return count
        count += 1
        start = hit + 1


def verify_patched(patched_bytes: bytes, rocksdb_native: bytes) -> None:
    """Reopen what was written and confirm the mod will find what it needs."""
    with zipfile.ZipFile(io.BytesIO(patched_bytes)) as archive:
        metadata = json.loads(archive.read("fabric.mod.json").decode("utf-8"))
        if MARKER_KEY not in metadata["custom"]:
            raise RuntimeError("patched jar has no compatibility marker")
        if SCATTER_MARKER_KEY not in metadata["custom"]:
            raise RuntimeError("patched jar has no scatter-workaround marker")
        if metadata.get("name") != PATCH_NAME:
            raise RuntimeError("patched jar has the wrong display name")
        if metadata.get("description") != PATCH_DESCRIPTION:
            raise RuntimeError("patched jar has the wrong description")
        if metadata.get("id") != "voxy":
            raise RuntimeError("patched jar lost its mod id; Fabric would not load it")
        for entry in (ZSTD_ENTRY, LMDB_ENTRY):
            if entry not in archive.namelist():
                raise RuntimeError(f"patched jar has no {entry}")
        with zipfile.ZipFile(io.BytesIO(archive.read(NESTED_ROCKSDB))) as nested:
            if ROCKSDB_NATIVE not in nested.namelist():
                raise RuntimeError("patched rocksdb jar has no macOS arm64 jnilib")
            if nested.read(ROCKSDB_NATIVE) != rocksdb_native:
                raise RuntimeError("the macOS arm64 jnilib was corrupted while patching")
        scatter = archive.read(SCATTER_COMP_PATH).decode("utf-8")
        if SCATTER_NEW_DERIVE not in scatter:
            raise RuntimeError("patched scatter.comp lacks the low-bit derivation")
        if "writeLocation>>31" in scatter or "(1u<<31)-1" in scatter:
            raise RuntimeError("patched scatter.comp still has the top-bit derivation")
        _audit_scatter_classes(archive.read(ASYNC_NODE_MANAGER),
                               archive.read(ASYNC_NODE_MANAGER_SYNC_RESULTS))
        if archive.testzip() is not None:
            raise RuntimeError("the patched jar failed its own integrity test")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download upstream Voxy, add the macOS ARM64 natives it omits, "
            "apply the local scatter-upload workaround for Zink/KosmicKrisp, "
            "and write an installable jar into dist/. Nothing is installed "
            "for you and no Minecraft installation is touched. Personal use "
            "only: the resulting jar must not be redistributed."
        )
    )
    arguments = parser.parse_args()

    tool_dir = Path(__file__).resolve().parent
    output = tool_dir / "dist" / OUTPUT_NAME

    log(f"== voxy {VOXY_VERSION}: macOS arm64 native patch")
    voxy_bytes = download(VOXY_URL, VOXY_SHA512, f"voxy {VOXY_VERSION}")
    rocksdb_osx = download(ROCKSDB_URL, ROCKSDB_SHA512, "org.rocksdb:rocksdbjni:10.2.1:osx")
    zstd_bytes = download(ZSTD_URL, ZSTD_SHA512, "org.lwjgl:lwjgl-zstd:3.4.1:natives-macos-arm64")
    lmdb_bytes = download(LMDB_URL, LMDB_SHA512, "org.lwjgl:lwjgl-lmdb:3.4.1:natives-macos-arm64")
    with zipfile.ZipFile(io.BytesIO(rocksdb_osx)) as archive:
        if ROCKSDB_NATIVE not in archive.namelist():
            raise RuntimeError(f"{ROCKSDB_NATIVE} is missing from the rocksdb osx jar")
        rocksdb_native = archive.read(ROCKSDB_NATIVE)

    log("  patching")
    patched_bytes = build_patched(voxy_bytes, rocksdb_native, zstd_bytes, lmdb_bytes)
    verify_patched(patched_bytes, rocksdb_native)
    log(f"    sha512 {sha512_hex(patched_bytes)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched_bytes)

    log(f"== built {output}")
    log(
        "\ninstall it by hand:\n"
        "  1. copy the jar into the instance's minecraft/mods/ folder\n"
        f"  2. delete the original {VOXY_FILENAME} from that folder\n"
        "     -- Fabric refuses to load two jars declaring the same mod id, so\n"
        "     leaving both in place crashes the game on startup\n"
        "  3. launch the instance"
    )
    log(
        "\nthe jar is for the machine that built it. Do not upload it to\n"
        "modrinth, discord, or anywhere else: voxy is all-rights-reserved with\n"
        '"do not redistribute" and no provision for unofficial versions.'
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ncancelled.", file=sys.stderr)
        raise SystemExit(130)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
