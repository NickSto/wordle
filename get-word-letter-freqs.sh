#!/usr/bin/env bash
if [ "x$BASH" = x ] || [ ! "$BASH_VERSINFO" ] || [ "$BASH_VERSINFO" -lt 4 ]; then
  echo "Error: Must use bash version 4+." >&2
  exit 1
fi
set -ue
unset CDPATH

SCRIPT_DIR=$(dirname $(readlink -f "${BASH_SOURCE[0]}"))
DEFAULT_LETTER_FREQS="$SCRIPT_DIR/letter-freqs.tsv"
Usage="Usage: \$ $(basename "$0") [options] word
Find the frequency rank of each letter in a word, according to the calculated letter frequencies.
Options:
-f: The letter frequency file to use. Default: $DEFAULT_LETTER_FREQS"

function main {

  # Get arguments.
  letter_freqs="$DEFAULT_LETTER_FREQS"
  while getopts "f:h" opt; do
    case "$opt" in
      f) letter_freqs="$OPTARG";;
      [h?]) fail -E "$Usage";;
    esac
  done
  word="${@:$OPTIND:1}"

  if ! [[ "$word" ]]; then
    fail -E "$Usage"
  fi

  i=0
  echo "$word" | fold -w 1 | while read letter; do
    i=$((i+1))
    grep -v '^#' "$letter_freqs" | sort -rg -k $((i+2)) | cat -n \
      | awk -v "letter=$letter" '$2 == letter {printf("%s: %2d\n", letter, $1)}'
  done
}

function fail {
  opt="$1"
  if [[ "$opt" == '-E' ]]; then
    prefix=
    shift
  else
    prefix="Error: "
  fi
  echo "$prefix$@" >&2
  exit 1
}

main "$@"
