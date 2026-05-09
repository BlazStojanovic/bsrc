#!/usr/bin/env bash
# Usage: transcribe.sh <audio-file>
#
# Pipes the input through ffmpeg → 16kHz/mono/PCM → whisper-cpp,
# emits the transcript text to stdout. Lossless on both ends so
# whisper-cpp gets exactly what it expects.
#
# Env:
#   WHISPER_MODEL  path to a ggml-*.bin model. Defaults to
#                  ~/.cache/whisper/ggml-base.en.bin (downloaded by
#                  knowledge-smith/install.sh on first install).
#
# Deps: ffmpeg, whisper-cpp (both via `brew install`).

set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <audio-file>\n' "$(basename "$0")" >&2
  exit 2
fi

audio="$1"
if [[ ! -f "$audio" ]]; then
  printf 'transcribe.sh: not a file: %s\n' "$audio" >&2
  exit 2
fi

model="${WHISPER_MODEL:-$HOME/.cache/whisper/ggml-base.en.bin}"
if [[ ! -f "$model" ]]; then
  printf 'transcribe.sh: model not found at %s\n' "$model" >&2
  printf '  download a small model, e.g.:\n' >&2
  printf '    curl -L -o "%s" \\\n' "$model" >&2
  printf '      https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin\n' >&2
  exit 3
fi

for cmd in ffmpeg whisper-cpp; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf 'transcribe.sh: missing %s on PATH\n' "$cmd" >&2
    exit 4
  fi
done

tmpdir="$(mktemp -d -t ks-whisper.XXXXXX)"
trap 'rm -rf "$tmpdir"' EXIT

wav="$tmpdir/audio.wav"
ffmpeg -i "$audio" -ar 16000 -ac 1 -c:a pcm_s16le -loglevel error -y "$wav"

# whisper-cpp writes <output-file>.txt next to the prefix we give it.
out_prefix="$tmpdir/transcript"
whisper-cpp -m "$model" -f "$wav" --output-txt --output-file "$out_prefix" >/dev/null

cat "${out_prefix}.txt"
