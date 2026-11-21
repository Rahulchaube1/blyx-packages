"""Compile and execute the example in each installed Blyx source package."""
import argparse
import json
from pathlib import Path
import subprocess


def test(prefix, compiler, catalog, names):
    packages = json.loads(catalog.read_bytes())["packages"]
    selected = [p for p in packages if not names or p["slug"] in names]
    if names and set(names) != {p["slug"] for p in selected}:
        raise ValueError("Unknown package selection")
    for n, package in enumerate(selected, 1):
        slug = package["slug"]
        project = prefix / package["directory"]
        vendor = project / "vendor" / slug
        for name in (package["module"], "LICENSE-MIT", "LICENSE-APACHE"):
            if not (vendor / name).is_file():
                raise ValueError(f"{slug} is missing {name}")
        if json.loads((project / "source.json").read_bytes())["commit"] != package["commit"]:
            raise ValueError(f"Source revision mismatch in {slug}")
        result = subprocess.run([compiler, "native-run", "main.blyx"], cwd=project, capture_output=True,
                                text=True, encoding="utf-8", timeout=120)
        expected = (project / "expected.txt").read_text(encoding="utf-8")
        if result.returncode or result.stdout != expected:
            raise ValueError(f"{slug} failed its example\n{result.stderr}\nExpected {expected!r}, got {result.stdout!r}")
        if n % 25 == 0 or n == len(selected):
            print(f"Passed {n}/{len(selected)} installed Blyx examples", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path, help="Installation prefix containing share/blyx/")
    parser.add_argument("--compiler", default="blyxc")
    parser.add_argument("--package", action="append", default=[])
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[1] / "docs/catalog.json")
    args = parser.parse_args()
    test(args.prefix.resolve(), args.compiler, args.catalog, args.package)
