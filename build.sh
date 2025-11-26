#!/usr/bin/env bash
set -euo pipefail

# Simple arg parsing for build-time config
BASE_URL=""
USERNAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"; shift 2 ;;
    --username)
      USERNAME="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--base-url <url>] [--username <user>]"
      exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--base-url <url>] [--username <user>]" >&2
      exit 2 ;;
  esac
done

# Create a build-time config.json if any config is provided
CONFIG_CREATED=false
if [[ -n "${BASE_URL}" || -n "${USERNAME}" ]]; then
  CONFIG_CREATED=true
  {
    echo "{"
    [[ -n "${BASE_URL}" ]] && echo "  \"base_url\": \"${BASE_URL}\""
    [[ -n "${BASE_URL}" && -n "${USERNAME}" ]] && echo ","
    [[ -n "${USERNAME}" ]] && echo "  \"username\": \"${USERNAME}\""
    echo "}"
  } > config.json
fi

PYI_ARGS=(--onefile --name login-to-openshift)
if [[ "${CONFIG_CREATED}" == "true" ]]; then
  # Bundle config.json into the onefile binary
  PYI_ARGS+=(--add-data "config.json:.")
fi

pyinstaller "${PYI_ARGS[@]}" main.py

echo "\nBuild complete. Binary: dist/login-to-openshift"
if [[ "${CONFIG_CREATED}" == "true" ]]; then
  echo "Note: base URL and/or username were embedded at build time via config.json."
fi