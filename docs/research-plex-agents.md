# Research: Plex media agents — what they are, and do competing tools use them

*Researched 2026-11-21. For a V2 feature. No code written yet.*

## What a Plex "agent" is
An **agent** is Plex's metadata matcher. When Plex scans a folder, the agent decides *which*
movie/episode a file is and fetches its metadata. The modern default agents are **Plex Movie**
and **Plex TV Series**: Plex merges data from IMDb/TMDb/Rotten Tomatoes on its own servers and
gives each item a single consistent **Plex GUID** like `plex://movie/5d776ad8…`.

Older ("legacy") agents put the provider's own ID straight in the GUID instead:
- `com.plexapp.agents.imdb://tt1234567`
- `com.plexapp.agents.thetvdb://12345`
- `local://…` means Plex never matched the item (home video, or a failed match).

The agent is **internal Plex machinery**. It's not something an outside tool drives or needs to
replace; it just runs inside Plex when the library is scanned.

## What this means for us: we consume the agent's *output*, not the agent
We would never "use an agent" directly. What we'd use is the **IDs the agent already worked out**,
which Plex exposes on each item through its normal API. Since ~PMS 1.20.1, a single item's
metadata includes the external IDs as `Guid` entries:

```
<Guid id="imdb://tt1385826"/>
<Guid id="tmdb://38050"/>
<Guid id="tvdb://8856"/>
```

Reading those is just reading the user's own Plex server over its API — **no licence, no agent
integration, no metadata fetching by us.** (python-plexapi already surfaces them as `item.guids`.)

### Two practical catches to design around
1. **Per-item fetch.** The external `Guid`s reliably appear only when you request a *single*
   item (`/library/metadata/<ratingKey>`), not in the bulk `/library/sections/<id>/all` list. Plex
   later added an `includeGuids` option to include them in listings; we'd check which our target
   PMS versions support, and otherwise fetch per item (slower, more requests).
2. **Unmatched items have no IDs.** Anything the agent left as `local://` (home video, bad match)
   won't carry IMDb/TMDb/TVDB IDs. We'd fall back to title+year or to the folder's own files.

## Do the other "release 2" tools use agents?
Not the agents themselves — they **consume the agent's results**, the same way we would:
- Tools like Deduplarr, Cleanarr and plex_dupefinder read the Plex API and rely on Plex having
  already **matched multiple files to one item** (Plex shows that as "2 versions" of a movie).
  That merged grouping is literally a product of the agent's matching.
- They read the `guid` / `Guid` fields to identify items. None of them write or drive agents.

So the ecosystem's pattern is: **let Plex's agent do the matching, then read what it produced.**
That's the sane approach and the one we'd take.

## A differentiator worth noting
Plex's own idea of a "duplicate" is narrow: it's only when Plex matched two files to the **same**
item. If two copies sit in two folders Plex never merged (exactly the leftover-copy situation in
this user's library), Plex doesn't see them as duplicates at all. Our app finds those because we
look at the **folders and the manager's tracked file**, not only at what Plex already merged. So
reading Plex IDs is a *nice-to-have* for grouping, but our core value doesn't depend on Plex's
matching being perfect — which is a selling point over the Plex-API-only tools.

## Recommendation
- Treat Plex agents as out of scope to integrate; just **read the external `Guid`s** the agent
  produced, when Plex is connected, to strengthen duplicate grouping.
- Design for per-item fetch and for unmatched (`local://`) items.
- This needs **no licence** (reading the user's own server), unlike fetching from IMDb/TVDB/TMDb
  ourselves (see the IDs & metadata research doc).
