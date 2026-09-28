# glmtlmc

Minecraft on Apple Silicon with a real OpenGL 4.6 stack:
Minecraft 26.2 -> Zink -> KosmicKrisp (Vulkan) -> Metal 4.

Fully self-contained. Nothing is installed on your machine — the game is
launched using the files inside this folder, and deleting this folder
removes every trace (run Unpatch first).

## Requirements
- Apple Silicon Mac, macOS 27.0+ (Metal 4)
- Prism Launcher
- Minecraft 26.2 instance (Iris/Sodium for shaders)

## Use
1. Quit Prism Launcher completely
2. Run `./glmtlmc` (double-click works too)
3. Paste the path of your instance when asked, then choose `1 : Patch`
4. Open Prism Launcher and launch the instance

To undo: `./glmtlmc` -> `2 : Unpatch`
After moving this folder: `./glmtlmc` -> `3 : Update glmtlmc`

Shaderpacks work with Iris. Third-party shaderpacks are not included in this
package. To create a local Complementary Reimagined copy later, see
`shaders/ComplementaryPatch/README.md`.

The optional tool requires its shipped patch file at
`shaders/ComplementaryPatch/patches/001-remove-apple-device-gating.patch`.
It downloads and patches the upstream shaderpack only when run explicitly;
no final patched shaderpack is included in this package.

Licenses: `licenses/`
