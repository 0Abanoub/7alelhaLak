---
name: Team editing boundaries
description: Collaboration scope while teammate-owned validation is unfinished.
---

Do not modify, replace, rename, or duplicate data_loader.py or any files the
teammate is actively editing. Do not implement another validation or cleaning
pipeline. Do not assume the teammate's final interface.

**Why:** The user stated that a teammate is implementing validation and cleaning
and has not pushed the work to main.

**How to apply:** Keep analytics work independent, document the cleaned
DataFrame input contract, and inspect the actual teammate implementation before
integrating it. The user also instructed: do not change branches, commit, push,
merge, reset, or discard changes.
