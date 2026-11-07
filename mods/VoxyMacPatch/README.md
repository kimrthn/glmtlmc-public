# Voxy macOS arm64 patch tool

This optional tool downloads Voxy `0.2.19-beta` from Modrinth, adds the macOS
ARM64 native libraries that build omits, applies a local scatter-upload
workaround for Zink/KosmicKrisp (below), and writes the resulting jar to
`dist/voxy-0.2.19-beta-macos-arm64.jar`.

Run `./build.sh` in this directory. It builds a jar file and nothing else: it
never looks for, opens, or modifies any Minecraft installation. Installing it
is a separate step done by hand — copy the jar into the instance's
`minecraft/mods/` folder and delete the original `voxy-0.2.19-beta.jar`, since
Fabric refuses to load two jars declaring the same mod id.

Requirements: Python 3.9 or newer, nothing else. The downloads and the patched
jar are not bundled; the tool runs only when invoked, and `dist/` is not
tracked by git.

Downloads show progress and retry stalled connections a few times before
failing (Ctrl+C cancels cleanly), since the Modrinth CDN can be slow from
some networks — a 12 MB file taking a minute is the network, not the tool.

## What it fixes

Every input is pinned by SHA-512, so the tool refuses to patch an unknown build:

| Input | Source | SHA-512 |
| --- | --- | --- |
| `voxy-0.2.19-beta.jar` | Modrinth `fxxUqruK/LzyXnE51` | `9071acefff00f952b049134f7ee8b5c8be27646ade992274f9a32e4adf7ad0932f9755530fa212a8e65cc23b3ed5dc643af139be83fcb89c778d8c8e723b9c3a` |
| `rocksdbjni-10.2.1-osx.jar` | Maven Central `org.rocksdb:rocksdbjni:10.2.1:osx` | `f728d5702d2477e976e9a93e8a6be2c86cc3693f8d411408e490026714fde1c354e8be6ee3b447df7b3ea5ac7d519cc03a6f083dee65007f7ee0c6954e087e36` |
| `lwjgl-zstd-3.4.1-natives-macos-arm64.jar` | Maven Central `org.lwjgl:lwjgl-zstd:3.4.1:natives-macos-arm64` | `6645fb87e80a9611f20a6dc5cb7a72c459978b7e9ef1859b9b747a2b64312e3163ca7315c86e16a340f8018b5633e432de2ddf06e3f913b73e105a62ae912621` |
| `lwjgl-lmdb-3.4.1-natives-macos-arm64.jar` | Maven Central `org.lwjgl:lwjgl-lmdb:3.4.1:natives-macos-arm64` | `146d6cca64ac12d796c89b14121886a23bcdd06c3a82ec2049cbfb79146b9de8b6355c6a538593fe61c6766e6c4f149e978dc81c64c6a9d7f95424239c1aa0aa` |

Voxy on Apple Silicon crashes on world join with
`java.lang.RuntimeException: librocksdbjni-osx-arm64.jnilib was not found inside JAR`,
because the `rocksdbjni` jar nested inside the mod ships only
`librocksdbjni-linux64.so` and `librocksdbjni-win64.dll`. Fixing that exposes the
next failure: Voxy's default ZSTD compressor needs LWJGL's zstd native, which the
build also ships for linux and windows only.

Both are libraries Voxy already declares as its own dependencies, so the patch
adds them rather than changing Voxy:

| File added | Source | License |
| --- | --- | --- |
| `librocksdbjni-osx-arm64.jnilib` into `META-INF/jars/rocksdbjni-10.2.1.jar` | `org.rocksdb:rocksdbjni:10.2.1:osx` | Apache-2.0 / GPL-2.0 dual |
| `META-INF/jars/lwjgl-zstd-3.4.1-natives-macos-arm64.jar` | `org.lwjgl:lwjgl-zstd:3.4.1:natives-macos-arm64` | BSD-3-Clause |
| `META-INF/jars/lwjgl-lmdb-3.4.1-natives-macos-arm64.jar` | `org.lwjgl:lwjgl-lmdb:3.4.1:natives-macos-arm64` | BSD-3-Clause |

The patched jar is bit-reproducible — fixed entry timestamps, upstream
compression preserved — so the same inputs always give the identical jar.

## Scatter-upload workaround (LODs generate but never display)

With natives fixed, Voxy still renders nothing on this stack: LOD sections
generate and cache, the F3 overlay shows `VS` (visible sections) climbing,
but `QC` (quad counts) stays all zeros, so no draw commands are ever built.
Root cause, verified headless against this stack down to the exact shader and
packing: Voxy's `AsyncNodeManager` packs scatter-write locations with the
buffer select in the **top bit** (`(val<<1)|(1<<31)` for metadata halves,
bare `val` for nodes), and `voxy:util/scatter.comp` splits on
`writeLocation>>31`. On Zink/KosmicKrisp a compute SSBO store whose index
derives from a top-bit-set value, inside a branch taken on that top bit,
never lands — every metadata write is silently lost while node writes,
atomics, barriers and everything else behave. shifting, masking, `&`-tests,
`if/else` reorderings and qualifier changes were all tried headless; only a
packing with no top bit anywhere routes both sides correctly.

The patched jar therefore packs the select in the **low bit** instead:

- `assets/voxy/shaders/util/scatter.comp`: `writeBuffer = writeLocation & 1u`,
  `writeLocation = writeLocation >> 1`, branch unchanged;
- `AsyncNodeManager`: `int scatterAddr = (val<<2)|1`,
  `getScatterWritePtr(scatterAddr+0, 1)` unchanged,
  `getScatterWritePtr(scatterAddr+2, 0)` (was `+1`), node writes
  `getScatterWritePtr(val<<1)` (was `val`) — three instructions, applied as
  byte patches with uniqueness, constant and control-flow assertions, so an
  unexpected upstream build fails loudly rather than patching wrong bytes.

Nothing else reads this encoding: the TLN add/remove and cleaner bit-31
markers live in separate CPU-side sets and are untouched, and section/node
buffer layouts are unchanged (metadata halves still land at `2*val`,
`2*val+1`; nodes at `val`). The low-bit packing plus patched shader is
verified headless to land every metadata and node write exactly, including
metadata content with the top bit set. In-game check: after installing the
jar, F3 `QC` goes nonzero and distant LOD terrain appears.

The marker `scatter_lsb_workaround` in `fabric.mod.json` records that this
build carries the workaround. Same rules as the natives: local machine only.

> **Runtime note (2026-10-10):** on Fabric 0.19.5 the two added
> `*-natives-macos-arm64.jar` entries are listed but their dylibs are not
> picked up by LWJGL's classpath lookup (`Failed to locate library:
> liblwjgl_zstd.dylib`), which poisons Voxy's section-saving workers and, via
> the shared executors, stalls Sodium chunk meshing too (empty world). Until
> that lookup gap is understood, also copy the two dylibs somewhere already
> on the instance's `-Djava.library.path` (for glmtlmc instances that is
> `~/.moltenvr/`):
>
> ```sh
> unzip -p dist/voxy-0.2.19-beta-macos-arm64.jar \
>   META-INF/jars/lwjgl-zstd-3.4.1-natives-macos-arm64.jar > /tmp/vz.jar
> unzip -p /tmp/vz.jar macos/arm64/org/lwjgl/zstd/liblwjgl_zstd.dylib \
>   > ~/.moltenvr/liblwjgl_zstd.dylib
> unzip -p dist/voxy-0.2.19-beta-macos-arm64.jar \
>   META-INF/jars/lwjgl-lmdb-3.4.1-natives-macos-arm64.jar > /tmp/vl.jar
> unzip -p /tmp/vl.jar macos/arm64/org/lwjgl/lmdb/liblwjgl_lmdb.dylib \
>   > ~/.moltenvr/liblwjgl_lmdb.dylib
> ```
>
> Verified: with those two files in place, LWJGL resolves the ZSTD/LMDB
> natives through the library path and Voxy's storage stack initializes.

## Do not upload the result

Voxy is all-rights-reserved (`LICENSE.md`: "All rights reserved. Do not
redistribute.") and its Modrinth page permits bundling only the unmodified
release and explicitly excludes "unofficial backports or versions". The patch is
for your own machine. Keep using the official Voxy in modpacks, and if you want
this fixed properly, ask upstream: the build has an
`-PincludeOtherArchs=true` property that already stops the stripping, so landing
it needs two dependency lines in `build.gradle` rather than any code change.
