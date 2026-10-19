# Persistent Demae archive

The shared private archive is private/demae/demae.sqlite. It currently retains
9400 restaurant identities across47 prefectures,9400 source versions, three
branch reviews and three partial menu observations. It stores public source
restaurant data; Wii home addresses and provider API credentials are not
imported. Image bytes remain in the existing validated private image caches.

tools/build_demae_database.py merges local source snapshots transactionally.
Restaurant IDs are stable. A source response omitting a restaurant never
deletes it or marks it closed. Changed source JSON adds a historical version;
identical imports are deduplicated. Evidence is archived even after expiry,
but menu use still requires current branch and menu validation. Older evidence
imported later cannot replace a newer observation in the menu directory.

Each successful import creates a new timestamped SQLite backup under
private/demae/backups/ using SQLite's backup API and checks its integrity.
Existing backups are never overwritten. These local backups protect against
refresh mistakes; they are not an off-device disaster recovery system.

The directory launcher refreshes the archive when local catalogs are present
and serves --directory-database with complete directory lists. The menu
coverage and phone-plan verification tools also prefer the archive. Original
JSON files remain import evidence rather than the only copy of restaurant
records. The database-backed nationwide HTTP check passes all9400 identities,
652 municipalities and1257 category lists across47 prefectures.

Permanent closure is a separate reviewed action: record_permanent_closure
requires an evidence HTTPS URL, review reason and timezone-aware timestamp.
A confirmed closed restaurant is hidden from active directory output but its
record/history remain archived. An old source listing cannot reopen it.
Temporary closure, provider outage or missing search result is insufficient.

follow_restaurant explicitly subscribes a Wii to that restaurant's future
closure notice. A reviewed closure freezes one notice per follower in the
durable closure outbox; repeat reviews do not create duplicates. The phone
service retries this outbox through the existing shared mail queue, retaining
failed deliveries for retry. There is no follow button integrated in the Wii
UI yet, and no automatic closure detector or mass audience subscription.

No real subscriptions, closures or notices were created while implementing
this feature. Tests exercise closure mail only with temporary databases and
test mail stores. Current live archive closure/event counts are zero.
