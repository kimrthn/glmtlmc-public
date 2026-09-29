[![Discord](https://img.shields.io/badge/Discord-Community-5865F2)](https://www.complementary.dev/discord)
![OpenGL](https://img.shields.io/badge/OpenGL-Graphics%20API-5586A4)
![KosmicKrisp](https://img.shields.io/badge/KosmicKrisp-Mesa%20driver-6A4C93)
![Metal](https://img.shields.io/badge/Metal-Apple%20graphics%20API-8A8F98)
![Vulkan](https://img.shields.io/badge/Vulkan-Graphics%20API-AC3B32)
![Mesa](https://img.shields.io/badge/Mesa-Graphics%20stack-3A806B)
![Publishing](https://img.shields.io/badge/Publishing-Local%20bundle-D18B2C)

**glmtlmc — OpenGL-on-Metal Minecraft**

Minecraft Java Edition needs OpenGL 4.4+ for modern shaderpacks, while macOS's deprecated system OpenGL is capped at 4.1. glmtlmc provides a userspace graphics stack that runs OpenGL 4.6 through Vulkan on Apple's Metal API, letting Minecraft use modern shaderpacks on Apple Silicon.

**Graphics stack**

Minecraft → patched GLFW + Mesa EGL/libGL → Zink (OpenGL on Vulkan) → KosmicKrisp (Vulkan on Metal) → Apple Silicon GPU

**What this enables**

- A real OpenGL 4.6 core context in Minecraft on macOS.
- Prism Launcher instances with Iris and Sodium, using shaderpacks that require newer OpenGL than Apple's system driver provides.
- Validated shaderpack compatibility, including Complementary Reimagined, with known limitations documented in the project.

**Requirements**

- Apple Silicon Mac. M3 is the only tested generation; other Apple Silicon models are unverified.
- Prism Launcher and a Minecraft Java Edition instance configured with Fabric, Iris, and Sodium.
- A local build of the Mesa/Zink/KosmicKrisp graphics stack and the patched GLFW library. See [the build and install guide](glmtlmc/docs/build-and-install.md) for dependencies and setup.

**Complementary Reimagined local patcher**

An optional tool in `shader-tools/ComplementaryPatch` downloads Complementary Reimagined r5.9.3 from Modrinth, applies the included Apple-device-gating patch, and writes the patched pack to `dist/ComplementaryReimagined_r5.9.3.zip`. Run `./build.sh` in that directory when you want to create it; Python 3 and the standard `patch` command are required. The upstream pack is downloaded on demand, and neither it nor the generated pack is bundled or redistributed by this project. This is a local patcher, not an official Complementary release.

**Contributing**

Contributions are welcome, especially reproducible reports and improvements to the build instructions, compatibility notes, and patches. Please open an issue or pull request with the relevant macOS, chip, Mesa, Minecraft, and shaderpack versions. For community discussion, see the [Complementary Discord](https://www.complementary.dev/discord). Please keep contributions focused on this project and do not include third-party shaderpack assets.

**Monetization**

There are no monetization plans for this project.
