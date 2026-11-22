# Research: external IDs & metadata (IMDb / TheTVDB / TMDb)

*Researched 2026-11-21. For a V2 feature. No code written yet.*

## Why we'd want this
To group different folders/files that are really the same title — e.g. "Dune (2021)"
and "Dune Part One (2021)" — by a shared external ID (IMDb `tt…`, TMDb number, TheTVDB
number) instead of by name. This is what Duplicatearr does. It makes duplicate grouping
much more reliable than title+year matching.

## The key finding: we probably don't need an external licence at all
The external IDs we want are **already handed to us by the apps the user connects**, so for
most users we never call IMDb/TVDB/TMDb directly and never touch their licences.

- **Radarr** — each movie record includes `imdbId` (e.g. `tt1160419`) and `tmdbId` (a number).
- **Sonarr** — each series record includes `tvdbId`, `imdbId`, and also `tvMazeId` / `tvRageId`.
- **Plex** — each item carries a `guid` (and `Guid` children) that embed the matched IDs from
  whatever agent matched it (IMDb/TMDb/TVDB). Reading your own server's data has no licence cost.

So the plan is: **read the IDs from the connected manager/server.** That is just reading the
user's own Radarr/Sonarr/Plex over its API — no third-party licence, no API key beyond the ones
the user already enters, no attribution burden. This covers every user who has one of those
connected, which is our main audience.

The only gap is **pure folder mode** (no Radarr/Sonarr/Plex at all). There we'd have to look a
title up ourselves, and that's the only place an external service comes in.

## If we ever do need an external lookup (folder-only mode)
Ranked by how usable they are for a product we might **sell**:

### 1. TMDb (The Movie Database) — the practical choice
- Free with **attribution**: the TMDb logo plus the exact notice "This product uses the TMDB API
  but is not endorsed or certified by TMDB," shown in an About/Credits section, with the TMDb
  logo less prominent than ours.
- Free tier is for **non-commercial** use; **commercial use needs their approval / a separate
  agreement**, but there's no paywall to simply start, and TMDb is the de-facto standard (Radarr
  and the Plex Movie agent both use TMDb).
- Each user (or we) registers a free API key. Cleanest path: **user supplies their own TMDb key**
  in Setup, so we're a tool that uses their key, and we carry the attribution.
- **Action if we use it:** confirm commercial terms with TMDb in writing before selling; add the
  logo + notice to an About screen.

### 2. TheTVDB v4 — workable but it costs
- Licensed two ways: a **negotiated commercial licence** (free under ~$50k revenue *with
  attribution*, then ~$1,000/yr for $50k–$250k, ~$10,000/yr for $250k–$1M, custom above), **or** a
  **user-supported** model where **each end user pays ~$12/yr** for a TheTVDB subscription and
  enters a PIN alongside our project key.
- Attribution with a link back to TheTVDB is required.
- **Takeaway:** only worth it if we specifically need TheTVDB's TV data in folder mode. For a free
  release, the revenue tier is free-with-attribution; if we sell and grow, it becomes a real cost
  or a per-user subscription requirement.

### 3. IMDb — avoid for direct use
- IMDb data is licensed **for personal, non-commercial use only**. Altering, republishing,
  reselling or building a database from it is prohibited, and scraping is prohibited.
- There's **no free public API**; commercial access is a paid enterprise licence via AWS Data
  Exchange.
- Helper libraries that wrap IMDb datasets (e.g. Cinemagoer) are **GPL-2.0** and still ride on
  IMDb's non-commercial dataset terms — a double problem for a closed, sellable product.
- **Takeaway:** **do not fetch from IMDb or bundle IMDb datasets.** It's fine to *display or match
  on an IMDb ID string that Radarr/Sonarr/Plex already gave us* (an ID is not their dataset), but
  we should not pull data from IMDb ourselves.

## Recommendation
1. **Phase 1 (no licence needed):** read `imdbId` / `tmdbId` / `tvdbId` from the connected
   Radarr/Sonarr, and the matched GUIDs from Plex, and use them to group duplicates. This is the
   high-value, zero-licence step and covers most users.
2. **Phase 2 (optional):** for folder-only users, add a **TMDb** lookup behind the user's own TMDb
   API key, with the required logo + "not endorsed or certified by TMDB" notice in an About
   screen. Verify commercial terms with TMDb before selling.
3. **Never** integrate IMDb or bundle its datasets; **avoid** TheTVDB direct unless we decide its
   TV data is worth the per-user subscription or the revenue-tier fee.
4. All of the above is subject to the trademark-and-licensing review (separate doc); these are
   engineering notes, not legal advice.

## Open questions to settle before building
- Exactly which Plex `Guid` shapes appear for Movie vs TV vs the different agents, so grouping is
  reliable (needs checking against a live Plex server).
- Whether we group only when IDs match, or fall back to title+year when an item has no ID.
- Whether to store the IDs in our results files so a rescan is faster.
