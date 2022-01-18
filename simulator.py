#!/usr/bin/env python3
import argparse
import enum
import logging
import pathlib
import sys
import wordle

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_WORDLIST = pathlib.Path(SCRIPT_DIR/'words.txt')
DEFAULT_FREQ_LIST = SCRIPT_DIR/'letter-freqs.tsv'
DESCRIPTION = """"""


def make_argparser():
  parser = argparse.ArgumentParser(add_help=False, description=DESCRIPTION)
  options = parser.add_argument_group('Options')
  options.add_argument('answer',
    help='Test on this specific answer.')
  options.add_argument('-w', '--word-list', type=argparse.FileType('r'),
    default=DEFAULT_WORDLIST.open(),
    help=f'Word list to use. Default: {str(DEFAULT_WORDLIST)}')
  options.add_argument('-f', '--letter-freqs', type=argparse.FileType('r'),
    default=DEFAULT_FREQ_LIST.open(),
    help='File containing the frequencies of letters in all --word-length words.')
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

  answer = args.answer
  word_len = len(answer)

  words = wordle.read_wordlist(args.word_list, word_len)
  logging.info(f'Read {len(words)} {word_len} letter words.')
  freqs = wordle.read_letter_freqs(args.letter_freqs)

  fixed = [''] * word_len
  present = [''] * word_len
  absent = set()
  round = 1
  while True:
    print(f'Round {round}')
    candidates = wordle.get_candidates(words, freqs, fixed, present, absent)
    if len(candidates) <= 0:
      fail('Error: No candidates found.')
    guess = candidates[0]
    if guess == answer:
      print('  Found it!')
      break
    print(f'  Guessing {guess} (from {len(candidates)})')
    new_fixed, new_present, new_absent = simulate_round(answer, guess)
    feedback = format_feedback(guess, new_fixed, new_present, new_absent)
    logging.info(f'  Result:  {feedback}')
    fixed = wordle.add_fixed(fixed, new_fixed)
    present = wordle.add_present(present, new_present)
    absent = absent | new_absent
    round += 1


def simulate_round(answer, guess):
  fixed = [''] * len(answer)
  present = [''] * len(answer)
  absent = set()
  for i, letter in enumerate(guess):
    if answer[i] == letter:
      fixed[i] = letter
    elif letter in answer:
      present[i] += letter
    else:
      absent.add(letter)
  return fixed, present, absent


def format_feedback(guess, fixed, present, absent):
  feedback = [''] * len(fixed)
  for i, letter in enumerate(fixed):
    if letter:
      feedback[i] = 'G'
  for i, letters in enumerate(present):
    for letter in letters:
      if guess[i] == letter:
        feedback[i] = 'Y'
        break
  for letter in absent:
    for i, guess_letter in enumerate(guess):
      if letter == guess_letter:
        feedback[i] = '.'
  return ''.join(feedback)


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
