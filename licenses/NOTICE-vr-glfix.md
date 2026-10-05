# NOTICE - VR GL interposer

`stack/vr-lib/libvr_glfix.dylib` is built from `scripts/vr-glfix/vr_glfix.c`,
which ships in this package. It is original work, distributed under the same
license as glmtlmc itself (`../LICENSE`, at the root of this package); it links
only Apple's OpenGL framework and libSystem.

It interposes Apple's CGL entry points so MoltenVR's OpenVR shim falls back to
Mesa's libGL instead of dereferencing a null CGL context.
