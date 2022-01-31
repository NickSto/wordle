#!/usr/bin/env python3
import argparse
import collections
import logging
import pathlib
import time
import sys
import wordle

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_WORDLIST = SCRIPT_DIR/'words.txt'
DEFAULT_FREQ_LIST = SCRIPT_DIR/'letter-freqs.all-answers.tsv'
DEFAULT_WORD_STATS = SCRIPT_DIR/'stats-ghent-plus.tsv'
DESCRIPTION = """Simulate Wordle games and pit the solver algorithm against it."""


def make_argparser():
  parser = argparse.ArgumentParser(add_help=False, description=DESCRIPTION)
  options = parser.add_argument_group('Options')
  options.add_argument('-a', '--answer',
    help='Test on this specific answer.')
  options.add_argument('-A', '--answers', type=argparse.FileType('r'),
    help='Test on all the answers in this file and give summary statistics at the end.')
  options.add_argument('-1', '--guess1',
    help='Force it to use this as the first guess instead of the auto-generated one.')
  options.add_argument('-g', '--guess-thres', type=float, default=0.05,
    help='Word score threshold above which this will attempt to solve. Default: %(default)s')
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
  options.add_argument('-t', '--tsv', dest='format', default='human', action='store_const',
    const='tsv',
    help='Print tab-delimited, computer-readable stats at the end instead of human optimized '
      'output.')
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

  if args.answer:
    answers = [args.answer]
  elif args.answers:
    answers = list(wordle.read_wordlist(args.answers))
    if len(answers) == 0:
      fail('No answers found in --answers file.')
  else:
    fail('Must provide --answer or --answers.')

  word_len = len(answers[0])
  words = wordle.read_wordlist(args.word_list, word_len)
  logging.info(f'Read {len(words)} {word_len} letter words.')
  freqs = wordle.read_letter_freqs(args.letter_freqs)
  stats = wordle.read_word_stats(args.stats)

  if len(answers) == 1:
    simulate_game(answers[0], words, freqs, stats, guess_thres=args.guess_thres, verbose=True)
  else:
    rounds = collections.Counter()
    start = last = time.perf_counter()
    for answer_num, answer in enumerate(answers,1):
      round = simulate_game(
        answer, words, freqs, stats, guess_thres=args.guess_thres, guess1=args.guess1, verbose=False
      )
      rounds[round] += 1
      now = time.perf_counter()
      if now - last > 60:
        logging.error(f'On game {answer_num}')
        last = now
    elapsed = time.perf_counter() - start
    logging.error(f'{len(answers)} games in {elapsed/60:0.1f} min')
    total = sum(rounds.values())
    print('# '+' '.join(argv))
    for round, count in sorted(rounds.items()):
      if args.format == 'human':
        print(f'Round {round:2d}: {count} ({100*count/total:0.2f}%)')
      elif args.format == 'tsv':
        print(f'{round}\t{count}\t{100*count/total:0.2f}')


def simulate_game(
    answer, words, freqs, stats, guess_thres=None, guess1=None, max_rounds=None, verbose=False
  ):
  word_len = len(answer)
  fixed = [''] * word_len
  present = [''] * word_len
  absent = set()
  round = 1
  while True:
    if verbose:
      print(f'Round {round}')
    if guess1 and round == 1:
      guess = guess1
    else:
      guess = wordle.choose_word(words, freqs, stats, fixed, present, absent, guess_thres)
    if verbose:
      print(f'  Guessing {guess}')
    if guess == answer:
      if verbose:
        print('  Found it!')
      break
    new_fixed, new_present, new_absent = simulate_round(answer, guess)
    if verbose:
      feedback = format_feedback(guess, new_fixed, new_present, new_absent)
      print(f'  Result:  {feedback}')
    fixed = wordle.add_fixed(fixed, new_fixed)
    present = wordle.add_present(present, new_present)
    absent = absent | new_absent
    round += 1
    if max_rounds is not None and round > max_rounds:
      break
  if max_rounds is None or round <= max_rounds:
    return round


def simulate_round(answer, guess):
  fixed = [''] * len(answer)
  present = [''] * len(answer)
  absent = set()
  for i, letter in enumerate(guess):
    if answer[i] == letter:
      fixed[i] = letter
    elif letter in answer:
      #TODO: It looks like this isn't technically correct in all situations.
      #      If your guess includes multiple of the same letter, and one is in the right position,
      #      that will appear green (fixed), but the other will be gray, not yellow.
      #      See the one from 2022-01-02 (BOOST) and guess GLOSS.
      #      This probably doesn't affect the simulator, because its definition of "fixed",
      #      "present", and "absent" is consistent. But would a human receive different information?
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
