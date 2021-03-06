#!/usr/bin/env python3
import argparse
import logging
import pathlib
import string
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_WORDLIST = SCRIPT_DIR/'words.txt'
DEFAULT_FREQ_LIST = SCRIPT_DIR/'letter-freqs.all-answers.tsv'
DEFAULT_WORD_STATS = SCRIPT_DIR/'stats-ghent-plus.tsv'
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
    help='Word list to use. Default: '+str(DEFAULT_WORDLIST))
  options.add_argument('-f', '--letter-freqs', type=argparse.FileType('r'),
    default=DEFAULT_FREQ_LIST.open(),
    help='File containing the frequencies of letters in all --word-length words. Default: '
      +str(DEFAULT_FREQ_LIST))
  options.add_argument('-s', '--stats', type=argparse.FileType('r'),
    default=DEFAULT_WORD_STATS.open(),
    help='File containing statistics on words. This should be a tab-delimited file with at least '
      'two columns: the word, and the proportion of people who recognize it (a float from 0 to 1). '
      'Default: '+str(DEFAULT_WORD_STATS))
  options.add_argument('-n', '--limit', type=int, default=15,
    help='Only print the top N candidates. Default: %(default)s')
  options.add_argument('-L', '--word-length', default=5)
  options.add_argument('-g', '--guess-thres', type=float,
    help='Threshold score for when it should make a guess.')
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
  except WordleError as error:
    fail(error.message)
  absent = set(args.absent.lower()) - set(fixed) - {'.',''}

  words = read_wordlist(args.word_list, args.word_length)
  logging.info(f'Read {len(words)} {args.word_length} letter words.')
  freqs = read_letter_freqs(args.letter_freqs)
  stats = read_word_stats(args.stats)

  candidates = get_candidates(words, freqs, fixed, present, absent)
  logging.warning(f'{len(candidates)} possible words left.')
  result = get_answer_guess(candidates, stats, args.guess_thres)
  if result:
    guess, stat = result
    print(f'Guess: {guess} (score: {stat:0.2f})')
  new_candidates = get_new_candidates(candidates, words, freqs, fixed, present, absent)
  print('\n'.join(new_candidates[:args.limit]))


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
  #   output: ['i', 'an', '', 'pac', '']
  #   input: '...t'
  #   output: ['', '', '', 't', '']
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
        raise WordleError(
          f'Invalid present string ({present_str!r}): Cannot have a {last_char!r} adjacent to a .',
        )
      elif last_char in string.ascii_lowercase:
        # If the last character was a letter, increment it by an additional place.
        debug_str += f'Incrementing place to {place}, then '
        place += 1
      place += 1
      debug_str += f'Incrementing place to {place}'
    else:
      if place > len(places):
        raise WordleError(f'Present string longer than word length ({place} > {word_len})')
      else:
        places[place-1] += char
      debug_str += f'Storing at place {place}'
    logging.debug(debug_str)
    last_char = char
  return places


def add_fixed(fixed, fixed_addition):
  new_fixed = fixed.copy()
  if len(fixed) != len(fixed_addition):
    raise WordleError(
      f'Fixed arrays have different lengths ({len(fixed)} != {len(fixed_addition)})'
    )
  for i, letter in enumerate(fixed_addition):
    if letter:
      if fixed[i] and letter != fixed[i]:
        raise WordleError(f'Different fixed letters in same place ({i+1}): {letter} != {fixed[i]}')
      new_fixed[i] = letter
  return new_fixed


def add_present(present, present_addition):
  new_present = present.copy()
  if len(present) != len(present_addition):
    raise WordleError(
      f'Present arrays have different lengths ({len(present)} != {len(present_addition)})'
    )
  for i, new_letters in enumerate(present_addition):
    old_letters = present[i]
    new_present[i] = ''.join(set(new_letters) | set(old_letters))
  return new_present


def get_candidates(words, freqs, fixed, present, absent):
  candidates = []
  for word in words:
    if is_candidate(word, fixed, present, absent):
      candidates.append(word)
  candidates.sort(key=lambda word: score_letter_freqs(word, freqs), reverse=True)
  return candidates


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


def score_letter_freqs(word, freqs):
  score = 0
  seen = set()
  repeats = 0
  for place, letter in enumerate(word,1):
    if letter in seen:
      repeats += 1
    seen.add(letter)
    counts = freqs[letter]
    score += counts[place]
  return score / (10**repeats)


def score_guesses(candidates, word_stats):
  """Calculate a score for each guess based on the likelihood it's the correct answer.
  This weights each word by a statistic like the percent of people who know it.
  The algorithm takes the stat for each word and divides it by the sum of the stats for all the
  candidate words. This is a weighted version of the naive case where each word has equal
  probability: the score for each word would be 1/N. That should be the actual probability that
  each word is correct. Instead here it's stat/sum_stats."""
  stats = []
  raw_stats = [word_stats.get(word,0) for word in candidates]
  total = sum(raw_stats)
  if total == 0:
    return [0] * len(candidates)
  for raw_stat in raw_stats:
    stats.append(raw_stat/total)
  return stats


def get_answer_guess(candidates, stats, thres):
  guesses = get_answer_guesses(candidates, stats)
  if not guesses:
    return None
  word, stat = guesses[0]
  if thres is None or stat >= thres:
    return word, stat
  else:
    return None


def get_answer_guesses(candidates, stats):
  weighted_stats = score_guesses(candidates, stats)
  return sorted(zip(candidates, weighted_stats), key=lambda e: e[1], reverse=True)


def choose_words(words, freqs, stats, fixed, present, absent, guess_thres, limit=None):
  guesses = {'choice':None}
  candidates = get_candidates(words, freqs, fixed, present, absent)
  # Make our best guess at the actual answer.
  answer_guesses = get_answer_guesses(candidates, stats)
  guesses['answers'] = answer_guesses[:limit]
  if answer_guesses:
    answer_guess, stat = answer_guesses[0]
    if stat >= guess_thres:
      guesses['choice'] = answer_guess
  if not candidates:
    raise WordleError('No words found which fit the constraints!')
  # If we're not trying to solve, guess new letters instead of ones we already know are right.
  new_candidates = get_new_candidates(candidates, words, freqs, fixed, present, absent)
  guesses['excluders'] = new_candidates[:limit]
  if not guesses['choice']:
    if new_candidates:
      guesses['choice'] = new_candidates[0]
    else:
      guesses['choice'] = candidates[0]
  return guesses


def choose_word(words, freqs, stats, fixed, present, absent, guess_thres):
  results = choose_words(words, freqs, stats, fixed, present, absent, guess_thres)
  return results['choice']


def get_new_candidates(candidates, words, freqs, fixed, present, absent):
  new_absent = absent.copy() | set(''.join(fixed)) | set(''.join(present))
  new_fixed = new_present = ['']*len(fixed)
  if new_fixed == fixed == new_present == present:
    # Everything's empty. It's our first guess so the new candidates would be the same as the old.
    return candidates
  else:
    return get_candidates(words, freqs, new_fixed, new_present, new_absent)


def read_wordlist(word_file, wordlen=None):
  words = set()
  for fields in read_tsv(word_file, min_columns=1):
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


def read_word_stats(stats_file):
  stats = {}
  for fields in read_tsv(stats_file, 2):
    word = fields[0].lower()
    stat = float(fields[1])
    stats[word] = stat
  return stats


def read_letter_freqs(freqs_file):
  freqs = {}
  for fields in read_tsv(freqs_file, min_columns=2):
    letter = fields[0]
    counts = [int(field) for field in fields[1:]]
    freqs[letter] = counts
  return freqs


def read_tsv(tsv_file, min_columns=None):
  for line_raw in tsv_file:
    fields = line_raw.rstrip('\r\n').split('\t')
    if len(fields) > 0 and fields[0].startswith('#'):
      continue
    if min_columns is not None and len(fields) < min_columns:
      raise WordleError(f'Too few columns ({len(fields)} < {min_columns})')
    yield fields


class WordleError(Exception):
  def __init__(self, message, data=None):
    super().__init__(message)
    self.message = message
    if data is None:
      self.data = {}
    else:
      self.data = data


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
