# Native item, variant and basket-identity bridge

October 26, 2026. The item-list consumer and its actual owned model now execute
in one offline check, extending the earlier category-model and isolated size
setter work. This is **not native item rendering or a completed basket flow**.
The [metadata report](../../research/demae_item_model_flow_20261026.json) records
the exact scope, source relationship, synthetic cases and current data blockers.

## Source and execution boundary

The new checker uses the unpatched private HCHJ v512 application, SHA-256
`6b9002431aec265e34ba532aae2707ef74a5b8c491f81be624a54563eabc88c9`.
Its bytes match decompression of the retained original content index1. Selected
model, item-consumer, stock, parser and basket-matching regions are byte-equal
to the older host-patched fixture, whose different whole-file hash is recorded
separately. No original executable bytes or derived disassembly are published.

`tools.verify_demae_item_model_flow` executes:

1. Item consumer `0x8004F45C`, its real record constructors, setters and native
   numeric price-display formatter `0x80022D3C`.
2. Variant attachment `0x80027358`, actual size-record copying, item insertion
   `0x80026060`, actual item copying and original temporary-record cleanup.
3. Indexed variant selection `0x8002757C` and item-code getter `0x80029774`.
4. The stock predicate at `0x8005712C..0x80057180`, using the real stock getter
   `0x80029A7C` and original string comparison.
5. Basket-code matching slice `0x800B2428..0x800B24A0`, after the parent item has
   already been chosen, using basket-line code getter `0x80012EC4`.

XML lookup, tree storage, payload wrappers, shared status validation, allocation,
codecs and selected libc remain explicit synthetic adapters. The native XML
lexer is **not** executed by this combined checker. Separate earlier parser
checks do not turn these mocks into a complete wire-to-UI proof. In particular,
the empty-node test assumes a payload wrapper; its result is control-flow
evidence, not proof of how a real empty element is represented.

Heap operations are mocked, including distinct owned storage for zero-size
image-buffer copy allocations. That policy does not establish the real heap's
zero-size behavior. Image fetch/decode/display, actual allocation cleanup and
whole-channel recovery remain separate checks. Original settings, address/save
data, source files and profiles are neither read nor changed by the checker.

## Concrete results

Two synthetic variants retain their independently supplied codes, labels,
prices and raw stock values through the consumer and deep-copy model. Native
formatting converts the supplied numeric prices into `1,280円` and `1,980円`.
Explicit supplied zero prices are also accepted and become `0円`; they are not
replaced with an invented positive amount or treated as proof of availability.
Overwriting every mocked XML text buffer after consumption leaves the owned
item/variant fields unchanged. Native indexed selection returns the expected
variant and its code.

The raw stock predicate sets its flag only for exact text `1`; `0`, `01`,
`true` and `unknown` do not set it. A false predicate is **not proof of provider
availability**. Missing/unknown source stock cannot be converted into available
food. The raw stock getter is `0x80029A7C`; nearby `0x800299C0` reads a different
wide-text field and must not be used to infer raw stock meanings.

With the mocked empty payload wrapper, the consumer's initial stock text `1`
is retained when no nonempty replacement is supplied. The conservative candidate
gate below rejects empty/unknown stock instead of depending on that wrapper
assumption.

The original basket matching slice selects the second variant when its exact
code is supplied, selects the first for that code, and leaves the selection
unchanged for an absent code. Duplicate variant codes select the **first match**,
making ambiguous identities unsuitable for publication. This slice does not
parse a basket response, establish the earlier parent-name matching, calculate
fees/totals, submit a basket or demonstrate any checkout transition.

Missing item-code/price/stock fields and a size list with zero attached rows
reject the tested item. A missing **later** price terminates the size loop while
earlier rows can still be inserted; accepting the consumer's return value alone
would silently lose intended variants. Injected variant-node or item-node
allocation failures reject insertion. Failure on the second item retains the
first owned item; no transactional rollback or leak-free recovery is claimed.

## Conservative candidate gate

`jwc24.demae_native_items.inspect_native_item_candidate` provides an independent
structural gate for a future action-10 publisher. It requires selected-menu
consistency, Count/container names and order, nonempty required fields, CDATA,
explicit closing tags, complete nonempty variant rows, canonical listed yen
amounts and explicit `0`/`1` stock. It rejects duplicate parent/per-item variant
identities and malformed rows that the native consumer could partially accept.

These stricter field/count/price/text rules are **local producer safeguards**,
not a claim that all are native protocol limits. The gate checks no provider
source, image role, freshness, delivery eligibility or stock observation. Its
result always leaves provider evidence, current orderability and rendering
unverified. Passing it is insufficient to publish a restaurant menu.

## Real-data and integration gate

The retained observation files currently contain **248 parent item observations
from 38 branches**. At this audit time all 38 observations fail the existing
24-hour freshness check. None contains provider item IDs or variant rows, and
all generic `options_observed` values are false. No timestamp or original source
record was changed by this audit.

Those records contain only name/category/listed parent price plus the generic
option flag. They cannot supply actual variant identities, labels, individual
prices or observed stock. Local routing IDs may be explicitly distinguished
from provider SKUs, but neither a technical ID nor `options_observed` invents
the missing variant facts. In particular, do not copy a parent's base price to
unobserved sizes or invent a standard-size row merely to pass the positive-count
gate.

The next live integration requires independently verified current branch and
variant evidence, preservation of the selected category/menu mapping, reviewed
item-image handling and the remaining native shop/item/basket controllers.
Action16's complete basket response remains unfinished. Existing local basket
plans still do not transfer a provider basket or establish checkout charges.
The phone handoff belongs after the real selection/basket flow; this batch does
not replace that flow with a QR screen.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_demae_item_model_flow tests.test_demae_native_items
```

Seventeen focused tests pass. Every fixture is synthetic and remains offline.
No source menu was refreshed, item route enabled, order submitted, notice
queued, profile changed or Dolphin instance launched.
