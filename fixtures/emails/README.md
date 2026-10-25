Local-only folder for real newsletters saved as `.eml`, used by `scripts/seed_emulator.py` and for manual checks.

**Everything here except this README and `.gitkeep` is gitignored on purpose**: real mails contain
subscriber-specific tracking links (and your address), so they must never be committed or pushed.
Tests use only synthetic fixtures built in `functions/tests/`.

The document ID in the emulator is the file name without extension.
