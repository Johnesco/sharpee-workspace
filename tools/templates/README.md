# {{title}}

{{description}}

Play it on IF Hub: {{hub_url}}

Written in [Chord](https://sharpee.net/chord/) for the [Sharpee](https://sharpee.net) engine. The whole game is `{{story_file}}`.

## Building

This game is built and published from the Sharpee workspace, which holds the shared tooling:

```
npx sharpee play                           # play in the terminal
npx sharpee test                           # replay {{id}}.tests.json
python ../tools/build.py {{id}} --force    # gates, build, tests, lay out the hub folder
python C:/code/ifhub/tools/ship.py {{id}}  # publish and list on IF Hub
```

## Walkthrough

[The commands, in order. `walkthrough.txt` at the root is generated from the tests document's main line.]
