#!/bin/bash
for f in /root/dsc-extract/*.dylib; do
  n=$(basename "$f")
  hits=$(strings -a "$f" | grep -icE "folders|DARWIN_USER|user_dir|/var/folders|/var/mobile")
  [ "$hits" -gt 0 ] && echo "=== $n ($hits) ===" && strings -a "$f" | grep -iE "folders|DARWIN_USER|user_dir|/var/folders|/var/mobile" | head -8
done
echo "DONE"
