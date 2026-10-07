from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

STAMP = "2026-10-07_23-55-WIB"
MASTER_NAME = f"MASTER-BACKUP-FULL-ALBUM-MAKER-{STAMP}"
REPO = os.environ["GITHUB_REPOSITORY"]
MAIN_SHA = "1fbf7c4a54a16c49053ab26e9fda7a838620d4df"
WORK_BRANCH = "ui/ui05-visual-remediation-v160"
WORK_SHA = "30db822fe5a27c417ed81dd8264a3ecc03d38264"
WINDOWS_RUN = "37646201849"
WINDOWS_ARTIFACT = "Full-Album-Maker-Windows-Portable"
UI05_RUN = "37652399221"

ROOT = Path("backup-work").resolve()
MASTER = ROOT / MASTER_NAME
APP = MASTER / "APP_001_FULL_ALBUM_MAKER"
MIRROR = ROOT / "repo-mirror.git"
CURRENT = ROOT / "current-tree"


def run(args: list[str], *, cwd: Path | None = None, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_zip(path: Path, *, minimum_entries: int = 1) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"ZIP kosong/tidak ada: {path}")
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP rusak {path}: {bad}")
        if len(zf.namelist()) < minimum_entries:
            raise RuntimeError(f"ZIP terlalu sedikit isi: {path}")


def iter_text_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_size > 2_000_000:
                continue
            yield p, p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue


def checksums_for(root: Path, output_name: str) -> None:
    out = root / output_name
    rows = []
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file() or p == out:
            continue
        rows.append(f"{sha256(p)}  {p.relative_to(root).as_posix()}")
    write(out, "\n".join(rows))


def verify_checksums(root: Path, checksum_name: str) -> None:
    for raw in (root / checksum_name).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        expected, rel = raw.split(None, 1)
        rel = rel.strip().lstrip("*")
        p = root / rel
        if not p.is_file():
            raise RuntimeError(f"Checksum target missing: {p}")
        actual = sha256(p)
        if actual.lower() != expected.lower():
            raise RuntimeError(f"Checksum mismatch: {p}")


def main() -> int:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    for sub in ("GIT", "SOURCE", "BUILD", "DOCS", "RECOVERY"):
        (APP / sub).mkdir(parents=True, exist_ok=True)

    # Complete mirror + integrity.
    run(["git", "clone", "--mirror", f"https://github.com/{REPO}.git", str(MIRROR)])
    run(["git", "-C", str(MIRROR), "remote", "update", "--prune"])
    run(["git", "-C", str(MIRROR), "fsck", "--full"])
    main_sha = run(["git", "-C", str(MIRROR), "rev-parse", "refs/heads/main"], capture=True).stdout.strip()
    work_sha = run(["git", "-C", str(MIRROR), "rev-parse", f"refs/heads/{WORK_BRANCH}"], capture=True).stdout.strip()
    if main_sha != MAIN_SHA or work_sha != WORK_SHA:
        raise RuntimeError(f"Ref moved: main={main_sha}, work={work_sha}")

    # Git Bundle and restore verification.
    bundle = APP / "GIT" / "Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle"
    run(["git", "-C", str(MIRROR), "bundle", "create", str(bundle), "--all"])
    if not bundle.is_file() or bundle.stat().st_size == 0:
        raise RuntimeError("Git Bundle kosong")
    verify = run(["git", "-C", str(MIRROR), "bundle", "verify", str(bundle)], capture=True)
    write(APP / "GIT" / "BUNDLE_VERIFY.txt", verify.stdout)
    heads = run(["git", "bundle", "list-heads", str(bundle)], capture=True).stdout
    write(APP / "GIT" / "BUNDLE_REFS.txt", heads)
    if not heads.strip():
        raise RuntimeError("Bundle refs kosong")
    restore_check = ROOT / "bundle-restore-check"
    run(["git", "clone", str(bundle), str(restore_check)])
    run(["git", "-C", str(restore_check), "fsck", "--full"])
    write(APP / "GIT" / "BUNDLE_CLONE_HEAD.txt",
          run(["git", "-C", str(restore_check), "rev-parse", "HEAD"], capture=True).stdout.strip())

    # Human-readable source snapshots.
    src_main = APP / "SOURCE" / "Full-Album-Maker-SOURCE-MAIN.zip"
    src_work = APP / "SOURCE" / "Full-Album-Maker-SOURCE-UI05-IN-PROGRESS.zip"
    docs_zip = APP / "DOCS" / "Full-Album-Maker-DOCS-UI05-IN-PROGRESS.zip"
    run(["git", f"--git-dir={MIRROR}", "archive", "--format=zip", f"--output={src_main}", "refs/heads/main"])
    run(["git", f"--git-dir={MIRROR}", "archive", "--format=zip", f"--output={src_work}", f"refs/heads/{WORK_BRANCH}"])
    run(["git", f"--git-dir={MIRROR}", "archive", "--format=zip", f"--output={docs_zip}",
         f"refs/heads/{WORK_BRANCH}", "docs", ".github/workflows"])
    check_zip(src_main, minimum_entries=20)
    check_zip(src_work, minimum_entries=20)
    check_zip(docs_zip, minimum_entries=5)

    CURRENT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src_work) as zf:
        zf.extractall(CURRENT)

    # Branch/tag/commit inventory.
    branches = run([
        "git", "-C", str(MIRROR), "for-each-ref", "--sort=refname",
        "--format=%(refname:short)|%(objectname)|%(objecttype)", "refs/heads"
    ], capture=True).stdout
    tags = run([
        "git", "-C", str(MIRROR), "for-each-ref", "--sort=refname",
        "--format=%(refname:short)|%(objectname)|%(objecttype)", "refs/tags"
    ], capture=True).stdout
    history = run([
        "git", "-C", str(MIRROR), "log", "--all", "--date=iso-strict",
        "--pretty=format:%H|%cI|%an|%D|%s"
    ], capture=True).stdout
    write(APP / "BRANCHES.txt", branches)
    write(APP / "TAGS.txt", tags or "(NO TAGS FOUND)")
    write(APP / "COMMIT_HISTORY.txt", history)
    write(APP / "MAIN_COMMIT.txt", MAIN_SHA)
    write(APP / "CURRENT_WORK_COMMIT.txt", WORK_SHA)
    write(APP / "REPOSITORY_INFO.txt", f"""
REPOSITORY={REPO}
VISIBILITY=public
DEFAULT_BRANCH=main
BACKUP_DATE_WIB=2026-10-07
BACKUP_TIME_WIB=23:55
MAIN_COMMIT={MAIN_SHA}
CURRENT_WORK_BRANCH={WORK_BRANCH}
CURRENT_WORK_COMMIT={WORK_SHA}
BRANCH_COUNT={len([x for x in branches.splitlines() if x.strip()])}
TAG_COUNT={len([x for x in tags.splitlines() if x.strip()])}
COMMIT_RECORD_COUNT={len([x for x in history.splitlines() if x.strip()])}
""")

    # Latest trusted portable artifact already produced by main/UI04.
    build_ok = False
    try:
        run(["gh", "run", "download", WINDOWS_RUN, "-R", REPO,
             "-n", WINDOWS_ARTIFACT, "-D", str(APP / "BUILD")])
        build_ok = any(p.is_file() and p.name != "BUILD_STATUS.txt" for p in (APP / "BUILD").rglob("*"))
    except subprocess.CalledProcessError as exc:
        print(f"Build download failed: {exc}", file=sys.stderr)
    if build_ok:
        write(APP / "BUILD" / "BUILD_STATUS.txt", f"""
BUILD_AVAILABLE
SOURCE_RUN={WINDOWS_RUN}
ARTIFACT_NAME={WINDOWS_ARTIFACT}
SOURCE_COMMIT={MAIN_SHA}
NOTE=Latest trusted Windows Portable build available from main at backup time. UI05 remains unmerged.
""")
    else:
        write(APP / "BUILD" / "BUILD_NOT_AVAILABLE.txt", "BUILD_NOT_AVAILABLE")
        write(APP / "BUILD" / "BUILD_STATUS.txt",
              f"BUILD_NOT_AVAILABLE\nAttempted run={WINDOWS_RUN} artifact={WINDOWS_ARTIFACT}")

    # Record secret NAMES only.
    names: set[str] = set()
    for _, text in iter_text_files(CURRENT):
        names.update(re.findall(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text))
        names.update(re.findall(
            r"(?:getenv|environ\.get)\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_]*)['\"]",
            text,
        ))
    req_lines = ["SECRET_REQUIRED_BUT_NOT_BACKED_UP", "", "Credential values are intentionally excluded."]
    req_lines += (["", "Names detected in source/workflows:"] + [f"- {n}" for n in sorted(names)]
                  if names else ["", "No explicit secret names detected in current tracked source."])
    write(APP / "REQUIRED_SECRETS.txt", "\n".join(req_lines))

    # High-confidence secret scan: current tree + every reachable commit.
    patterns = {
        "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        "GITHUB_PAT": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b"),
        "GOOGLE_API_KEY": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "OPENAI_STYLE_KEY": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    }
    findings: list[str] = []
    for p, text in iter_text_files(CURRENT):
        for label, rx in patterns.items():
            if rx.search(text):
                findings.append(f"CURRENT|{label}|{p.relative_to(CURRENT)}")

    commits = run(["git", "-C", str(MIRROR), "rev-list", "--all"], capture=True).stdout.splitlines()
    grep_rx = r"(-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,})"
    seen: set[str] = set()
    for commit in commits:
        proc = run(
            ["git", "-C", str(MIRROR), "grep", "-I", "-n", "-E", grep_rx, commit, "--", "."],
            capture=True, check=False,
        )
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"git grep failed on {commit}")
        for line in (proc.stdout or "").splitlines():
            normalized = line.split(":", 1)[-1]
            if normalized not in seen:
                seen.add(normalized)
                findings.append(f"HISTORY|{commit}|{normalized[:500]}")
    if findings:
        write(APP / "SECRET_SCAN.txt",
              "SECRET_SCAN_FAIL\nHigh-confidence credential material detected. Distribution blocked.\n\n"
              + "\n".join(findings[:200]))
        raise RuntimeError("High-confidence credential pattern found in reachable history")
    write(APP / "SECRET_SCAN.txt",
          "SECRET_SCAN_PASS\nNo high-confidence API key/PAT/private-key pattern detected in current tracked source or reachable Git history.")

    # Recovery documentation/scripts.
    write(APP / "README_RESTORE.txt", f"""
FULL ALBUM MAKER — SINGLE APP BACKUP
====================================
Backup timestamp: 2026-10-07 23:55 WIB.

Included:
- complete verified Git Bundle;
- main source ZIP;
- UI05 in-progress source ZIP;
- branch/tag/commit inventory;
- docs + workflow snapshot;
- latest trusted Windows Portable build when downloadable;
- Windows PowerShell verify/restore scripts.

IMPORTANT:
main and UI05 are intentionally separate.
UI05 passed STEP06 Visual validation run {UI05_RUN} but was not merged into main.
Credentials are never backed up.
""")
    status = "BACKUP_COMPLETE" if build_ok else "BACKUP_PARTIAL"
    write(APP / "STATUS_BACKUP.txt", f"""
{status}
APP=Full-Album-Maker
MAIN={MAIN_SHA}
CURRENT_WORK_BRANCH={WORK_BRANCH}
CURRENT_WORK_COMMIT={WORK_SHA}
GIT_BUNDLE=VERIFIED
SOURCE_MAIN=VERIFIED
SOURCE_UI05_IN_PROGRESS=VERIFIED
UI05_VALIDATION_RUN={UI05_RUN}
WINDOWS_BUILD_RUN={WINDOWS_RUN}
BUILD={'AVAILABLE' if build_ok else 'BUILD_NOT_AVAILABLE'}
SECRET_SCAN=PASS
""")
    write(APP / "RECOVERY" / "PETUNJUK_PEMULIHAN.txt", """
PEMULIHAN KE GITHUB BARU — WINDOWS 11
=====================================
1. Ekstrak MASTER BACKUP ke SSD/HDD.
2. Jalankan VERIFY_BACKUP.ps1.
3. Pastikan checksum dan Git Bundle PASS.
4. Buat repo GitHub BARU dan KOSONG bernama Full-Album-Maker.
5. Jalankan RESTORE_TO_NEW_GITHUB.ps1.
6. Masukkan URL: https://github.com/AKUN-BARU/Full-Album-Maker.git
7. Script membuat repo lokal dari Git Bundle dan BELUM push otomatis.
8. Ketik PUSH hanya setelah memeriksa URL/branch/tag.
9. Pasang kembali secret yang disebut REQUIRED_SECRETS.txt secara manual.
10. Jalankan workflow build.
11. Cocokkan MAIN_COMMIT.txt dan CURRENT_WORK_COMMIT.txt.
""")
    write(APP / "RECOVERY" / "VERIFY_BACKUP.ps1", r'''
$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
$ChecksumFile = Join-Path $AppRoot "SHA256SUMS.txt"
if (-not (Test-Path $ChecksumFile)) { throw "SHA256SUMS.txt tidak ditemukan." }
$failed = $false
Get-Content $ChecksumFile | ForEach-Object {
  if ($_ -match '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
    $expected = $Matches[1].ToLower()
    $relative = $Matches[2]
    $path = Join-Path $AppRoot $relative
    if (-not (Test-Path $path)) { Write-Host "MISSING $relative" -ForegroundColor Red; $failed = $true }
    else {
      $actual = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLower()
      if ($actual -eq $expected) { Write-Host "PASS $relative" -ForegroundColor Green }
      else { Write-Host "FAIL $relative" -ForegroundColor Red; $failed = $true }
    }
  }
}
$bundle = Join-Path $AppRoot "GIT\Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle"
git bundle verify $bundle
if ($LASTEXITCODE -ne 0) { throw "Git Bundle gagal diverifikasi." }
if ($failed) { throw "Satu atau lebih checksum gagal." }
Write-Host "BACKUP VERIFIED" -ForegroundColor Green
''')
    write(APP / "RECOVERY" / "RESTORE_TO_NEW_GITHUB.ps1", r'''
param([string]$NewRepoUrl)
$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot "VERIFY_BACKUP.ps1")
if (-not $NewRepoUrl) { $NewRepoUrl = Read-Host "URL repo GitHub BARU (repo kosong)" }
if ($NewRepoUrl -notmatch '^https://github\.com/.+/.+\.git$') { throw "URL GitHub tidak valid." }
$bundle = Join-Path $AppRoot "GIT\Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle"
$restoreRoot = Join-Path $AppRoot "RESTORED_WORKTREE"
if (Test-Path $restoreRoot) {
  $answer = Read-Host "RESTORED_WORKTREE sudah ada. Hapus? ketik YA"
  if ($answer -ne "YA") { throw "Dibatalkan." }
  Remove-Item -Recurse -Force $restoreRoot
}
git clone $bundle $restoreRoot
if ($LASTEXITCODE -ne 0) { throw "Clone Git Bundle gagal." }
Push-Location $restoreRoot
try {
  git remote remove origin 2>$null
  git remote add origin $NewRepoUrl
  Write-Host "BELUM ADA YANG DI-PUSH." -ForegroundColor Yellow
  git branch -a
  git tag
  $confirm = Read-Host "Ketik PUSH untuk mengirim semua branch/tag"
  if ($confirm -ne "PUSH") { Write-Host "Push dibatalkan."; exit 0 }
  git push origin --all
  if ($LASTEXITCODE -ne 0) { throw "Push branch gagal." }
  git push origin --tags
  if ($LASTEXITCODE -ne 0) { throw "Push tag gagal." }
  Write-Host "RESTORE SELESAI" -ForegroundColor Green
} finally { Pop-Location }
''')
    write(MASTER / "RESTORE_ALL.ps1", r'''
$ErrorActionPreference = "Stop"
Write-Host "MASTER BACKUP — PILIH APLIKASI"
Write-Host "[1] Full-Album-Maker"
$choice = Read-Host "Pilih nomor"
if ($choice -ne "1") { throw "Pilihan tidak valid." }
& (Join-Path $PSScriptRoot "APP_001_FULL_ALBUM_MAKER\RECOVERY\RESTORE_TO_NEW_GITHUB.ps1")
''')
    write(MASTER / "VERIFY_ALL_BACKUP.ps1", r'''
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$ChecksumFile = Join-Path $Root "00_SHA256SUMS.txt"
if (-not (Test-Path $ChecksumFile)) { throw "00_SHA256SUMS.txt tidak ditemukan." }
$failed = $false
Get-Content $ChecksumFile | ForEach-Object {
  if ($_ -match '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
    $expected = $Matches[1].ToLower()
    $relative = $Matches[2]
    $path = Join-Path $Root $relative
    if (-not (Test-Path $path)) { Write-Host "MISSING $relative" -ForegroundColor Red; $failed = $true }
    else {
      $actual = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLower()
      if ($actual -eq $expected) { Write-Host "PASS $relative" -ForegroundColor Green }
      else { Write-Host "FAIL $relative" -ForegroundColor Red; $failed = $true }
    }
  }
}
& (Join-Path $Root "APP_001_FULL_ALBUM_MAKER\RECOVERY\VERIFY_BACKUP.ps1")
if ($failed) { throw "Verifikasi master checksum gagal." }
Write-Host "SEMUA BACKUP TERVERIFIKASI" -ForegroundColor Green
''')

    build_status = "BUILD_AVAILABLE" if build_ok else "BUILD_NOT_AVAILABLE"
    write(MASTER / "00_README_PERTAMA.txt", f"""
MASTER BACKUP KHUSUS: Full-Album-Maker
Tanggal/Jam: 2026-10-07 23:55 WIB
Repo: https://github.com/{REPO}
Main: {MAIN_SHA}
Pekerjaan aktif: {WORK_BRANCH} @ {WORK_SHA}
Status: {status}

Jalankan VERIFY_ALL_BACKUP.ps1 sebelum restore.
Gunakan RESTORE_ALL.ps1 jika GitHub lama tidak dapat diakses.
Credential tidak disimpan.
""")
    write(MASTER / "00_BACKUP_INFO.txt", f"""
BACKUP_TYPE=SINGLE_APP
APP=Full-Album-Maker
BACKUP_DATE_WIB=2026-10-07
BACKUP_TIME_WIB=23:55
ORIGINAL_REPO=https://github.com/{REPO}
DEFAULT_BRANCH=main
MAIN_COMMIT={MAIN_SHA}
CURRENT_WORK_BRANCH={WORK_BRANCH}
CURRENT_WORK_COMMIT={WORK_SHA}
UI05_VALIDATION_RUN={UI05_RUN}
WINDOWS_BUILD_RUN={WINDOWS_RUN}
BUILD_STATUS={build_status}
GIT_BUNDLE_SIZE_BYTES={bundle.stat().st_size}
SECRETS=SECRET_REQUIRED_BUT_NOT_BACKED_UP
""")
    write(MASTER / "00_MASTER_MANIFEST.txt", f"""
TOTAL_PROYEK=1

APP NAME=Full-Album-Maker
ORIGINAL REPO=https://github.com/{REPO}
BACKUP DATE=2026-10-07 23:55 WIB
DEFAULT BRANCH=main
MAIN COMMIT={MAIN_SHA}
CURRENT WORK BRANCH={WORK_BRANCH}
CURRENT WORK COMMIT={WORK_SHA}
GIT BUNDLE=APP_001_FULL_ALBUM_MAKER/GIT/Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle
GIT BUNDLE STATUS=VERIFIED
SOURCE SNAPSHOT MAIN=APP_001_FULL_ALBUM_MAKER/SOURCE/Full-Album-Maker-SOURCE-MAIN.zip
SOURCE SNAPSHOT CURRENT=APP_001_FULL_ALBUM_MAKER/SOURCE/Full-Album-Maker-SOURCE-UI05-IN-PROGRESS.zip
BUILD={build_status}
DOCS=APP_001_FULL_ALBUM_MAKER/DOCS/Full-Album-Maker-DOCS-UI05-IN-PROGRESS.zip
RECOVERY SCRIPT=APP_001_FULL_ALBUM_MAKER/RECOVERY/RESTORE_TO_NEW_GITHUB.ps1
BACKUP STATUS={status}
CHECKSUM STATUS=VERIFIED_BEFORE_PACKAGING
""")
    with (MASTER / "00_MASTER_MANIFEST.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["APP_NAME","ORIGINAL_REPO","DEFAULT_BRANCH","MAIN_COMMIT","CURRENT_WORK_BRANCH",
                    "CURRENT_WORK_COMMIT","SOURCE_STATUS","BUILD_STATUS","DOC_STATUS","BACKUP_STATUS"])
        w.writerow(["Full-Album-Maker",f"https://github.com/{REPO}","main",MAIN_SHA,WORK_BRANCH,WORK_SHA,
                    "SOURCE_MAIN_AND_UI05",build_status,"INCLUDED",status])

    checksums_for(APP, "SHA256SUMS.txt")
    checksums_for(MASTER, "00_SHA256SUMS.txt")
    verify_checksums(APP, "SHA256SUMS.txt")
    verify_checksums(MASTER, "00_SHA256SUMS.txt")

    # Final gates.
    run(["git", "-C", str(MIRROR), "bundle", "verify", str(bundle)])
    if not (APP / "BRANCHES.txt").stat().st_size or not (APP / "COMMIT_HISTORY.txt").stat().st_size:
        raise RuntimeError("Ref/history inventory empty")
    if len([p for p in MASTER.iterdir() if p.is_dir() and p.name.startswith("APP_")]) != 1:
        raise RuntimeError("Project folder count mismatch")
    if "TOTAL_PROYEK=1" not in (MASTER / "00_MASTER_MANIFEST.txt").read_text(encoding="utf-8"):
        raise RuntimeError("Manifest project count mismatch")

    final_zip = ROOT / f"{MASTER_NAME}.zip"
    if final_zip.exists():
        final_zip.unlink()
    shutil.make_archive(str(final_zip.with_suffix("")), "zip", root_dir=MASTER.parent, base_dir=MASTER.name)
    check_zip(final_zip, minimum_entries=20)
    write(ROOT / f"{MASTER_NAME}.zip.sha256", f"{sha256(final_zip)}  {final_zip.name}")

    extract_test = ROOT / "final-extract-test"
    with zipfile.ZipFile(final_zip) as zf:
        zf.extractall(extract_test)
    required = [
        extract_test / MASTER_NAME / "00_MASTER_MANIFEST.txt",
        extract_test / MASTER_NAME / "VERIFY_ALL_BACKUP.ps1",
        extract_test / MASTER_NAME / "APP_001_FULL_ALBUM_MAKER" / "GIT" / bundle.name,
        extract_test / MASTER_NAME / "APP_001_FULL_ALBUM_MAKER" / "SOURCE" / src_main.name,
    ]
    if not all(p.is_file() for p in required):
        raise RuntimeError("Final ZIP structure verification failed")

    print(f"FINAL_BACKUP={final_zip}")
    print(f"FINAL_SHA256={sha256(final_zip)}")
    print(f"FINAL_SIZE={final_zip.stat().st_size}")
    print(f"FINAL_STATUS={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
