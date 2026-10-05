[![Discord](https://img.shields.io/badge/Discord-Community-5865F2)](https://discord.gg/zBMcGPRgB5)
![OpenGL](https://img.shields.io/badge/OpenGL-Graphics%20API-5586A4)
![KosmicKrisp](https://img.shields.io/badge/KosmicKrisp-Mesa%20driver-6A4C93)
![Metal](https://img.shields.io/badge/Metal-Apple%20graphics%20API-8A8F98)
![Vulkan](https://img.shields.io/badge/Vulkan-Graphics%20API-AC3B32)
![Mesa](https://img.shields.io/badge/Mesa-Graphics%20stack-3A806B)
![Publishing](https://img.shields.io/badge/Publishing-Local%20bundle-D18B2C)

*glmtlmc*

Minecraft Java Edition needs OpenGL 4.4+ for modern shaderpacks, while macOS's deprecated system OpenGL is capped at 4.1. glmtlmc provides a userspace graphics stack that runs OpenGL 4.6 through Vulkan on Apple's Metal API, letting Minecraft use modern shaderpacks on Apple Silicon.

*The magic*

Minecraft → patched GLFW + Mesa EGL/libGL → Zink → KosmicKrisp → Apple Silicon 

*What this enables*

A real OpenGL 4.6 core context in Minecraft on macOS.
Prism Launcher instances with Iris and Sodium, using shaderpacks that require newer OpenGL than Apple's system driver provides.
Validated shaderpack compatibility, including Complementary Reimagined, with known limitations documented in the project.

*Requirements*

- Apple Silicon Mac. M3 is the only tested generation; other Apple Silicon models are unverified.
- Prism Launcher and a Minecraft Java Edition instance configured with Fabric, Iris, and Sodium.
- sudo xattr -cr ing the glmtlmc-public folder so it works without gatekeeper errors.

*Complementary Reimagined local patcher*

An optional tool in `shaders/ComplementaryPatch` downloads Complementary Reimagined r5.9.3 from Modrinth, applies the included Apple-device-gating patch, and writes the patched pack to `dist/ComplementaryReimagined_r5.9.3.zip`. Run `./build.sh` in that directory if you want the patched version. Why can we not ship it? Licensing. We abide by licenses. This patcher does basically the same thing but on your device.

*Contributing*

Contributions are accepted in discord. This project is mainly going to be maintained by me ( at least for now ).

*Monetization*

There are no monetization plans for this project.
