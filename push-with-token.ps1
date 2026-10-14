# push-with-token.ps1 -- push to the user-pages repo using a Personal Access Token
#
# Why a token: the browser OAuth popup inherits whichever GitHub account is
# already signed in (that is how timeleaper128 kept getting used). A token does
# not depend on the browser session at all.
#
# Create the token while signed in as darkcoffin-wiki (use a private window):
#     https://github.com/settings/tokens  ->  Generate new token (classic)
#     scope: check the whole "repo" block
#
# Run (from E:\DSHwork\heijiu\wiki):
#     powershell -ExecutionPolicy Bypass -File .\push-with-token.ps1
#
# NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1 reads
# script files as ANSI/GBK unless they carry a UTF-8 BOM, which would mangle
# any Chinese text here.

$ErrorActionPreference = 'Stop'
$repo = 'darkcoffin-wiki/darkcoffin-wiki.github.io'
$user = 'darkcoffin-wiki'

Write-Host "==== push to $repo with a token ====" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path '.git')) {
    Write-Host "[ERROR] not a git repo. cd to the wiki folder first." -ForegroundColor Red
    exit 1
}
Write-Host "working dir: $((Get-Location).Path)"

Write-Host ""
Write-Host "Paste the token for account '$user' (starts with ghp_), then Enter." -ForegroundColor Yellow
Write-Host "Input is hidden and does NOT go into shell history." -ForegroundColor DarkGray
$sec = Read-Host -AsSecureString
$token = [System.Net.NetworkCredential]::new('', $sec).Password
if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Host "[ERROR] empty token, aborting." -ForegroundColor Red
    exit 1
}
if ($token -notmatch '^(ghp_|github_pat_)') {
    Write-Host "[WARN] this does not look like a GitHub token; trying anyway." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "storing credential for git:https://github.com ..." -ForegroundColor Cyan
cmdkey /generic:"LegacyGeneric:target=git:https://github.com" /user:$user /pass:$token | Out-Null

git remote remove origin 2>$null
git remote add origin "https://github.com/$repo.git"
Write-Host "remote = $(git remote get-url origin)"

git config user.name $user
git config user.email "604926574@qq.com"

Write-Host ""
Write-Host "pushing ..." -ForegroundColor Cyan
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'never'
git push -u origin main
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
    Write-Host "[OK] push succeeded." -ForegroundColor Green
    Write-Host "     site should appear at https://darkcoffin-wiki.github.io/ within 1-2 minutes"
    Write-Host "     next: add the DNS record and set the custom domain (see the publish guide)"
} else {
    Write-Host "[FAIL] push failed (exit code $code)" -ForegroundColor Red
    Write-Host "  * 403 denied to timeleaper128 -> the token belongs to the wrong account;"
    Write-Host "    generate a new one while signed in as darkcoffin-wiki."
    Write-Host "  * 404 not found -> repo does not exist yet: https://github.com/$repo"
    Write-Host "  * timeout / cannot connect -> proxy:"
    Write-Host "    git config --global http.proxy http://127.0.0.1:PORT"
    Write-Host "  * bad credentials -> rerun this script, or clear with:"
    Write-Host "    cmdkey /delete:LegacyGeneric:target=git:https://github.com"
}
