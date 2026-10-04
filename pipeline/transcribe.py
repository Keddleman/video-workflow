"""Word-level transcript. python3 transcribe.py audio.wav words.json [prompt]
The prompt biases spelling of product names (built from brands.json by run.sh)."""
import sys, json
from faster_whisper import WhisperModel
m = WhisperModel('small.en', device='cpu', compute_type='int8')
segs, _ = m.transcribe(sys.argv[1], word_timestamps=True, initial_prompt=sys.argv[3] if len(sys.argv) > 3 else None)
words = []
for s in segs:
    print(f'[{s.start:6.2f}] {s.text.strip()}')
    words += [[round(w.start, 2), round(w.end, 2), w.word.strip()] for w in s.words]
json.dump(words, open(sys.argv[2], 'w')); print('WORDS OK', len(words))
