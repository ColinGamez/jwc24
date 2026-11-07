# Shared publisher directory lock

News, HBNJ and catalog/artwork publishers share `directory_lock`. A persistent
`.publication.lock` file identifies each directory's lock; it is never removed
on release, so waiting publishers continue to address the same file.

The November 7 integrated run exposed a first-creation race on Windows. Two
writers could both see an empty lock file. After one writer locked byte zero,
the other could fail while flushing an initial marker byte, before entering
the contention/retry loop. The actual concurrent Rakuten test produced that
`PermissionError`. A new deterministic test reproduced the same failure by
holding byte zero of an empty file before starting a contender.

The lock no longer initializes or writes the file. Windows byte-range locking
works beyond EOF, as documented for [Microsoft CRT `_locking`](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/locking?view=msvc-170).
The existing retry, timeout and unlock behavior stays in force. Existing lock
files retain their bytes; empty lock files remain empty. POSIX uses its existing
whole-file `flock` path.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_publication_lock tests.test_rakuten tests.test_asset_publication tests.test_news_publication tests.test_hbnj_publication
```

The regression tests use actual OS locks and temporary directories. They check
a contended empty file, real child-process exclusion and subsequent acquisition,
exception release, bounded contention timeout, persistent file identity and
preservation of existing bytes. The empty-file test failed before the fix with
the same initialization-flush error. No test mocks successful lock acquisition.
These checks do not establish network-filesystem lock semantics or crash-safe
payload publication by themselves; those belong to each publisher's transaction
and recovery contract.
