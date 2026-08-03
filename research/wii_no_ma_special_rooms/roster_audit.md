# Historical room-roster audit

Audit completed 2026-08-03.

## Result

- 48 room/campaign records are cataloged in `rooms.csv`.
- 29 have a confirmed historical identity plus substantive evidence.
- 5 have their existence confirmed but still lack useful mechanics/layout data.
- 14 have primary evidence for existence and some behavior, but remain marked
  partial because dates, layouts, content rotations, or authentic assets are
  incomplete.
- No entry now rests only on an unsupported retrospective list.

The 48-record total counts the 2010, 2011, and 2012 `福袋の間` campaigns as
three records because they had separate dates and prize sets. By unique room
name, the catalog contains 46 names.

## Coverage method

The roster is the union of:

1. Every room listed in the archived official January-October 2010
   `いろんな間` directory snapshots.
2. Every room listed in all distinct archived official redesigned `variety/`
   pages from November 2010 through shutdown in April 2012.
3. The four launch-week Company Room sponsors documented by contemporary
   hands-on reporting: Seven & i, Unilever, Honda, and AEON.
4. Rooms observed in a dated contemporary Wii/DS update log, including the
   pre-November-2009 Daiwa House room and the November launch cohort omitted
   from the first surviving official directory capture.
5. Official seasonal campaign announcements and Nintendo Online Magazine's
   detailed `みんなの間` / `プレゼントの間` coverage.

The archived official monthly Topics pages from November 2009 through January
2012 were also searched for room announcements. No additional launched room
name was found beyond the catalog after the two early omissions—Unilever and
Daiwa House—were added.

## Explicit exclusions

Contemporary reporting records trademark applications for `本の間`,
`絵本の間`, `まんがの間`, `音楽の間`, and `地方の間`. Only `音楽の間` has
evidence of launching. The other four remain concepts/trademarks, not rooms,
unless new service footage or server data proves otherwise.

`シアターの間`, `ホームシアター`, shopping storefronts, ordinary calendar
columns, and individual television programs are not counted as parade/special
rooms unless the service separately presented them as an `いろんな間` room.

## Meaning of “roster complete”

This is an evidence-complete working roster, not a claim that every byte has
survived. New footage or an original server dump could still expose a very
short-lived room hidden inside archive gaps. Authentic parade Mii binaries,
placard textures, entrance art, and complete menu data remain missing for most
rooms. JWC24 recreations must therefore keep provenance labels such as
`historical recreation` and must not call generated Miis or artwork original.

## Preserved archival package

The repository now locally preserves five Nintendo Online Magazine screenshots
for `みんなの間` and `プレゼントの間`, plus Nagatanien's original room press
release PDF. Hashes and capture provenance are recorded in `archive/README.md`.
These close the risk of losing the strongest known layout references, while
preserving the distinction between publication screenshots and original Wii
service binaries.
