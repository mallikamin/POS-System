# Pause Checkpoint — 2026-03-25

## Project
- **Name**: POS System (Sitara Infotech)
- **Path**: C:\Users\Malik\desktop\POS-Project
- **Branch**: main
- **Server**: 159.65.158.26 (pos-demo.duckdns.org)

## Goal
Complete QB Desktop Week 3 (testing, docs, admin UI, deployment) and set up professional CI/CD pipeline via GitHub Actions for automated deployments.

## Completed
- [x] QB Desktop Week 3: Admin UI page (QBDesktopPage.tsx — 450+ lines)
- [x] QB Desktop Week 3: Backend API endpoints verified (connect, QWC download, status, sync)
- [x] Frontend route `/admin/qb-desktop` added to App.tsx + AdminLayout nav
- [x] Fixed TypeScript errors (unused Badge import, Select component API, useToast path)
- [x] GitHub Actions CI/CD pipeline created (.github/workflows/deploy-production.yml)
- [x] SSH key generated on Windows, added to server + GitHub Secrets (SSH_PRIVATE_KEY)
- [x] Fixed CI/CD workflow (removed destructive `rsync --delete`, added `Dockerfile.prebuilt`)
- [x] Restored server after rsync --delete wiped files (git clone + .env.demo restore)
- [x] Deployed pre-built frontend to production using Dockerfile.prebuilt approach
- [x] **QB Desktop page CONFIRMED WORKING** at https://pos-demo.duckdns.org/admin/qb-desktop
- [x] Backend healthy, all 4 Docker services running
- [x] Fixed backend restart loop (password auth error — recreated container with fresh env)

## In Progress
- [ ] GitHub Actions CI/CD just pushed fix (commit 6fe24e8) — workflow running, needs verification that FUTURE automated deploys work correctly
- [ ] QB Desktop end-to-end testing (create connection → download QWC → QBWC client test)

## Pending
- [ ] Verify next GitHub Actions auto-deploy works end-to-end (the fixed workflow)
- [ ] QB Desktop: Create a test Desktop connection via the UI
- [ ] QB Desktop: Download QWC file and verify it's valid XML
- [ ] QB Desktop Week 4-6: Kitchen BOM + Inventory Assembly sync
- [ ] Account mapping with Younis team (QB Online)
- [ ] Tuesday demo preparation
- [ ] Enhancement backlog items (ENH-001 to ENH-016)

## Key Decisions
- **GitHub Actions over server upgrade**: Chose free CI/CD ($0/mo) over $32/mo 4GB droplet
- **Dockerfile.prebuilt approach**: Frontend built on GitHub's 7GB runner, lightweight nginx-only Dockerfile on server (no npm build needed on 2GB server)
- **git pull + rsync dist only**: Workflow does `git pull` for code sync + rsync ONLY the built frontend dist (no `--delete` that wipes server files)
- **Single connection per tenant**: QB Desktop follows same pattern as QB Online (not multi-connection CRUD)
- **Native HTML select**: Frontend uses native `<select>` component, not Radix UI SelectContent/SelectItem

## Files Modified This Session
- `frontend/src/pages/admin/QBDesktopPage.tsx` — Rewrote to match backend API (uses /status, /desktop/connect, /desktop/qwc, /sync/jobs, /sync/stats)
- `frontend/src/App.tsx` — Added lazy import + route for QBDesktopPage
- `frontend/src/components/layout/AdminLayout.tsx` — Added "QB Desktop" nav link
- `frontend/Dockerfile.prebuilt` — NEW: lightweight nginx Dockerfile for CI/CD (no npm build)
- `.github/workflows/deploy-production.yml` — NEW: GitHub Actions CI/CD workflow
- `.github/DEPLOYMENT_SETUP.md` — NEW: CI/CD setup documentation

## Git Commits This Session
1. `86e3f3b` — Add QB Desktop frontend UI + wiring (Week 3 40%→60%)
2. `374f9ea` — Fix QB Desktop page UI component imports
3. `f2d7ced` — Add GitHub Actions CI/CD deployment workflow
4. `3433da7` — Fix: Remove unused Badge import
5. `6fe24e8` — Fix CI/CD: use git pull + prebuilt Dockerfile (no rsync --delete)

## Uncommitted Changes
- `.claude/settings.local.json` — minor settings change
- `.env.example` — added QB env vars
- `docs/QB_ONLINE_ACCOUNT_MAPPING_REVIEW.html` — untracked doc
- `docs/QB_ONLINE_ACCOUNT_MAPPING_REVIEW.md` — untracked doc
- `docs/QB_ONLINE_TROUBLESHOOTING.md` — untracked doc

## Errors & Resolutions
1. **Backend restart loop (password auth failed for user "posapp")** → Recreated backend container with `up -d --no-deps --force-recreate backend` to pick up correct .env.demo
2. **Server resource exhaustion (load 47.97, 29MB RAM free)** → Killed stuck tsc process, chose GitHub Actions over server upgrade
3. **TypeScript: unused Badge import** → Removed import, pushed fix
4. **TypeScript: missing Table/Select/useToast** → Rewrote page to use available components (native select, div-based list, use-toast hook)
5. **rsync --delete wiped server files** → Restored via git clone + .env.demo backup; fixed workflow to only rsync dist/
6. **.dockerignore blocks dist folder** → Workflow removes `dist` from .dockerignore before build, restores after
7. **Container read_only: true** → Can't docker cp; must rebuild image with Dockerfile.prebuilt

## Critical Context
- **Server restored from git**: After rsync --delete incident, server was git cloned fresh. .env.demo was preserved from backup.
- **SSH key**: Windows key at `~/.ssh/id_rsa`, added to server's authorized_keys AND GitHub Secrets (SSH_PRIVATE_KEY)
- **GitHub Actions workflow**: Latest push (6fe24e8) triggers auto-deploy — needs verification that the FIXED workflow succeeds
- **Dockerfile.prebuilt**: Must exist on server at `frontend/Dockerfile.prebuilt` — git pull in workflow handles this
- **.dockerignore hack**: Workflow temporarily removes `dist` line from .dockerignore, rebuilds, then restores it
- **QB Desktop page CONFIRMED WORKING**: User verified at /admin/qb-desktop
- **QB Online Production keys**: Already deployed (earlier session), Younis company visible in OAuth popup
- **Server IP**: 159.65.158.26 (SGP1 DigitalOcean, 2GB RAM, 1 vCPU)
- **No swap configured** on server — builds must happen on GitHub Actions
