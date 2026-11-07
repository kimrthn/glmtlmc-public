# Changelog

## 0.5.0-beta.1 (2026-11-07, experimental)

Mesa `411f4a9d5ed`: the 0.4.0 Mesa plus one experimental patch. Built separately from the standard release.

- Made shader packs faster by skipping a slow compute pass for flat shading: about 33% on Retina and up to 84% on non-Retina screens, in a 1280×720 window. Plain Sodium gains about 4%.
- Trade-off: pack or mod values marked `flat` now come from a triangle's first vertex instead of its last, so some triangles may show the wrong colour.

## 0.4.0 (2026-11-07)

Mesa `1c1f9bbc7ec` plus one cleanup commit (`8f97a75b4dd`), now built without LLVM.

- Added Minecraft 26.3, which replaced GLFW with SDL3, using a patched SDL 3.4.14.
- Added NeoForge support on 26.2 and 26.3.
- Changed releases to one zip per Minecraft version.
- Added VR to 26.3.
- Fixed Vivecraft 26.3 crashing on a function MoltenVR does not implement.
- Added the logo and version to the terminal app.
- Reduced the download from about 68 MB to under 9 MB by dropping LLVM and Z3, which this stack never uses. FPS is unchanged.
- Fixed Update breaking VR instances, including after moving the folder.
- Fixed Sodium Extra's Reduce Resolution filling only a quarter of the window on 26.3.
- Fixed native crashes leaving no Java crash report.
- Added a check that stops before Iris 1.11.2 or older is used with Sodium 0.9.2 or newer.
- Added a Prism instance picker, plus checks for paths that would break launching and for files still quarantined.

## 0.3.0 (2026-10-15)

Tag `glmtlmc-public-20261015-1c1f9bbc7ec`. Mesa `1c1f9bbc7ec`.

- Fixed VR image readback failing when pixel-pack state leaked between the menu and the world.
- Added the optional Voxy patcher.

## 0.2.0 (2026-10-05)

Tag `glmtlmc-publishing-20261005-bc85ec8d602`. Mesa `bc85ec8d602`.

- Added VR through MoltenVR.
- Made the release folder movable by relocating library install names.

## 0.1.0 (2026-09-29)

Tag `release`. Mesa `bc85ec8d602`.

- First public release: OpenGL 4.6 on Apple Silicon for Minecraft 26.2.
