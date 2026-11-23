# Deploy the HackOn Systems website → hackonsystems.com

The website is the static files in `site/` (HTML/CSS/SVG). It's gitignored in this
code repo, so it gets its own **public** repo and is served by **GitHub Pages** at
your GoDaddy domain `hackonsystems.com`. Free GitHub Pages requires a *public* repo
— that's fine, a website is public anyway, and it holds no secrets.

## 1. Create a public repo for the site
github.com → **New repository**
- Owner: **Hackenon**  ·  Name: **hackonsystems**  ·  Visibility: **Public**
- Do **not** add a README, .gitignore, or license (keep it empty)
- Create repository

## 2. Put the site files in it (pick one)

**Easy — web upload (no git):**
1. On the new empty repo page, click **"uploading an existing file."**
2. In Explorer, open `C:\Claude\Projects\hackon-dedupe\site`, select **everything inside** it
   (`index.html`, `about.html`, `help.html`, `install.html`, `style.css`, `CNAME`,
   the `assets` folder) and **drag it onto the page.** Keep the `assets` folder and the
   `CNAME` file — both are required.
3. Commit directly to `main`.

**Git (if you prefer):**
```
# from a COPY of the site folder, outside this repo:
Copy-Item -Recurse C:\Claude\Projects\hackon-dedupe\site C:\Claude\Projects\hackonsystems-site
cd C:\Claude\Projects\hackonsystems-site
git init
git add .
git commit -m "HackOn Systems website"
git branch -M main
git remote add origin https://github.com/Hackenon/hackonsystems.git
git push -u origin main
```

## 3. Turn on GitHub Pages
Repo → **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: **main**, folder: **/ (root)** → **Save**

## 4. Confirm the custom domain
Still in **Settings → Pages → Custom domain**: it should already show
**hackonsystems.com** (the `CNAME` file sets it). If not, type it and Save.

## 5. Point GoDaddy DNS at GitHub  (the important part)
GoDaddy → **My Products → hackonsystems.com → DNS / Manage DNS**
- **Delete** GoDaddy's default parked **A record** on host `@` (and any "Forwarding").
- Add **four A records**, all with Host **`@`**:
  - `185.199.108.153`
  - `185.199.109.153`
  - `185.199.110.153`
  - `185.199.111.153`
- Add **one CNAME record**: Host **`www`** → Value **`hackenon.github.io`**
- (Optional IPv6 — four AAAA records on `@`: `2606:50c0:8000::153`,
  `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`)
- Save.

## 6. Wait, then force HTTPS
- DNS can take anywhere from ~10 minutes to 48 hours to propagate.
- When **Settings → Pages** shows the domain verified, tick **"Enforce HTTPS."**
- Visit **https://hackonsystems.com** — you should see the site.

## Notes
- If the page looks like raw markdown or assets 404, add an empty file named
  **`.nojekyll`** to the repo root (turns off Jekyll processing).
- **Re-deploying after edits:** run `python tools/build_site.py`, then re-upload /
  re-push the contents of `site/` to the `hackonsystems` repo.
- The site's GITHUB / DOWNLOAD links point at your code repo. When
  `hackon-dedupe` goes public, update `GITHUB`/`DOWNLOAD` in
  `tools/build_site.py` and rebuild.
