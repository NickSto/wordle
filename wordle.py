#!/usr/bin/env python3
import argparse
import logging
import pathlib
import string
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_WORDLIST = pathlib.Path(SCRIPT_DIR/'words.txt')
DEFAULT_FREQ_LIST = SCRIPT_DIR/'letter-freqs.tsv'
DESCRIPTION = """How much can a simple script help solve wordles?
This gives a list of the possible words that fit what you currently know based on your previous
guesses."""
EPILOG = 'Wordle: https://www.powerlanguage.co.uk/wordle/'


def make_argparser():
  parser = argparse.ArgumentParser(add_help=False, description=DESCRIPTION, epilog=EPILOG)
  options = parser.add_argument_group('Options')
  options.add_argument('fixed',
    help="The greens: letters with known locations. Give dots for unknowns. You can omit trailing "
      "dots (this argument doesn't have to be 5 characters long).")
  options.add_argument('present',
    help='The yellows: known letters without a known location. You still need to give location '
      "information, because we still know where they aren't. Because each position can have "
      "multiple letters, the format is a little more complicated. Basically, it's the same as for "
      "the greens, except you can give multiple letters at each position. And you need to separate "
      "letters in adjacent positions with a '/', unless there's a dot in-between. Example: "
      "'i/an.pac' means you've seen a yellow 'i' at position 1, 'a' and 'n' at position 2, and "
      "'p', 'a', and 'c' at position 4.")
  options.add_argument('absent',
    help="The grays: letters known to be absent. Order and position doesn't matter. Repeat letters "
      "are fine. It can also handle letters present in the 'fixed' argument (they're ignored). "
      "Also, dots are valid (mainly so you can give an empty set as '.').")
  options.add_argument('-w', '--word-list', type=argparse.FileType('r'),
    default=DEFAULT_WORDLIST.open(),
    help=f'Word list to use. Default: {str(DEFAULT_WORDLIST)}')
  options.add_argument('-f', '--letter-freqs', type=argparse.FileType('r'),
    default=DEFAULT_FREQ_LIST.open(),
    help='File containing the frequencies of letters in all --word-length words.')
  options.add_argument('-n', '--limit', type=int, default=15,
    help='Only print the top N candidates. Default: %(default)s')
  options.add_argument('-L', '--word-length', default=5)
  options.add_argument('-h', '--help', action='help',
    help='Print this argument help text and exit.')
  logs = parser.add_argument_group('Logging')
  logs.add_argument('-l', '--log', type=argparse.FileType('w'), default=sys.stderr,
    help='Print log messages to this file instead of to stderr. Warning: Will overwrite the file.')
  volume = logs.add_mutually_exclusive_group()
  volume.add_argument('-q', '--quiet', dest='volume', action='store_const', const=logging.CRITICAL,
    default=logging.WARNING)
  volume.add_argument('-v', '--verbose', dest='volume', action='store_const', const=logging.INFO)
  volume.add_argument('-D', '--debug', dest='volume', action='store_const', const=logging.DEBUG)
  return parser


def main(argv):

  parser = make_argparser()
  args = parser.parse_args(argv[1:])

  logging.basicConfig(stream=args.log, level=args.volume, format='%(message)s')

  if len(args.fixed) > args.word_length:
    fail(
      f'Error: fixed ({len(args.fixed)}) cannot be longer than --word-length ({args.word_length}).'
    )

  fixed = parse_fixed(args.fixed, args.word_length)
  try:
    present = parse_present(args.present, args.word_length)
  except IndexError:
    fail(f'Present characters longer than --word-length(?)')
  absent = set(args.absent.lower()) - set(fixed) - {'.',''}

  words = read_wordlist(args.word_list, args.word_length)
  logging.info(f'Read {len(words)} {args.word_length} letter words.')
  freqs = read_letter_freqs(args.letter_freqs)

  candidates = get_candidates(words, freqs, fixed, present, absent)
  logging.warning(f'{len(candidates)} possible words left.')
  print('\n'.join(candidates[:args.limit]))


def get_candidates(words, freqs, fixed, present, absent):
  candidates = []
  for word in words:
    if is_candidate(word, fixed, present, absent):
      candidates.append(word)
  candidates.sort(key=lambda word: score_word(word, freqs), reverse=True)
  return candidates


def parse_fixed(fixed_str, word_len):
  fixed = [''] * word_len
  for i, letter in enumerate(fixed_str.lower()):
    if letter == '.':
      continue
    fixed[i] = letter
  return fixed


def parse_present(present_str, word_len):
  # Test cases:
  #   input: 'i/an.pac'
  #   output: {'i': [1], 'a': [2, 4], 'n': [2], 'p': [4], 'c': [4]}
  #   input: '...t'
  #   output: {'t':[4]}
  places = [''] * word_len
  place = 1
  last_char = None
  for char in present_str.lower():
    debug_str = f'{char}: '
    if char in '/|-':
      place += 1
      debug_str += f'Incrementing place to {place}'
    elif char == '.':
      if last_char is None:
        pass
      elif last_char in '/|-':
        raise ValueError(
          f'Invalid present string ({present_str!r}): Cannot have a {last_char!r} adjacent to a .'
        )
      elif last_char in string.ascii_lowercase:
        # If the last character was a letter, increment it by an additional place.
        debug_str += f'Incrementing place to {place}, then '
        place += 1
      place += 1
      debug_str += f'Incrementing place to {place}'
    else:
      places[place-1] += char
      debug_str += f'Storing at place {place}'
    logging.debug(debug_str)
    last_char = char
  return places


def add_fixed(fixed, fixed_addition):
  new_fixed = fixed.copy()
  if len(fixed) != len(fixed_addition):
    raise ValueError(f'Fixed arrays have different lengths ({len(fixed)} != {len(fixed_addition)})')
  for i, letter in enumerate(fixed_addition):
    if letter:
      if fixed[i] and letter != fixed[i]:
        raise ValueError(f'Different fixed letters in same place ({i+1}): {letter} != {fixed[i]}')
      new_fixed[i] = letter
  return new_fixed


def add_present(present, present_addition):
  new_present = present.copy()
  if len(present) != len(present_addition):
    raise ValueError(
      f'Present arrays have different lengths ({len(present)} != {len(present_addition)})'
    )
  for i, new_letters in enumerate(present_addition):
    old_letters = present[i]
    new_present[i] = ''.join(set(new_letters) | set(old_letters))
  return new_present


def is_candidate(word, fixed, present, absent):
  # Exclude words without a "fixed" character in the right place.
  for i, letter in enumerate(fixed):
    if letter and word[i] != letter:
      logging.debug(f'{word}: Missing fixed letter {letter} at {i+1}')
      return False
  for place, letters in enumerate(present,1):
    # Exclude words without a "present" character.
    for letter in letters:
      if letter not in word:
        logging.debug(f'{word}: Missing present letter {letter}')
        return False
    # Exclude words with a "present" character in the place we know it isn't.
    if word[place-1] in letters:
      logging.debug(f'{word}: Has present letter {letter} at excluded position ({place})')
      return False
  # Exclude words with an "absent" character.
  for letter in absent:
    if letter in word:
      logging.debug(f'{word}: Has absent letter {letter}')
      return False
  return True


def score_word(word, freqs):
  score = 0
  seen = set()
  repeats = 0
  for letter in word:
    if letter in seen:
      repeats += 1
    seen.add(letter)
    score += freqs[letter]
  return score / (10**repeats)


def read_wordlist(word_file, wordlen=None):
  words = set()
  for line_raw in word_file:
    fields = line_raw.rstrip('\r\n').split()
    if not fields or fields[0].startswith('#'):
      continue
    word = fields[0].lower()
    if wordlen is not None and len(word) != wordlen:
      continue
    invalid = False
    for letter in word:
      if letter not in string.ascii_lowercase:
        invalid = True
    if invalid:
      continue
    words.add(word)
  return words


def read_letter_freqs(freqs_file):
  freqs = {}
  for line_raw in freqs_file:
    fields = line_raw.rstrip('\r\n').split()
    if len(fields) < 2 or fields[0].startswith('#'):
      continue
    letter = fields[0]
    count = int(fields[1])
    freqs[letter] = count
  return freqs


def fail(message):
  logging.critical(f'Error: {message}')
  if __name__ == '__main__':
    sys.exit(1)
  else:
    raise Exception(message)


if __name__ == '__main__':
  try:
    sys.exit(main(sys.argv))
  except BrokenPipeError:
    pass
