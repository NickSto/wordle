#!/usr/bin/env python3
import argparse
import logging
import string
import sys
import wordle

DESCRIPTION = """"""


def make_argparser():
  parser = argparse.ArgumentParser(add_help=False, description=DESCRIPTION)
  options = parser.add_argument_group('Options')
  options.add_argument('words', metavar='word-list.txt', type=argparse.FileType('r'))
  options.add_argument('-f', '--stats', type=argparse.FileType('r'),
    help='Weight by word commonality data.')
  options.add_argument('-s', '--sort', action='store_true',
    help='Sort output by letter frequency instead of alphabetically.')
  options.add_argument('-w', '--weight', type=float, default=1)
  options.add_argument('-h', '--help', action='help',
    help='Print this argument help text and exit.')
  logs = parser.add_argument_group('Logging')
  logs.add_argument('-L', '--log', type=argparse.FileType('w'), default=sys.stderr,
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
  stats = None
  if args.stats:
    stats = wordle.read_word_stats(args.stats)

  # Count up all letter occurrences in all words.
  freqs = {letter:[0] for letter in string.ascii_lowercase}
  for fields in wordle.read_tsv(args.words):
    word = fields[0].lower()
    for place, letter in enumerate(word,1):
      try:
        freqs[letter]
      except KeyError:
        fail(f'Invalid character {letter!r} in word {word!r}')
      letter_freqs = freqs[letter]
      if stats is None or word not in stats:
        weight = 1
      else:
        weight = stats[word]**2
      letter_freqs[0] += 1 * weight
      while len(letter_freqs) <= place:
        letter_freqs.append(0)
      letter_freqs[place] += 1 * weight

  # Pad out the counts to the full word lengths.
  max_word_len = 0
  for counts in freqs.values():
    max_word_len = max(max_word_len, len(counts))
  logging.info(f'Max word length: {max_word_len}')
  for counts in freqs.values():
    while len(counts) < max_word_len:
      counts.append(0)

  # Define the sorting key according to the desired sort.
  if args.sort:
    key_fxn = lambda item: -item[1][0]
  else:
    key_fxn = lambda item: item[0]

  # Print the results.
  print('# '+' '.join(argv))
  for letter, counts in sorted(freqs.items(), key=key_fxn):
    fields = [letter]
    for count in counts:
      weighted_count = round(count*args.weight)
      fields.append(weighted_count)
    print(*fields, sep='\t')


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
