# Consent, labelling and licences

## Consent

| person | appears as | consent | recorded |
|---|---|---|---|
| none | | | |

No real person's face, likeness or voice is generated. The woman in the film is a generic, unnamed figure seen only from behind or as hands, and the family are seen from behind. The narration uses a prebuilt Gemini TTS voice; no one's voice is cloned.

If a real person is added (for example a relative's photo as a reference, or a line they said), their informed consent for this specific use, and for the exact words, is recorded in the table above **before** anything is generated. Without it the film scores zero.

## Labelling

- The film ends with a 3.5 s end card: "Made with AI" plus the models used.
- The platform's AI-content disclosure is switched on when posting (TikTok "AI-generated", YouTube "altered or synthetic content", Meta "AI info").
- Watermarks and provenance metadata from any model (SynthID, C2PA) are left intact; the pipeline does not strip metadata.

## Licences

| component | licence / terms | use here |
|---|---|---|
| FLUX.2 klein 4B (Black Forest Labs) via Cloudflare Workers AI | Apache 2.0 model; Cloudflare Workers AI terms | keyframes |
| Wan 2.2 TI2V-5B | Apache 2.0 | image-to-video |
| ACE-Step 1.5 | MIT; outputs usable commercially | score |
| Gemini TTS / Gemini API (free tier) | Google Gemini API terms; free-tier inputs may be used to improve Google products | narration |
| FFmpeg | LGPL/GPL | assembly |
| DejaVu Sans font | free licence (Bitstream Vera derivative) | titles, subtitles |
| Code in this repo | MIT | |

## Style and private data

- The look is described by its qualities (gouache, warm light, earth palette), never by naming a living artist.
- No private family details (names, addresses, photos) are sent to free endpoints, because some free tiers may train on inputs. The story is a shared cultural practice, not a private one.
