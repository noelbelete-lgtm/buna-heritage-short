# Design

## Audience

<!-- Confirm or rewrite this before generating anything. -->
**Who:** young Ethiopians, roughly 20–35, especially those living abroad or in cities, who grew up with buna at home but rarely sit through a full ceremony now.

**Where:** on a phone, vertical, in a TikTok, Instagram or Telegram feed, often with sound on but while scrolling.

**What they should feel at the end:** the warmth of being home at that hour of the afternoon, and the understanding that buna is about time spent together, not about coffee.

**Define:** *How might we remind young Ethiopians who live far from home that the coffee ceremony is a way of being together, in under 90 seconds?*

## Intent and choices

- **Structure follows the ceremony.** The three cups (abol, tona, bereka) are the three acts, so the film has a shape the audience already knows.
- **Smoke is the motif.** It appears in s01, s03, s04, s06 and s10, and ends the film.
- **No faces.** Hands, backs and objects carry the story. Viewers can project their own mother or grandmother onto it, there is no identity to drift between shots, and no real person's likeness is used.
- **Painted, not photoreal.** A warm gouache look reads as memory, holds together better across shots than realism, and is clearly not documentary footage.
- **Amharic narration, English subtitles.** The voice is in the language of the ceremony, and the subtitles open it to the diaspora and to friends.

## Shots and why each exists

<!-- SHOTS:BEGIN -->
| shot | size | beat | why it exists |
|---|---|---|---|
| s01 | extreme wide | Arrival: a home in the highlands, smoke already rising | Establishes place and time of day; the rising smoke is the film's motif and promises the ceremony before we see it. |
| s02 | close up | Preparation: the home is made ready | The ceremony starts with care for the space itself; hands only, so there is no face to drift between shots. |
| s03 | insert | Transformation: raw beans become coffee | Shows the change from raw to ready; scent is invisible, so smoke stands in for it. |
| s04 | medium | Inclusion: the smoke is carried to everyone | The gesture that says everyone belongs; seen from behind to keep the woman consistent. |
| s05 | close up | First cup: abol | Names the first round; the pour from a height is the iconic image of buna. |
| s06 | medium wide | Gathering: popcorn, incense, talk | Widens from objects to people; the conversation is the real point of the ceremony. |
| s07 | close up | Second cup: tona | Time passing: the jebena is refilled; lighter coffee, warmer talk. |
| s08 | insert | What happens here: news, peace, laughter | The emotional centre; an elder's hands hold the memory the film is about. |
| s09 | close up | Third cup: bereka, the blessing | Climax: the cup that gives the ceremony its meaning; mirrors the abol pour so the structure is felt. |
| s10 | wide | After: the room keeps the warmth | Absence after presence; the last wisp of smoke closes the motif and leaves the viewer with the meaning. |
<!-- SHOTS:END -->

## User test 1: radio cut

**Date:**
**Prototype:** `outputs/film/radio_cut.mp4` (narration + temp music on black, English subtitles)
**People (at least 3 from the audience; first name or initials, how they fit the audience, in person or on Slack):**

1.
2.
3.

**Questions asked:** What did you feel at the end? Which line stayed with you? Where did your attention drift? Was any Amharic word mispronounced? Too fast or too slow?

**What they said (their words, not a summary):**

**What I will change (and the storyboard field it touches):**

## User test 2: near-final cut

**Date:**
**Prototype:** `outputs/film/buna_9x16.mp4`, commit:
**People:**

1.
2.
3.

**What they said:**

**What changed:**




## User test: rough cut (Ken Burns stills, Amharic narration, temp music)

**Date:** 25 Nov
**Prototype:** outputs/film/buna_9x16.mp4, commit 4aac8de
**How shared:** (Telegram / WhatsApp / Slack / in person)

| person | what they said | what I changed |
|---|---|---|
| Dawit | The story is interesting, but the images don't look realistic enough; they feel a little artificial. | Replacing the still pan-and-zoom shots with Wan 2.2 image-to-video clips (real motion); keeping the painted style on purpose, since it reads as memory, and checking whether motion alone fixes "artificial". |
| Natnael | The voice stops for a moment and then continues; the audio flow needs to be smoother. | Shot length now follows the narration (planned length was up to 1.5 s longer than the voice), and the silence between lines is shorter. |
| Dibora | I liked the cultural connection, but the ending could be more emotional and engaging. | Rewriting the s10 narration line and letting the score rise under the last shot and the end card. |

**Insight:** the story lands; what holds it back is the craft (stillness, gaps, a flat ending), not the concept.
**Status of user test 2 (26 Nov):** the near-final cut was shared in the cohort's #all-technical-challenge Slack channel; no replies arrived before the deadline.
