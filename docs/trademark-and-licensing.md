# Trademark & licensing review — starting notes

*Started 2026-11-21. Engineering/business notes to brief a lawyer. **Not legal advice.***

## 1. Name clearance: "Photo & Video Dedupe"
**Finding: the name is safe to *use* but impossible to *own*, and the field is crowded.**
A search turns up many existing apps using almost the same descriptive name, e.g.:
- PhotoDeDupe, PicDeDupe, Dedup, Dedup2, PhotoDupFinder (iOS photo/video dup cleaners)
- "Sweeper Photo&Video Duplicates", "Duplicate Photo - Video Remover", "Storage Cleaner - Dedupify"
- Mylio Photos+ ships a feature literally called the "Photo DeDupe tool"

What this means:
- **Discoverability: good.** These are the exact words people search, so a descriptive name helps
  people find us.
- **Trademark protection: effectively none.** The phrase is generic/descriptive and already used by
  many; we could not register or enforce it, and neither can they. We can't stop copycats using it.
- **Confusion risk: low in our niche.** Those are phone storage-cleaner apps; we're a desktop
  library tool that works with Plex/Radarr/Sonarr. Different market, so real-world confusion is
  limited — but the name alone won't distinguish us.
- **"No Plex in the name" release rule: met.**

**Recommendation:** use "Photo & Video Dedupe" as the plain-English **descriptor/what-it-does**, and
if we want a brand we can protect and sell under, put a **distinctive mark** on top of it (the
earlier *Winnow* / *Cull* idea), e.g. *"Winnow — photo & video dedupe."* The distinctive word is the
trademark; the descriptive phrase is the tagline. A lawyer should run a proper clearance search on
whichever distinctive mark we choose (not on the descriptor).

### Candidate brand: "HackOn" (proposed 2026-11-21)
Structure would be **HackOn** (the trademark) + **Photo & Video DeDupe** (the descriptor):
*"HackOn — Photo & Video DeDupe."* This is the right shape — a coined, distinctive mark we can own,
sitting on top of the plain descriptor. It also continues the app's existing boot branding
("HACKENON SYSTEMS"); we'd tighten that to "HACKON SYSTEMS" for consistency.

**Preliminary checks (not a legal clearance):**
- **No exact "HackOn" software trademark** turned up. Nearby registered marks exist in the software/
  security space — HackerOne, HackNotice, HackerNoon, Hacky (HACKY, downloadable software), HackRod —
  so the "Hack*" field is crowded and a registration could draw a confusion objection. A proper
  USPTO + common-law clearance by a lawyer is important here.
- **Domain:** `hackon.tech` is already registered/used by someone else, so the obvious domain may be
  taken. Plan on an alternative TLD (e.g. hackon.app, gethackon.com) — confirm availability.
- **Optics / "Hack" branding risk (honest caution):** the product has features literally named
  "backdoor," "grab key" and "probe local network," and it handles API keys and scans the LAN.
  Wrapping that in a "Hack" brand leans hard into the hacker aesthetic (which is the whole
  personality and fun) but, for a **paid/mainstream** audience, it could (a) read as sketchy, (b)
  raise antivirus/reputation flags, and (c) complicate app-store review. Fine for the enthusiast/
  self-hoster crowd; worth a conscious decision if we target mainstream buyers.
- **Keep "Video" in the descriptor:** the proposal dropped it ("Photo & DeDupe"). Since the app does
  photos *and* video, use **"Photo & Video DeDupe"** for accuracy, or go shorter as **"HackOn DeDupe"**
  (brand + action) and let the brand carry the rest.

**Verdict:** HackOn is a good, ownable brand and a strong fit for the theme — proceed to a proper
clearance search on "HackOn" before committing, secure a domain, and decide consciously whether the
"Hack" framing suits the market you want to sell to.


## 2. Our dependencies — all permissive, all fine for commercial/closed use
Every runtime dependency uses a permissive licence that allows commercial and closed-source
redistribution, provided we include their licence/copyright notices in the distribution.

| Package | Licence | Commercial/closed OK? |
|---|---|---|
| Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click | BSD-3-Clause | Yes (keep notices) |
| blinker | MIT | Yes |
| Pillow | HPND / MIT-CMU | Yes |
| ImageHash | BSD-2-Clause | Yes |
| NumPy, SciPy | BSD-3-Clause | Yes |
| PyWavelets | MIT | Yes |
| keyring | MIT | Yes |

**To do before release:** bundle a `THIRD-PARTY-LICENSES` file with each of these licence texts.
(Avoid GPL libraries like Cinemagoer/IMDbPY — see the IDs & metadata doc.)

## 3. FFmpeg / ffprobe — the one that needs a decision
We use **ffprobe** to read video resolution/codec/length. FFmpeg is **LGPL-2.1+**, or **GPL** if a
build includes GPL components (e.g. x264). This is the only copyleft piece in play.

- We call ffprobe as a **separate executable** via `subprocess` — we don't link its code into ours.
  Calling a separate program at arm's length generally does **not** make our app a derivative work,
  even of a GPL build. So *using* an ffprobe the user installed is clean.
- The question is only about **bundling/distributing** FFmpeg with our installer. Options:
  1. **Don't bundle** — have the user install FFmpeg (we already support `winget install Gyan.FFmpeg`
     and detect it). Cleanest; zero copyleft exposure. *(Current behaviour.)*
  2. **Bundle an LGPL build** and include FFmpeg's licence + source offer / notices. More convenient
     for users; needs the notice work and an LGPL (not GPL) build.
- **Recommendation:** ship without bundling for v1 (as today); if we later bundle for convenience,
  use an LGPL build and add the notices. Lawyer to confirm the bundling choice.

## 4. Our own licence choice (for the code we release)
- **MIT / BSD (permissive):** anyone can use, including in closed/commercial forks. Maximises
  adoption; others *could* sell their own build.
- **GPL-3.0 / AGPL-3.0 (copyleft):** forks must stay open; prevents closed resale by others. AGPL
  also covers hosted/SaaS use.
- We can **sell our own builds under either**, and could **dual-license** (open under GPL, sell a
  commercial licence) if we want both.
- **Recommendation to discuss:** GPL-3.0 if the priority is "stays open, no closed clones"; MIT if
  the priority is maximum adoption. Decide before the first public commit (it's hard to change later
  once others contribute).

## 5. Logo / asset ownership
- The draft logo (`assets/logo.svg`) is our own artwork — fine to use and modify.
- **Font caveat:** it references `Courier New`, which is a proprietary Microsoft font. For a
  distributed/rasterised logo, either convert the text to vector paths or switch to an open
  monospace (OFL, e.g. a free DOS/terminal font) so no font licence rides along.

## 6. Open items for the lawyer
1. Trademark clearance on the **distinctive brand** we choose (USPTO + common-law search); the
   descriptor "photo & video dedupe" needs none but gives no protection.
2. Final **code licence** choice (section 4), and whether to dual-license.
3. **FFmpeg bundling** decision and notices (section 3).
4. If we use **TMDb** (folder-mode lookups), confirm their commercial terms in writing and add the
   required logo + "not endorsed or certified by TMDB" notice (see IDs & metadata doc).
5. A short **privacy/data statement**: the app reads the user's library, stores API keys/tokens
   (in the OS keychain), and bug reports are user-submitted with secrets redacted — worth stating
   plainly for a paid product.
6. Confirm we ship a `THIRD-PARTY-LICENSES` file (section 2).
