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
  return render(request, 'wordle/main.tmpl', {'word_length_range':range(1,WORD_LENGTH+1)})


def guess(request):
  params = QueryParams()
  for i in range(1,WORD_LENGTH+1):
    params.add(f'green{i}', type=lower_strip_whitespace)
    params.add(f'yellow{i}', type=lower_strip_whitespace)
  params.add('grays', type=lower_strip_whitespace)
  params.parse(request.POST)
  if params.invalid_value:
    log.error('Invalid query parameter.')
    return HttpResponse('Invalid input.', content_type=settings.PLAINTEXT)
  fixed = []
  present = []
  for i in range(1,WORD_LENGTH+1):
    # Greens
    letter = params[f'green{i}']
    if not (len(letter) == 1 or letter == ''):
      error = f'Must provide one green letter per position. Received {letter!r} instead.'
      log.error(error)
      return HttpResponse(error, content_type=settings.PLAINTEXT)
    fixed.append(letter)
    # Yellows
    letters = params[f'yellow{i}']
    present.append(letters)
  # Grays
  letters = params['grays']
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


def lower_strip_whitespace(raw_value):
  """Remove whitespace from the string (both internal and at the ends)."""
  if raw_value is None:
    return ''
  return ''.join(raw_value.lower().strip().split())
