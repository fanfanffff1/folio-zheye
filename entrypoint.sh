#!/bin/sh
set -e
if [ -f data/cleaned-books.json ]; then
  python3 -m folio.seed
fi
exec python3 run.py
