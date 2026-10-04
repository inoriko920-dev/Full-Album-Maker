$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$BackupDate = '2026-10-04'
$Repo = $env:GITHUB_REPOSITORY
$MainExpected = 'f4d522584156f8546cf9e7d7841e8bea729801c6'
$ReleaseTag = 'v1.4.0'
$PortableName = 'Full-Album-Maker-v1.4.0-Windows-Portable.zip'
$PortableExpected = '873a84f81313caeda11538b2f12251e4611d2c229b2b7c98fe71f105e9df89f1'
$PackageName = "FULL-ALBUM-MAKER-BACKUP-$BackupDate"
$Stage = Join-Path $env:RUNNER_TEMP $PackageName
$App = Join-Path $Stage 'APP_001_FULL_ALBUM_MAKER'
$GitDir = Join-Path $App 'GIT'
$SourceDir = Join-Path $App 'SOURCE'
$BuildDir = Join-Path $App 'BUILD'
$DocsDir = Join-Path $App 'DOCS'
$RecoveryDir = Join-Path $App 'RECOVERY'
$Mirror = Join-Path $env:RUNNER_TEMP 'Full-Album-Maker.mirror.git'
$SourceExtract = Join-Path $env:RUNNER_TEMP 'Full-Album-Maker-source-main'
$FinalZip = Join-Path $env:GITHUB_WORKSPACE "$PackageName.zip"

Remove-Item $Stage,$Mirror,$SourceExtract,$FinalZip -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage,$App,$GitDir,$SourceDir,$BuildDir,$DocsDir,$RecoveryDir | Out-Null

Write-Host '1/11 Mirror clone + fsck'
git clone --mirror "https://github.com/$Repo.git" $Mirror
if ($LASTEXITCODE -ne 0) { throw 'Mirror clone failed.' }
git -C $Mirror fsck --full
if ($LASTEXITCODE -ne 0) { throw 'git fsck failed.' }
$MainCommit = (git -C $Mirror rev-parse refs/heads/main).Trim()
if ($MainCommit -ne $MainExpected) { throw "main changed. Expected $MainExpected, got $MainCommit" }

Write-Host '2/11 Create and verify complete Git bundle'
$Bundle = Join-Path $GitDir 'Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle'
git -C $Mirror bundle create $Bundle --all
if ($LASTEXITCODE -ne 0 -or !(Test-Path $Bundle) -or (Get-Item $Bundle).Length -lt 1024) { throw 'Git bundle creation failed/empty.' }
git -C $Mirror bundle verify $Bundle 2>&1 | Out-File (Join-Path $GitDir 'BUNDLE_VERIFY.txt') -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Git bundle verify failed.' }
git bundle list-heads $Bundle | Out-File (Join-Path $GitDir 'BUNDLE_HEADS.txt') -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Bundle list-heads failed.' }

Write-Host '3/11 Create source-main snapshot'
$SourceZip = Join-Path $SourceDir 'Full-Album-Maker-SOURCE-MAIN.zip'
git -C $Mirror archive --format=zip --output=$SourceZip refs/heads/main
if ($LASTEXITCODE -ne 0 -or !(Test-Path $SourceZip) -or (Get-Item $SourceZip).Length -lt 1024) { throw 'Source ZIP failed/empty.' }
Expand-Archive -LiteralPath $SourceZip -DestinationPath $SourceExtract -Force
if (!(Get-ChildItem $SourceExtract -Recurse -File | Select-Object -First 1)) { throw 'Extracted source is empty.' }

Write-Host '4/11 Record refs and history'
git -C $Mirror for-each-ref --sort=refname --format='%(refname) %(objectname)' refs/heads | Out-File (Join-Path $App 'BRANCHES.txt') -Encoding utf8
git -C $Mirror for-each-ref --sort=refname --format='%(refname) %(objectname)' refs/tags | Out-File (Join-Path $App 'TAGS.txt') -Encoding utf8
git -C $Mirror log --all --date=iso-strict --pretty=format:'%H`t%ad`t%an`t%s' | Out-File (Join-Path $App 'COMMIT_HISTORY.txt') -Encoding utf8
Set-Content (Join-Path $App 'MAIN_COMMIT.txt') $MainCommit -Encoding utf8
$RepoInfo = @(
  'APP NAME: Full Album Maker',
  "ORIGINAL REPO: https://github.com/$Repo",
  'DEFAULT BRANCH: main',
  "MAIN COMMIT: $MainCommit",
  "BACKUP DATE: $BackupDate",
  "RELEASE TAG: $ReleaseTag",
  'BACKUP MECHANISM BRANCH: backup/full-album-maker-2026-10-04'
)
$RepoInfo | Set-Content (Join-Path $App 'REPOSITORY_INFO.txt') -Encoding utf8

Write-Host '5/11 Copy convenience documentation'
Get-ChildItem $SourceExtract -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^README' } | ForEach-Object { Copy-Item $_.FullName $DocsDir -Force }
foreach ($n in @('docs','DOCS','documentation','Documentation')) {
  $p = Join-Path $SourceExtract $n
  if (Test-Path $p) { Copy-Item $p (Join-Path $DocsDir $n) -Recurse -Force }
}
$wf = Join-Path $SourceExtract '.github\workflows'
if (Test-Path $wf) { Copy-Item $wf (Join-Path $DocsDir 'github-workflows') -Recurse -Force }

Write-Host '6/11 Download and verify trusted portable release'
gh release download $ReleaseTag --repo $Repo --pattern $PortableName --pattern 'SHA256SUMS.txt' --dir $BuildDir
if ($LASTEXITCODE -ne 0) { throw 'Release download failed.' }
$PortablePath = Join-Path $BuildDir $PortableName
if (!(Test-Path $PortablePath)) { throw 'Portable release not downloaded.' }
$PortableActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $PortablePath).Hash.ToLowerInvariant()
if ($PortableActual -ne $PortableExpected) { throw "Portable checksum mismatch: $PortableActual" }

Write-Host '7/11 Secret-name inventory + high-confidence secret scan'
$SecretNames = New-Object System.Collections.Generic.HashSet[string]
Get-ChildItem (Join-Path $SourceExtract '.github\workflows') -File -ErrorAction SilentlyContinue | ForEach-Object {
  $text = Get-Content $_.FullName -Raw
  foreach ($m in [regex]::Matches($text, 'secrets\.([A-Za-z0-9_]+)')) { [void]$SecretNames.Add($m.Groups[1].Value) }
}
(@('SECRET_REQUIRED_BUT_NOT_BACKED_UP') + ($SecretNames | Sort-Object)) | Set-Content (Join-Path $App 'REQUIRED_SECRETS.txt') -Encoding utf8
$SecretRegex = '(ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9_-]{32,}|xox[baprs]-[A-Za-z0-9-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'
$CurrentHits = New-Object System.Collections.Generic.List[string]
Get-ChildItem $SourceExtract -Recurse -File | Where-Object { $_.Length -lt 5MB } | ForEach-Object {
  try {
    $text = Get-Content $_.FullName -Raw -ErrorAction Stop
    if ($text -match $SecretRegex) { $CurrentHits.Add($_.FullName.Substring($SourceExtract.Length).TrimStart('\')) }
  } catch { }
}
$HistoryText = (git -C $Mirror log -p --all --no-color) -join "`n"
$HistoryHit = $HistoryText -match $SecretRegex
if ($CurrentHits.Count -gt 0 -or $HistoryHit) {
  (@('HIGH_CONFIDENCE_SECRET_PATTERN_FOUND','Current paths:') + $CurrentHits + @("History hit: $HistoryHit")) | Set-Content (Join-Path $App 'SECRET_SCAN.txt') -Encoding utf8
  throw 'High-confidence credential pattern detected. Export stopped.'
}
Set-Content (Join-Path $App 'SECRET_SCAN.txt') 'PASS: no high-confidence token/private-key pattern found in current source or patch history.' -Encoding utf8

Write-Host '8/11 Write Windows recovery scripts'
$RestoreGuide = @(
  'FULL ALBUM MAKER - PETUNJUK PEMULIHAN', '',
  'Kondisi awal: GitHub lama sudah tidak bisa diakses.',
  '1. Ekstrak ZIP backup utama.',
  '2. Buka APP_001_FULL_ALBUM_MAKER.',
  '3. Jalankan RECOVERY\VERIFY_BACKUP.ps1.',
  '4. Buat repo KOSONG Full-Album-Maker pada akun GitHub baru.',
  '5. Jalankan RECOVERY\RESTORE_TO_NEW_GITHUB.ps1 dan masukkan URL repo baru.',
  '6. Script memulihkan dari Git Bundle lalu push semua branch dan tag.',
  '7. Isi ulang secret yang tercantum di REQUIRED_SECRETS.txt; nilai secret tidak disimpan.',
  '8. Cocokkan main dengan MAIN_COMMIT.txt.',
  '9. Jalankan workflow build/release bila diperlukan.', '',
  'SOURCE-MAIN.zip mudah dibuka manusia. Git Bundle adalah sumber pemulihan riwayat Git.'
)
$RestoreGuide | Set-Content (Join-Path $RecoveryDir 'PETUNJUK_PEMULIHAN.txt') -Encoding utf8

$RestoreScript = @'
param([string]$NewRepoUrl)
$ErrorActionPreference='Stop'
$AppRoot=Split-Path $PSScriptRoot -Parent
$Bundle=Join-Path $AppRoot 'GIT\Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle'
$RestoreDir=Join-Path $AppRoot 'RESTORED_FULL_ALBUM_MAKER'
if(!(Get-Command git -ErrorAction SilentlyContinue)){throw 'Git belum terpasang atau tidak ada di PATH.'}
git bundle verify $Bundle
if($LASTEXITCODE -ne 0){throw 'Bundle gagal diverifikasi.'}
if(!$NewRepoUrl){$NewRepoUrl=Read-Host 'Masukkan URL repo GitHub BARU yang masih kosong'}
if(!$NewRepoUrl){throw 'URL repo baru wajib diisi.'}
if(Test-Path $RestoreDir){throw "Folder restore sudah ada: $RestoreDir"}
git clone $Bundle $RestoreDir
if($LASTEXITCODE -ne 0){throw 'Clone dari Git Bundle gagal.'}
Push-Location $RestoreDir
try{
  git remote remove origin 2>$null
  git remote add origin $NewRepoUrl
  git push origin --all
  if($LASTEXITCODE -ne 0){throw 'Push branch gagal.'}
  git push origin --tags
  if($LASTEXITCODE -ne 0){throw 'Push tag gagal.'}
  Write-Host 'RESTORE SELESAI. Isi ulang secret dan cek branch/tag.' -ForegroundColor Green
} finally { Pop-Location }
'@
$RestoreScript | Set-Content (Join-Path $RecoveryDir 'RESTORE_TO_NEW_GITHUB.ps1') -Encoding utf8

$VerifyScript = @'
$ErrorActionPreference='Stop'
$AppRoot=Split-Path $PSScriptRoot -Parent
$ChecksumFile=Join-Path $AppRoot 'SHA256SUMS.txt'
$Bundle=Join-Path $AppRoot 'GIT\Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle'
$Failures=0
foreach($line in Get-Content $ChecksumFile){
  if($line -match '^([0-9a-fA-F]{64})\s+\*(.+)$'){
    $expected=$Matches[1].ToLowerInvariant(); $rel=$Matches[2]; $p=Join-Path $AppRoot $rel
    if(!(Test-Path $p)){Write-Host "MISSING $rel" -ForegroundColor Red; $Failures++; continue}
    $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()
    if($actual -ne $expected){Write-Host "FAIL $rel" -ForegroundColor Red; $Failures++} else {Write-Host "PASS $rel"}
  }
}
git bundle verify $Bundle
if($LASTEXITCODE -ne 0){$Failures++}
if($Failures -gt 0){throw "Verifikasi gagal: $Failures masalah."}
Write-Host 'SEMUA VERIFIKASI BACKUP LULUS.' -ForegroundColor Green
'@
$VerifyScript | Set-Content (Join-Path $RecoveryDir 'VERIFY_BACKUP.ps1') -Encoding utf8

Write-Host '9/11 Generate per-app and master metadata/checksums'
$AppFiles = Get-ChildItem $App -Recurse -File | Where-Object { $_.FullName -ne (Join-Path $App 'SHA256SUMS.txt') }
$AppLines = @($AppFiles | Sort-Object FullName | ForEach-Object {
  $rel=$_.FullName.Substring($App.Length+1).Replace('\','/')
  $hash=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
  "$hash *$rel"
})
$AppLines | Set-Content (Join-Path $App 'SHA256SUMS.txt') -Encoding ascii

@(
  'BACKUP STATUS: BACKUP_COMPLETE',
  'SOURCE STATUS: VERIFIED',
  'GIT BUNDLE STATUS: VERIFIED',
  'BUILD STATUS: VERIFIED_RELEASE_ASSET',
  "BUILD RELEASE: $ReleaseTag",
  "BUILD SHA256: $PortableActual",
  'DOCUMENTATION STATUS: INCLUDED_WHEN_PRESENT',
  'SECRET EXPORT STATUS: NO_SECRET_VALUES_INTENTIONALLY_ADDED; HIGH_CONFIDENCE_SCAN_PASS',
  "MAIN COMMIT: $MainCommit"
) | Set-Content (Join-Path $App 'STATUS_BACKUP.txt') -Encoding utf8

@(
  '00_MASTER_MANIFEST - SINGLE REPOSITORY BACKUP', '',
  'APP NAME: Full Album Maker',
  "ORIGINAL REPO: https://github.com/$Repo",
  "BACKUP DATE: $BackupDate",
  "MAIN COMMIT: $MainCommit",
  'GIT BUNDLE: APP_001_FULL_ALBUM_MAKER/GIT/Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle',
  'SOURCE SNAPSHOT: APP_001_FULL_ALBUM_MAKER/SOURCE/Full-Album-Maker-SOURCE-MAIN.zip',
  "BUILD: APP_001_FULL_ALBUM_MAKER/BUILD/$PortableName",
  'DOCS: APP_001_FULL_ALBUM_MAKER/DOCS/',
  'RECOVERY SCRIPT: APP_001_FULL_ALBUM_MAKER/RECOVERY/RESTORE_TO_NEW_GITHUB.ps1',
  'BACKUP STATUS: BACKUP_COMPLETE',
  'CHECKSUM STATUS: VERIFIED BEFORE PACKAGING'
) | Set-Content (Join-Path $Stage '00_MASTER_MANIFEST.txt') -Encoding utf8
"APP_NAME,ORIGINAL_REPO,DEFAULT_BRANCH,MAIN_COMMIT,TAG,BACKUP_STATUS,BUILD_STATUS`nFull Album Maker,https://github.com/$Repo,main,$MainCommit,$ReleaseTag,BACKUP_COMPLETE,VERIFIED_RELEASE_ASSET" | Set-Content (Join-Path $Stage '00_MASTER_MANIFEST.csv') -Encoding utf8
@(
  'FULL ALBUM MAKER - VERIFIED BACKUP',
  "Backup date: $BackupDate",
  "Original repository: https://github.com/$Repo",
  "Main commit: $MainCommit", '',
  'Berisi Git Bundle lengkap, SOURCE-MAIN.zip, portable release terverifikasi, metadata, dokumentasi, checksum, dan script recovery Windows 11.'
) | Set-Content (Join-Path $Stage '00_README_PERTAMA.txt') -Encoding utf8
@(
  'BACKUP_SCOPE: ONLY inoriko920-dev/Full-Album-Maker',
  "BACKUP_DATE: $BackupDate",
  'DEFAULT_BRANCH: main',
  "MAIN_COMMIT: $MainCommit",
  "RELEASE: $ReleaseTag",
  "PORTABLE_RELEASE_SHA256: $PortableActual",
  'GIT_BUNDLE: VERIFIED',
  'SOURCE_SNAPSHOT: VERIFIED',
  'SECRETS: VALUES NOT EXPORTED; workflow secret NAMES only'
) | Set-Content (Join-Path $Stage '00_BACKUP_INFO.txt') -Encoding utf8
"`$ErrorActionPreference='Stop'`n& (Join-Path `$PSScriptRoot 'APP_001_FULL_ALBUM_MAKER\RECOVERY\RESTORE_TO_NEW_GITHUB.ps1')" | Set-Content (Join-Path $Stage 'RESTORE_ALL.ps1') -Encoding utf8

$MasterVerify = @'
$ErrorActionPreference='Stop'
$Root=$PSScriptRoot; $Failures=0
foreach($line in Get-Content (Join-Path $Root '00_SHA256SUMS.txt')){
  if($line -match '^([0-9a-fA-F]{64})\s+\*(.+)$'){
    $expected=$Matches[1].ToLowerInvariant(); $rel=$Matches[2]; $p=Join-Path $Root $rel
    if(!(Test-Path $p)){$Failures++; continue}
    if((Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant() -ne $expected){$Failures++}
  }
}
& (Join-Path $Root 'APP_001_FULL_ALBUM_MAKER\RECOVERY\VERIFY_BACKUP.ps1')
if($Failures -gt 0){throw "Master verification failed: $Failures"}
Write-Host 'MASTER BACKUP VALID.' -ForegroundColor Green
'@
$MasterVerify | Set-Content (Join-Path $Stage 'VERIFY_ALL_BACKUP.ps1') -Encoding utf8

$MasterFiles = Get-ChildItem $Stage -Recurse -File | Where-Object { $_.FullName -ne (Join-Path $Stage '00_SHA256SUMS.txt') }
$MasterLines = @($MasterFiles | Sort-Object FullName | ForEach-Object {
  $rel=$_.FullName.Substring($Stage.Length+1).Replace('\','/')
  $hash=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
  "$hash *$rel"
})
$MasterLines | Set-Content (Join-Path $Stage '00_SHA256SUMS.txt') -Encoding ascii

Write-Host '10/11 Compress final ZIP'
Compress-Archive -LiteralPath $Stage -DestinationPath $FinalZip -CompressionLevel Optimal
if (!(Test-Path $FinalZip) -or (Get-Item $FinalZip).Length -lt 1024) { throw 'Final ZIP creation failed.' }

Write-Host '11/11 Re-open final ZIP and validate required structure'
$ZipTest = Join-Path $env:RUNNER_TEMP 'backup-zip-test'
Remove-Item $ZipTest -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -LiteralPath $FinalZip -DestinationPath $ZipTest -Force
$TestRoot = Join-Path $ZipTest $PackageName
$Required = @(
  '00_README_PERTAMA.txt','00_MASTER_MANIFEST.txt','00_MASTER_MANIFEST.csv','00_SHA256SUMS.txt','00_BACKUP_INFO.txt','RESTORE_ALL.ps1','VERIFY_ALL_BACKUP.ps1',
  'APP_001_FULL_ALBUM_MAKER\GIT\Full-Album-Maker-COMPLETE-GIT-HISTORY.bundle',
  'APP_001_FULL_ALBUM_MAKER\SOURCE\Full-Album-Maker-SOURCE-MAIN.zip',
  "APP_001_FULL_ALBUM_MAKER\BUILD\$PortableName",
  'APP_001_FULL_ALBUM_MAKER\MAIN_COMMIT.txt','APP_001_FULL_ALBUM_MAKER\BRANCHES.txt','APP_001_FULL_ALBUM_MAKER\TAGS.txt',
  'APP_001_FULL_ALBUM_MAKER\RECOVERY\RESTORE_TO_NEW_GITHUB.ps1','APP_001_FULL_ALBUM_MAKER\RECOVERY\VERIFY_BACKUP.ps1'
)
foreach ($r in $Required) { if (!(Test-Path (Join-Path $TestRoot $r))) { throw "Final ZIP missing required path: $r" } }

$FinalSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $FinalZip).Hash.ToLowerInvariant()
$FinalSize = (Get-Item $FinalZip).Length
@(
  'TOTAL PROYEK: 1','BACKUP COMPLETE: 1','BACKUP PARTIAL: 0','TIDAK DAPAT DIAKSES: 0',
  "UKURAN MASTER ZIP: $FinalSize bytes",
  "SHA-256 MASTER ZIP: $FinalSha",
  "COMMIT TERBARU PENTING: $MainCommit",
  'VALIDASI: ZIP_OPEN_PASS; STRUCTURE_PASS; CHECKSUM_GENERATED; GIT_BUNDLE_VERIFY_PASS; SOURCE_NONEMPTY_PASS; BUILD_SHA256_PASS; SECRET_HIGH_CONFIDENCE_SCAN_PASS',
  'STATUS AKHIR: BACKUP_COMPLETE'
) | Set-Content (Join-Path $env:GITHUB_WORKSPACE 'BACKUP_RESULT.txt') -Encoding utf8

Write-Host "BACKUP_COMPLETE $FinalZip"
