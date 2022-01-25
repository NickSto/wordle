# Builtins
import logging
import pathlib
# 3rd party
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
# Our modules
from utils.queryparams import QueryParams
from . import wordle
log = logging.getLogger(__name__)

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
WORD_LENGTH = 5
GUESS_THRES = 0.05
WORD_LIST_PATH = SCRIPT_DIR/'words.txt'
FREQS_PATH = SCRIPT_DIR/'letter-freqs.tsv'
STATS_PATH = SCRIPT_DIR/'stats-ghent-plus.tsv'

with WORD_LIST_PATH.open() as word_list_file:
  WORDS = wordle.read_wordlist(word_list_file, WORD_LENGTH)
with FREQS_PATH.open() as freqs_file:
  FREQS = wordle.read_letter_freqs(freqs_file)
with STATS_PATH.open() as stats_file:
  STATS = wordle.read_word_stats(stats_file)
log.info(
  f'Read {len(WORDS)} {WORD_LENGTH} letter words, {len(FREQS)} letter frequencies, and statistics '
  f'on {len(STATS)} words.'
)


##### Views #####


def main(request):
  return render(request, 'wordle/main.tmpl')


def guess(request):
  params = QueryParams()
  for i in range(1,WORD_LENGTH+1):
    params.add(f'green{i}', type=str)
    params.add(f'yellow{i}', type=str)
  params.add('grays', type=str)
  params.parse(request.POST)
  if params.invalid_value:
    log.error('Invalid query parameter.')
    return HttpResponse('Invalid input.', content_type=settings.PLAINTEXT)
  fixed = []
  present = []
  for i in range(1,WORD_LENGTH+1):
    # Greens
    letter_raw = params[f'green{i}']
    letter = letter_raw.lower().strip()
    if not (len(letter) == 1 or letter == ''):
      error = f'Must provide one green letter per position. Received {letter!r} instead.'
      log.error(error)
      return HttpResponse(error, content_type=settings.PLAINTEXT)
    fixed.append(letter)
    # Yellows
    letters_raw = params[f'yellow{i}']
    # Remove whitespace from ends and between letters.
    letters = ''.join(letters_raw.lower().strip().split())
    present.append(letters)
  # Grays
  letters_raw = params['grays']
  # Remove whitespace from ends and between letters.
  letters = ''.join(letters_raw.lower().strip().split())
  absent = set(letters) - set(fixed) - {'.',''}
  log.info(f'Got fixed letters   {fixed!r}')
  log.info(f'Got present letters {present!r}')
  log.info(f'Got absent letters  {"".join(absent)!r}')
  try:
    guess = wordle.choose_word(WORDS, FREQS, STATS, fixed, present, absent, GUESS_THRES)
  except wordle.WordleError as error:
    log.error(error)
    return HttpResponse(error.message, content_type=settings.PLAINTEXT)
  return HttpResponse(guess, content_type=settings.PLAINTEXT)
