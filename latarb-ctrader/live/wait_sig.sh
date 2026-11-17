#!/bin/bash
# exit when signals.jsonl has more than $1 lines, or after $2 seconds
cd "$(dirname "$0")"; end=$(( $(date +%s) + $2 ))
until [ "$(wc -l < signals.jsonl 2>/dev/null || echo 0)" -gt "$1" ] || [ "$(date +%s)" -ge "$end" ]; do sleep 0.2; done
tail -n +$(( $1 + 1 )) signals.jsonl; date +%s%3N
