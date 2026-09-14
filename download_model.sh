#!/bin/bash
BASE="https://hf-mirror.com/Qwen/Qwen2.5-7B-Instruct/resolve/main"
DIR="models/Qwen2.5-7B-Instruct"
mkdir -p "$DIR"
FILES="config.json generation_config.json tokenizer.json tokenizer_config.json vocab.json merges.txt model.safetensors.index.json model-00001-of-00004.safetensors model-00002-of-00004.safetensors model-00003-of-00004.safetensors model-00004-of-00004.safetensors"
for f in $FILES; do
  echo "=== $f ==="
  curl -sL -C - --retry 5 --retry-delay 10 -o "$DIR/$f" "$BASE/$f" || { echo "FAIL $f"; exit 1; }
  echo "done: $(ls -la "$DIR/$f" | awk '{print $5}') bytes"
done
echo "ALL DONE"
