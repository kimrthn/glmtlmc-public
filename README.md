<a id="readme-top"></a>

<br />
<div align="center">
  <a href="GLMTLMC">
    <img src="https://github.com/user-attachments/assets/88afe4e0-7d43-4a1b-8fc4-6a236d0a6dd2" alt="Logo" width="600" height="240">
  </a>

  <h3 align="center">GLMTLMC</h3>

  <p align="center">
    GLMTLMC
    <br />
    <a href="https://discord.com/invite/mVtWzCHhKr"><strong>Join the Discord</strong></a>
    <br />
    <br />
    <a href="https://github.com/user-attachments/assets/547ba474-cec8-4643-ba54-bbd0083a6580">View Screenshot</a>
    &middot;
    <a href="https://discord.com/invite/mVtWzCHhKr">Report Bug</a>
    &middot;
    <a href="https://discord.com/invite/mVtWzCHhKr">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

GLMTLMC originates from GL from OpenGL MTL from Metal MC from Minecraft

GLMTLMC brings experimental but improving support for newer versions of OpenGL specifically 4.2 and onwards. This enables very cool stuff that apple decided shouldnt happen.

Here's what this enables:
* Compute Shaders and Path Tracing/Ray Tracing and Colored Shadows are some of the bigger examples.
* Running modern shaders that from the start didnt even support MacOS in the first place
* VR minecraft with Shaders

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

A couple important pieces of this project

* [![OpenGL][OpenGL]][OpenGL-url]
* [![KosmikKrisp][KosmikKrisp]][KosmikKrisp-url]
* [![Mesa][Mesa]][Mesa-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

> **Experimental branch: 0.5.0-beta.1.** Shader packs run faster, but some triangles may show the wrong colour. For the standard build, use the `main` branch or the latest normal release.

Open the latest release and download the zip for your Minecraft version: `glmtlmc-<version>-mc26.2.zip` for 26.2, `glmtlmc-<version>-mc26.3.zip` for 26.3. Each build only patches its own version. Save it to a non temporary location for eg Documents or your User folder.

### Prerequisites

- MacOS 27
- Prism Launcher
- Minecraft Ownership
- Apple Silicon
- Fabric or NeoForge if you want mods
- Iris & Sodium for shaders (for VR: Iris 1.11.2 & Sodium 0.9.1, for NeoForge on 26.3: Sodium 0.9.3-beta.1 or newer)

### Installation

Quick Start

Run glmtlmc with sudo. Browsers quarantine every file they download, and Gatekeeper then blocks each library in the stack when Minecraft loads it. Running with sudo lets glmtlmc clear that quarantine itself before it patches anything. Once it has, it switches back to your own user, so every file it writes stays yours.

1. Quit Prism Launcher completely.
2. Open your terminal.
3. Type 'sudo ' (with the space), drag the 'glmtlmc' file from the release folder into the terminal, then press enter and enter your password.
4. glmtlmc lists the Prism instances it finds, with their Minecraft version and whether they're already patched. Type the number of the one you want. If yours isn't listed, drag the instance folder into the terminal instead and press enter. Escaped spaces like 'Application\ Support' are fine.
5. Choose an option and follow its instructions.

The path to the GLMTLMC release folder itself must not contain spaces or backslashes. The launch settings glmtlmc writes into Prism are split on spaces, so a folder like 'Downloads/glmtlmc-public 2' would break them. glmtlmc stops and tells you if it finds one; move or rename the folder (e.g. to '~/glmtlmc') and run it again.

Gatekeeper Fix

If something is still blocked after running glmtlmc with sudo:

1. Open your terminal.
2. Type 'sudo xattr -cr '
3. Drag and drop your downloaded GLMTLMC release folder.
4. Press enter and enter your password.

Complementary Reimagined GLMTLMC Patch

Due to licensing problems we can't ship a prebuilt patched Complementary Reimagined shader specificaly modified for GLMTLMC. In order to adress this every release ships with a /shaders folder. Navigate to the appropriate subfolder and then read the instructions.

VR and Voxy

The Voxy patch below is in the 26.2 build only. VR is in both builds.

Voxy GLMTLMC Apple Patch

Bring Voxy back to Apple Silicon with shader support! Supports VR use too. Very powerful Mac recommended for running Voxy in VR. Due to licensing problems we can't ship a prebuilt patched Voxy jar. In order to adress this every new release ships with a /mods folder. Navigate to the appropriate subfolder and then read the instructions.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- VERSIONING -->
## Versioning

Releases are numbered `MAJOR.MINOR.PATCH` and tagged like `v0.4.0`. See [CHANGELOG.md](CHANGELOG.md) for what changed in each one.

* `PATCH`: bug fixes only.
* `MINOR`: a new Minecraft version, mod loader or feature, or a Mesa update.
* `MAJOR`: a change that makes people redo their setup, or drops a Minecraft version.

The project is on `0.x` for now. The Minecraft version is in the zip name, not the version number. Run `glmtlmc` to see which version you have.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are appreciated. They can be done either via opening an issue on this repository or ( preferably ) by posting to the relevant channels in discord.


<!-- LICENSE -->
## License

This project has many other open-source projects inside of it. All of them have their respective licenses shipped with every release.


<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

@Discord - atkevyn / https://discord.com/invite/mVtWzCHhKr

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

Based on the https://gist.github.com/lucamignatti/5312f5e937de2ba44256ecba6de54cc2 by https://github.com/lucamignatti , couldn't have been possible without their work.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->


[forks-shield]: https://img.shields.io/github/forks/kimrthn/glmtlmc-public?style=for-the-badge
[stars-shield]: https://img.shields.io/github/stars/kimrthn/glmtlmc-public?style=for-the-badge
[issues-shield]: https://img.shields.io/github/issues/kimrthn/glmtlmc-public?style=for-the-badge
[issues-url]: https://discord.gg/zBMcGPRgB5
[product-screenshot]: https://github.com/user-attachments/assets/7e57feb2-cd9b-408b-9ec4-01e9c5caf934
[OpenGL]: https://img.shields.io/badge/OpenGl-5487A6?logo=OpenGl&logoColor=white
[OpenGL-url]: https://www.opengl.org/
[KosmikKrisp]: https://camo.githubusercontent.com/9b5f86854a9ca76796f773c2c21fc3dbe61d9c89d499ee64b37a93875dd2a37c/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f4b6f736d69634b726973702d4d6573612532306472697665722d364134433933
[KosmikKrisp-url]: https://docs.mesa3d.org/drivers/kosmickrisp.html
[Mesa]: https://camo.githubusercontent.com/963cf9a770167be3c2d3aaa6cd3316d83d36c4daa6dbf257b3d43c0fea218a22/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f4d6573612d4772617068696373253230737461636b2d334138303642
[Mesa-url]: https://mesa3d.org/
