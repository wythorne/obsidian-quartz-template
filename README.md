# Wythorne Quartz Site

Deployed URL will be:

- `https://wythorne.github.io/obsidian-quartz-template`

This repo is configured to publish the Obsidian vault from:

- `/Users/radorrans/Downloads/Wythorne`

into Quartz content at:

- `source/content`

## What I changed

- imported the Wythorne vault into `source/content`
- generated a homepage for the site
- converted the vault's Dataview blocks into static markdown for Quartz publishing
- set Quartz `pageTitle` and `baseUrl` for this repo
- disabled template analytics
- added an export script so the site can be refreshed from the original vault later

## Refresh the site after the Obsidian vault changes

From the repo root:

```bash
python3 scripts/export_wythorne_vault.py
```

## Preview locally

```bash
cd source
npm install
npx quartz build --serve
```

Then open the local URL Quartz prints.

## Publish on GitHub Pages

1. Push this repository to the `main` branch on GitHub.
2. In the GitHub repo, open **Settings → Pages**.
3. Under **Build and deployment**, choose **GitHub Actions**.
4. In **Actions**, allow workflows if GitHub asks.
5. Push again or run the existing workflow manually.

The workflow in `.github/workflows/ci.yaml` will build Quartz and deploy the site automatically.

## Important note about Dataview

Quartz does not execute Obsidian Dataview queries in the browser the way Obsidian does. To make this vault publish cleanly, the export script replaces those Dataview blocks with static generated lists/tables at export time.
