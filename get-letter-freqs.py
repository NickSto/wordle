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
  options.add_argument('-s', '--sort', action='store_true',
    help='Sort output by letter frequency instead of alphabetically.')
  options.add_argument('-l', '--word-length', type=int)
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

  freqs = {letter:[0] for letter in string.ascii_lowercase}
  for fields in wordle.read_tsv(args.words):
    word = fields[0].lower()
    for place, letter in enumerate(word,1):
      try:
        freqs[letter]
      except KeyError:
        fail(f'Invalid character {letter!r}')
      letter_freqs = freqs[letter]
      letter_freqs[0] += 1
      while len(letter_freqs) <= place:
        letter_freqs.append(0)
      letter_freqs[place] += 1

  if args.sort:
    key_fxn = lambda item: -item[1][0]
  else:
    key_fxn = lambda item: item[0]

  print('# '+' '.join(argv))
  for letter, counts in sorted(freqs.items(), key=key_fxn):
    print(letter, end='')
    for count in counts:
      print(f'\t{count}', end='')
    print()


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
