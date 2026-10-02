# STEP 00 Backup / Restore Gate

Overall backup gate: **LOCAL_PENDING**.

The rescue artifacts themselves are hash-verified and remained untouched, and the recovery branch is pushed to GitHub. A standalone Git bundle/restore rehearsal was not created because STEP 00 did not have a persistent user-local clone to place and verify that bundle.

## Verified now

- outer rescue portable ZIP SHA-256 verified;
- inner portable v1.4.1 ZIP SHA-256 verified;
- recovery-package ZIP SHA-256 verified;
- planning/recovery input hashes recorded;
- exact v1.4.0 source snapshot is committed on `recovery/step-00-r0`;
- remote recovery branch exists and can be read back;
- `main` was not force-pushed or used as the STEP 00 write target;
- no rescue binary ZIP was committed into the application source tree.

## LOCAL_PENDING — create and verify a Git bundle on the user's Windows clone

Run after cloning/fetching the repo:

```powershell
git clone https://github.com/inoriko920-dev/Full-Album-Maker.git Full-Album-Maker-step00
cd Full-Album-Maker-step00
git fetch origin main recovery/step-00-r0
git branch step00-r0 origin/recovery/step-00-r0

git bundle create Full-Album-Maker-STEP00-R0.bundle main step00-r0
git bundle verify Full-Album-Maker-STEP00-R0.bundle
Get-FileHash .\Full-Album-Maker-STEP00-R0.bundle -Algorithm SHA256
```

Then perform a restore rehearsal into a new folder:

```powershell
cd ..
New-Item -ItemType Directory -Force step00-restore-test | Out-Null
cd step00-restore-test
git clone ..\Full-Album-Maker-step00\Full-Album-Maker-STEP00-R0.bundle restored
cd restored
git show-ref
git log --oneline --decorate --all -20
```

Expected recovery branch content can then be checked out from the bundle-created ref. Record the bundle SHA-256 and restore-test result before changing the backup gate from `LOCAL_PENDING` to `VERIFIED`.

## Rescue restore rule

The original rescue ZIPs remain independent evidence and must stay outside normal source editing. Do not overwrite them with later builds. If a new portable is produced in a later step, give it a new versioned artifact name and its own checksum instead of replacing the preserved rescue artifact.
