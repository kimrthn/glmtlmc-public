# Complementary Reimagined patch tool

This optional tool downloads Complementary Reimagined r5.9.3 from Modrinth,
applies the included Apple-device-gating patch, and writes the resulting shader
pack to `dist/ComplementaryReimagined_r5.9.3.zip`.

Run `./build.sh` when you want to create the patched pack. Python 3 and the
standard `patch` command are required. The download and generated pack are not
included in the glmtlmc publishing package; the tool runs only when invoked.

The patch is based on the upstream archive whose pristine SHA-512 is
`45304b1d7862afdb2177b7e6226fc9c6737911d17a4ad46cc9c519ca4deb935f05072cd337cd8b19a15bb8062b57b54eceec7bdee4cd572d94858e2946d37d85`.
