# ZIP content policy

The downloadable progress ZIP contains the complete active project worktree, including source, specifications, requirements ledgers, generated contracts, migrations, tests, infrastructure, documentation, and retained build evidence.

Only non-project or regenerable transient material is excluded:

- `.git/` worktree internals;
- Python bytecode and pytest caches;
- JavaScript dependency/cache directories such as `node_modules/` and `.next/`;
- temporary test-matrix locks/staging directories;
- operating-system metadata files.

Git branch, base commit, current status, and the complete binary patch from the base commit are retained in the checkpoint report directory.
