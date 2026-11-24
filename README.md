# Blyx source packages

Install individual Blyx frameworks and libraries with Conda, or download them together as a ZIP. The 2026.11.24 collection contains **65 frameworks and 107 libraries**. Every project includes a runnable Blyx example, its expected output, the upstream source and licenses, and the exact Git commit used for packaging. [Framework directory](https://www.blyx-lang.space/frameworks) · [Library directory](https://www.blyx-lang.space/libraries) · [Release downloads](https://github.com/Rahulchaube1/blyx-packages/releases)

## Install individual packages

The project maintains a public Conda channel at `https://rahulchaube1.github.io/blyx-packages`. Its `noarch` packages contain portable source. A package retains its upstream release version. Install the [Blyx compiler](https://www.blyx-lang.space/download), Rust and a host linker to run the native examples.

```sh
conda create -y -n blyx-demo --override-channels -c https://rahulchaube1.github.io/blyx-packages blyxtorch=0.5.0 blyx-moments=0.1.0
conda activate blyx-demo
```

On macOS or Linux, run the Moments example with the following command.

```sh
blyxc native-run "$CONDA_PREFIX/share/blyx/moments/main.blyx"
```

On Windows, run this in PowerShell after activating the environment.

```powershell
blyxc native-run (Join-Path $env:CONDA_PREFIX 'share/blyx/moments/main.blyx')
```

The example prints `3`, `12` and `2` on separate lines. Use `share/blyx/blyxtorch/main.blyx` to run the differentiation example. To find other package names and versions, search the channel.

```sh
conda search --override-channels -c https://rahulchaube1.github.io/blyx-packages "*"
```

## Install the collection

The [release ZIP and SHA-256 checksums](https://github.com/Rahulchaube1/blyx-packages/releases/tag/v2026.11.24) are available without an account. Extract the ZIP and run `blyxc native-run share/blyx/moments/main.blyx` from its root. Each directory under `share/blyx` contains a complete example project. To use Moments in your own program, copy the project's `vendor/moments` directory into your own `vendor` directory and import `use vendor::moments::moments;`. Copying the entire module directory preserves its local dependencies.

The full collection is also distributed through the project's [Homebrew tap](https://github.com/Rahulchaube1/homebrew-blyx) and [Scoop bucket](https://github.com/Rahulchaube1/scoop-blyx).

```sh
brew install rahulchaube1/blyx/blyx-packages
blyxc native-run "$(brew --prefix rahulchaube1/blyx/blyx-packages)/share/blyx/moments/main.blyx"
```

```powershell
scoop bucket add blyx https://github.com/Rahulchaube1/scoop-blyx
scoop install blyx/blyx-packages
blyxc native-run (Join-Path (scoop prefix blyx-packages) 'share/blyx/moments/main.blyx')
```

## Reproduce and verify a release

`snapshot.json` pins the language catalog and the two Git submodules used by ModelGate. Each upstream project ships under its own MIT or Apache-2.0 licenses. The channel catalog records the package name, version, source revision, entry module and SHA-256 for each archive. [Machine-readable catalog](https://rahulchaube1.github.io/blyx-packages/catalog.json)

With Python 3.10 or later, run `python scripts/build_channel.py` to reproduce the Conda channel under `docs` and the collection ZIP under `dist`. The build refuses to replace a published package with different bytes at the same version and build number. To test installed projects, run `python scripts/test_installs.py PREFIX`, where `PREFIX` contains the installed `share/blyx` directory and `blyxc` is on PATH. To check one package, append `--package moments`.

## Maintainer and support

Blyx is an open-source project created by Rahul Chaube. [GitHub](https://github.com/Rahulchaube1) · [LinkedIn](https://www.linkedin.com/in/rahulchaube1) · [Community](https://www.blyx-lang.space/community) · [GitHub Sponsors](https://github.com/sponsors/Rahulchaube1) · [Buy Me a Coffee](https://buymeacoffee.com/rahulchaube)
