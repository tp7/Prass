## Prass
Console processor for ASS subtitles.

This script is super pre-alpha so things might break, although they shouldn't. Feature requests and any kind of feedback are welcome.

### Why?
Imagine you've got a few dozens of subtitle files and you want to apply TPP to each of them, and maybe also restyle one of the files and use the same group of styles for everything else. This script allows you to easily do it from console so you don't have to suffer with Aegisub.

### Usage
The main script is called `prass.py` and it provides a few commands for working with subtitles.
```bash
# to convert subtitles from SRT to ASS
prass convert-srt input.srt -o output.ass
# to copy styles from one ASS script to another
prass copy-styles --from template.ass --to input.ass -o output.ass
# to sort an ASS script
prass sort input.ass --by time -o output.ass
# to run tpp
prass tpp input.ass -s default,alt --lead-in 100 --lead-out 200 --keyframes kfs.txt --fps 23.976 --kf-before-start 150 --kf-after-start 150
# to cleanup a script
prass cleanup --comments --empty-lines --styles input.ass -o output.ass
# to shift start time back by 1 minute and 10 seconds
prass shift --start --by -1:10 input.ass -o output.ass
```
Some parameters are not mentioned - just run `prass --help` or `prass %command% --help` to see the full docs.

### Pipes
Prass more or less supports pipes and allows you to do fun stuff like
```bash
prass convert-srt input.srt | prass copy-styles --from template.ass | prass sort --by time | prass tpp --overlap 150 --gap 150 -o out.ass
```
If you don't provide some file arguments, most commands will use stdin/stdout by default. They will also do this if you provide "-" as file paths.

### Installation
Prass should work on OS X, Linux and Windows without any problems. Right now the only dependency is [Click](http://click.pocoo.org/3/). Assuming you have python and pip, just run:
```bash
pip install git+https://github.com/tp7/prass
```
