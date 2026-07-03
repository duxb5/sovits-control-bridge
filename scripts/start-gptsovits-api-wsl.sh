#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$script_dir/.." && pwd)"

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate GPTSoVits

cd "$root/GPT-SoVITS"
exec python -X utf8 api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
