PY ?= python3

.PHONY: help setup smoke validate status keyframes sheet narration radio bundle import-shots import-music film report clean-edit

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/\t/'

setup:           ## install Python deps (ffmpeg must be installed separately)
	$(PY) -m pip install -r requirements.txt

smoke:           ## call every provider once, log latency to runs.jsonl
	$(PY) -m pipeline.smoke

validate:        ## validate storyboard.json against the schema
	$(PY) -m pipeline.validate

status:          ## what is cached / stale / missing per shot
	$(PY) -m pipeline.run status

sheet:           ## reference sheets (4 seeds per character/prop)
	$(PY) -m pipeline.keyframes --sheet

keyframes:       ## keyframes for every shot (cached)
	$(PY) -m pipeline.keyframes

narration:       ## Amharic narration, one WAV per shot (cached)
	$(PY) -m pipeline.narration

radio:           ## radio cut: narration + temp music on black, subtitled
	$(PY) -m pipeline.run radio

bundle:          ## pack pending Wan + ACE-Step jobs for Kaggle -> build/kaggle_jobs.zip
	$(PY) -m pipeline.kaggle_bundle

import-shots:    ## import Wan clips: make import-shots DIR=~/Downloads/clips
	$(PY) -m pipeline.shots import $(DIR)

import-music:    ## import ACE-Step candidates: make import-music DIR=~/Downloads/music
	$(PY) -m pipeline.music import $(DIR)

film:            ## THE command: validate, keyframes, narration, assemble 9:16 + 16:9
	$(PY) -m pipeline.run all

report:          ## refresh measured tables in COSTS.md and the shot table in DESIGN.md
	$(PY) -m pipeline.report

clean-edit:      ## drop rendered edit pieces (model outputs are kept)
	rm -rf outputs/edit outputs/film
