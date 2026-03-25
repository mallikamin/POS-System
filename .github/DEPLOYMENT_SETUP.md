# GitHub Actions Deployment Setup

This document explains how to set up automated deployments to DigitalOcean using GitHub Actions.

## How It Works

1. **Push to `main` branch** → GitHub Actions triggers automatically
2. **GitHub runner** (7GB RAM) builds the frontend
3. **rsync** uploads built files to your DigitalOcean server
4. **SSH** commands rebuild and restart containers
5. **Health check** verifies deployment succeeded

## One-Time Setup (5 minutes)

### Step 1: Get Your SSH Private Key

On your local machine:

```bash
# Display your SSH private key
cat ~/.ssh/id_rsa
```

Copy the **entire output** (from `-----BEGIN` to `-----END`), including those lines.

**Alternative:** If you don't have an SSH key on the server yet:

```bash
# Generate a new deployment key
ssh-keygen -t rsa -b 4096 -C "github-actions-deploy" -f ~/.ssh/github_deploy
cat ~/.ssh/github_deploy

# Copy public key to server
ssh-copy-id -i ~/.ssh/github_deploy.pub root@159.65.158.26
```

### Step 2: Add SSH Key to GitHub Secrets

1. Go to your GitHub repository: https://github.com/mallikamin/POS-System
2. Click **Settings** (top menu)
3. In left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret** button
5. Name: `SSH_PRIVATE_KEY`
6. Value: Paste the entire SSH private key (from step 1)
7. Click **Add secret**

### Step 3: Test the Workflow

```bash
# Commit and push (workflow will trigger automatically)
git add .github/
git commit -m "Add GitHub Actions deployment workflow"
git push origin main
```

### Step 4: Monitor Deployment

1. Go to: https://github.com/mallikamin/POS-System/actions
2. Click on the running workflow
3. Watch the build progress in real-time
4. Deployment takes ~3-5 minutes

## What Gets Deployed

- ✅ **Frontend:** Built on GitHub (7GB RAM runner), deployed to nginx
- ✅ **Backend:** Code synced, containers recreated if needed
- ✅ **Docker configs:** Updated
- ⚠️ **Environment files:** NOT overwritten (`.env.demo` preserved on server)

## Automatic Deployment Triggers

The workflow runs automatically when:
- You push to `main` branch
- You merge a PR into `main`
- You manually trigger it from GitHub Actions UI

## Manual Deployment

You can also trigger deployments manually:

1. Go to: https://github.com/mallikamin/POS-System/actions
2. Click **Deploy to Production** workflow
3. Click **Run workflow** button
4. Select `main` branch
5. Click **Run workflow**

## Deployment Safety

✅ **Backup created:** Old frontend container backed up before deployment
✅ **Health check:** Deployment fails if API health check fails
✅ **Rollback:** If deployment fails, previous backup can be restored
✅ **No data loss:** Database and volumes are never touched
✅ **Zero downtime:** Containers recreated with `--no-deps` (no service interruption)

## Troubleshooting

### "Permission denied (publickey)" Error

**Solution:** SSH key not added correctly to GitHub secrets

1. Verify the key works locally:
   ```bash
   ssh -i ~/.ssh/id_rsa root@159.65.158.26 "echo OK"
   ```
2. Re-add the secret with the correct key

### "Frontend build failed"

**Solution:** Check the build logs in GitHub Actions

- Usually a TypeScript error
- Fix locally, commit, push again

### "rsync: command not found"

**Solution:** GitHub runners have rsync pre-installed, this shouldn't happen

### Deployment stuck on "Waiting for service"

**Solution:** Container failed to start

1. SSH to server manually
2. Check logs: `docker compose -f pos-system/docker-compose.demo.yml logs frontend`
3. Fix issue and redeploy

## Environment Variables

The workflow uses these environment variables:

```yaml
VITE_API_URL: https://pos-demo.duckdns.org/api/v1
VITE_WS_URL: wss://pos-demo.duckdns.org/ws
```

To change these, edit `.github/workflows/deploy-production.yml`

## Cost

**GitHub Actions Free Tier:**
- 2,000 minutes/month
- Average deployment: 3 minutes
- **You get: ~660 deployments/month** (more than enough!)

## Monitoring

After deployment, check:

1. **GitHub Actions:** https://github.com/mallikamin/POS-System/actions
2. **Production site:** https://pos-demo.duckdns.org
3. **API health:** https://pos-demo.duckdns.org/api/v1/health
4. **Server logs:** `ssh root@159.65.158.26 "cd pos-system && docker compose logs -f"`

## Next Steps After Setup

Once setup is complete, your workflow will be:

1. Make code changes locally
2. Commit and push to `main`
3. ☕ Relax while GitHub builds and deploys
4. 🎉 Changes live in ~3 minutes!

No more manual SSH, docker build, or resource constraints!
