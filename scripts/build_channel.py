"""Build the Blyx source channel and collection ZIP from an immutable catalog."""
import argparse
import bz2
import configparser
import hashlib
import io
import json
import re
import stat
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://www.blyx-lang.space"
PLATFORMS = ("linux-64", "linux-aarch64", "osx-64", "osx-arm64", "win-64", "win-arm64")
LICENSES = ("LICENSE-MIT", "LICENSE-APACHE")


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Blyx-source-distribution"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def valid_path(name):
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError(f"Invalid package path {name!r}")
    return path.as_posix()


def upstream(repository, commit, cache):
    if not re.fullmatch(r"https://github\.com/Rahulchaube1/[\w-]+", repository) or not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Expected a full GitHub commit in the Blyx catalog")
    archive = cache / (commit + ".zip")
    if not archive.exists():
        content = fetch(f"https://codeload.github.com/{repository.split('github.com/')[1]}/zip/{commit}")
        with zipfile.ZipFile(io.BytesIO(content)) as check:
            if check.testzip():
                raise ValueError(f"Invalid archive for {repository}")
        archive.write_bytes(content)
    files = {}
    prefix = repository.rsplit("/", 1)[-1] + "-" + commit + "/"
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            if not member.filename.startswith(prefix):
                raise ValueError(f"Unexpected archive root for {repository}")
            if member.is_dir():
                continue
            name = valid_path(member.filename[len(prefix):])
            if name.split("/")[0] in {".git", ".github", ".gitattributes", ".gitignore"}:
                continue
            if stat.S_ISLNK(member.external_attr >> 16) or name in files:
                raise ValueError(f"Unexpected source member {name}")
            files[name] = zipped.read(member)
    return files


def project(item, snapshot, cache):
    slug = item["slug"]
    name = item.get("name") or "blyx-" + slug
    version = item["version"]
    if not all(re.fullmatch("[a-z0-9-]+", n) for n in (name, slug)) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Invalid catalog entry {slug}")
    files = upstream(item["repository"], item["commit"], cache)
    locks = snapshot["submodules"].get(slug, {})
    modules = configparser.ConfigParser()
    modules.read_string(files.pop(".gitmodules", b"").decode())
    declared = {modules[s]["path"]: modules[s]["url"].removesuffix(".git") for s in modules.sections()}
    if declared != {k: v["repository"] for k, v in locks.items()}:
        raise ValueError(f"Submodule lock mismatch in {slug}")
    for directory, pin in locks.items():
        path = valid_path(directory)
        for target, data in upstream(pin["repository"], pin["commit"], cache).items():
            key = path + "/" + target
            if key in files or target == ".gitmodules":
                raise ValueError(f"Unexpected nested or overlapping submodule in {slug}")
            files[key] = data
    if not all(x in files for x in (*LICENSES, item["module"] + ".blyx", "Blyx.toml")):
        raise ValueError(f"Incomplete source or missing license in {slug}")
    prefix = "share/blyx/" + slug + "/"
    payload = {prefix + "vendor/" + slug + "/" + key: value for key, value in files.items()}
    payload[prefix + "main.blyx"] = (item["program"].rstrip() + "\n").encode()
    payload[prefix + "expected.txt"] = (item["output"].rstrip("\r\n") + "\n").encode()
    source = {"repository": item["repository"], "commit": item["commit"], "submodules": locks}
    payload[prefix + "source.json"] = encoded(source)
    number = snapshot["build_numbers"].get(slug, 0)
    index = {"name": name, "version": version, "build": str(number), "build_number": number,
             "subdir": "noarch", "noarch": "generic", "depends": [], "arch": None, "platform": None,
             "license": "MIT OR Apache-2.0"}
    home = SITE + "/packages/" + slug
    about = {"home": home, "doc_url": home, "dev_url": item["repository"], "summary": item["description"],
             "license": index["license"]}
    descriptor = {"slug": slug, "name": name, "version": version, "kind": item["category"],
                  "build": index["build"], "directory": prefix.rstrip("/"), "module": item["module"] + ".blyx", **source}
    licenses = {f"info/licenses/{path}": files[path] for path in LICENSES}
    return descriptor, payload, index, about, licenses


def conda_archive(payload, index, about, licenses):
    paths = [{"_path": path, "path_type": "hardlink", "sha256": digest(data), "size_in_bytes": len(data)}
             for path, data in sorted(payload.items())]
    files = {**payload, **licenses,
             "info/index.json": encoded(index), "info/about.json": encoded(about),
             "info/paths.json": encoded({"paths_version": 1, "paths": paths}),
             "info/link.json": encoded({"package_metadata_version": 1, "noarch": {"type": "generic"}}),
             "info/files": ("\n".join(sorted(payload)) + "\n").encode()}
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:bz2", format=tarfile.PAX_FORMAT) as archive:
        for name, data in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    return result.getvalue()


def keep_artifact(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"{path.name} already exists with different contents. Increase its build number or release version.")
        return
    path.write_bytes(data)


def write_repo_index(folder, records):
    raw = encoded({"info": {"subdir": folder.name}, "packages": records, "packages.conda": {},
                   "removed": [], "repodata_version": 1})
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "repodata.json").write_bytes(raw)
    (folder / "repodata.json.bz2").write_bytes(bz2.compress(raw))


def build(args):
    snapshot = json.loads((ROOT / "snapshot.json").read_bytes())
    sha = snapshot["catalog_commit"]
    raw = fetch(f"https://raw.githubusercontent.com/Rahulchaube1/blyxxxx/{sha}/website/src/lib/packages.json")
    catalog = json.loads(raw)
    cache, channel, out = args.cache, args.channel, args.out
    for directory in (cache, channel / "noarch", out):
        directory.mkdir(parents=True, exist_ok=True)
    entries = sorted(catalog["packages"], key=lambda item: item["slug"])
    if len({p["slug"] for p in entries}) != len(entries):
        raise ValueError("Duplicate Blyx catalog slugs")
    all_files, manifest, descriptions = {}, [], {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for descriptor, payload, index, about, licenses in pool.map(lambda p: project(p, snapshot, cache), entries):
            name = index["name"]
            if name in descriptions:
                raise ValueError(f"Duplicate Conda package name {name}")
            filename = f"{name}-{index['version']}-{index['build']}.tar.bz2"
            archive = conda_archive(payload, index, about, licenses)
            keep_artifact(channel / "noarch" / filename, archive)
            manifest.append({**descriptor, "filename": filename, "sha256": digest(archive)})
            all_files.update(payload)
            descriptions[name] = {**about, "name": name, "version": index["version"], "subdirs": ["noarch"]}
    records = {}
    for path in sorted((channel / "noarch").glob("*.tar.bz2")):
        archive = path.read_bytes()
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:bz2") as packed:
            index = json.load(packed.extractfile("info/index.json"))
            about = json.load(packed.extractfile("info/about.json"))
        records[path.name] = {**index, "size": len(archive), "sha256": digest(archive),
                              "md5": hashlib.md5(archive, usedforsecurity=False).hexdigest()}
        descriptions.setdefault(index["name"], {**about, "name":index["name"], "version":index["version"], "subdirs":["noarch"]})
    write_repo_index(channel / "noarch", records)
    for platform in PLATFORMS:
        write_repo_index(channel / platform, {})
    (channel / "channeldata.json").write_bytes(encoded({"channeldata_version": 1, "subdirs": ["noarch", *PLATFORMS], "packages": descriptions}))
    manifest_data = encoded({"version": snapshot["version"], "compiler": catalog["compiler"], "catalog_commit": sha, "packages":manifest})
    (channel / "catalog.json").write_bytes(manifest_data)
    all_files["catalog.json"] = manifest_data
    bundle = out / ("blyx-packages-" + snapshot["version"] + ".zip")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        for name, data in sorted(all_files.items()):
            member = zipfile.ZipInfo(name)
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            zipped.writestr(member, data, compress_type=zipfile.ZIP_DEFLATED)
    keep_artifact(bundle, buffer.getvalue())
    (out / "SHA256SUMS").write_text(digest(bundle.read_bytes()) + "  " + bundle.name + "\n"
        + "".join(f"{item['sha256']}  noarch/{item['filename']}\n" for item in manifest), encoding="utf-8",newline="\n")
    print(f"Built {len(manifest)} source projects and {bundle.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache")
    parser.add_argument("--channel", type=Path, default=ROOT / "docs")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    build(parser.parse_args())
