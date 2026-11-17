# Nightreign Guide

Weapon drop odds for Elden Ring Nightreign, read straight from the game's params.

**Demo: https://frcynda.github.io/nightreign-guide/app/**

- Pick a weapon and see every boss, enemy and chest that can drop it, with the chance per source.
- Filter by hero, Dormant Power relic, Discovery, Normal / Deep of Night and Shifting Earth map.
- "By boss" view: pick a boss and see every weapon each reward choice can give.

## How it works

`extract/` reads the game files (params, maps, event scripts) and writes `app/data.js` and the icons.
`app/index.html` is a single static page that computes the odds in the browser.

To rebuild the data you need your own copy of the game, plus a `tools/` folder (not included) with
Smithbox's archive keys and name lists, WitchyBND (to unpack `regulation.bin` and the text into
`data/raw`) and `oo2core_9_win64.dll` from the game folder.

```
cd extract
python unpack.py        # maps + event scripts -> ../data/game
python extract.py       # -> app/data.js
python icons.py         # menu textures
python icons.py export  # -> app/icons
```

Game data and art belong to FromSoftware / Bandai Namco. This is an unofficial fan project.
