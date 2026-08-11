# Day Three bonus evidence

This file distinguishes built evidence from external publication steps. Nothing is called awarded
until judges accept it.

## Additional Google AI models: full 0.6 allowance evidenced

| Model | Product job | Execution proof | Safety boundary |
|---|---|---|---|
| Gemma 4, gemma-4-26b-a4b-it-maas | Reviews already-pattern-redacted text for remaining person-name spans | app/scripts/record_gemma.py and app/fixtures/recordings/gemma_names.json | Spans only, never prose; fails closed |
| Gemini 3.1 Flash Image, gemini-3.1-flash-image | Creates the optional first-use workflow illustration | app/scripts/record_bonus_media.py and app/web/media/day-three-visual-briefing.png | No data, measurements, drug names, or recommendation |
| Veo 3.1 Fast, veo-3.1-fast-generate-001 | Creates the optional four-second workflow motion briefing | app/scripts/record_bonus_media.py and app/web/media/day-three-wake-briefing.mp4 | No autoplay and no clinical execution role |

The live Vertex model catalog did not expose a current Imagen endpoint. Day Three therefore does
not claim Imagen. It names the exact served Google image model instead. Both media records include
the prompt, location, byte count, and SHA-256 hash in app/web/media/bonus-media-provenance.json.

Run python scripts/record_bonus_media.py from app to regenerate both assets with Application
Default Credentials. Tests in app/tests/test_bonus_media.py verify integrity, public labels, model
IDs, absence of autoplay, and separation from clinical execution.

## Public build content: published evidence for up to 0.2

[The Antibiotic Review That Software Quietly Forgets](https://dev.to/ujwal240/the-antibiotic-review-that-software-quietly-forgets-2ane)
is public on DEV Community and contains the required hackathon-purpose disclosure. Add this exact
URL to the Day Three Devpost submission. Judges determine whether the contribution earns the bonus.

## Social publication: 0.2 after publication

The publication-ready copy is docs/social-post.md. It contains the exact hashtag
#AllThingsAgenticHackathon. Add the public demo-video URL, publish from an eligible social account,
and paste the final public post URL into Devpost.

## Maximum score path

A 5.0 core score plus 0.6 model points, 0.2 public-build-content points, and 0.2 social points equals
the Rules maximum of 6.0. The model evidence is built and the build content is public. The remaining
publication step is the social post; every public evidence URL must also be entered accurately in
Devpost. Judges determine all bonus awards.
