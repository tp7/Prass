#!/usr/bin/env python2
import click
import sys
from operator import attrgetter
from common import PrassError, zip, map
from subs import AssScript
from tools import Timecodes, parse_keyframes

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def parse_fps_string(fps_string):
    if '/' in fps_string:
        parts = fps_string.split('/')
        if len(parts) > 2:
            raise PrassError('Invalid fps value')
        try:
            return float(parts[0]) / float(parts[1])
        except ValueError:
            raise PrassError('Invalid fps value')
    else:
        try:
            return float(fps_string)
        except ValueError:
            raise PrassError('Invalid fps value')


def parse_shift_string(shift_string):
    try:
        if ':' in shift_string:
            negator = 1
            if shift_string.startswith('-'):
                negator = -1
                shift_string = shift_string[1:]
            parts = list(map(float, shift_string.split(':')))
            if len(parts) > 3:
                raise PrassError("Invalid shift value: '{0}'".format(shift_string))
            shift_seconds = sum(part * multiplier for part, multiplier in zip(reversed(parts), (1.0, 60.0, 3600.0)))
            return shift_seconds * 1000 * negator  # convert to ms
        else:
            if shift_string.endswith("ms"):
                return float(shift_string[:-2])
            elif shift_string.endswith("s"):
                return float(shift_string[:-1]) * 1000
            else:
                return float(shift_string) * 1000
    except ValueError:
        raise PrassError("Invalid shift value: '{0}'".format(shift_string))


def parse_resolution_string(resolution_string):
    if resolution_string == '720p':
        return 1280,720
    if resolution_string == '1080p':
        return 1920,1080
    for separator in (':', 'x', ","):
        if separator in resolution_string:
            width, _, height = resolution_string.partition(separator)
            try:
                return int(width), int(height)
            except ValueError:
                raise PrassError("Invalid resolution string: '{0}'".format(resolution_string))
    raise PrassError("Invalid resolution string: '{0}'".format(resolution_string))


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    pass


@cli.command("convert-srt", short_help="convert srt subtitles to ass")
@click.option("-o", "--output", "output_file", default='-', type=click.File(encoding="utf-8-sig", mode='w'))
@click.option("--encoding", "encoding", default='utf-8-sig', help="Encoding to use for the input SRT file")
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, allow_dash=True))
def convert_srt(input_path, output_file, encoding):
    """Convert SRT script to ASS.

    \b
    Example:
    $ prass convert-srt input.srt -o output.ass --encoding cp1251
    """
    try:
        with click.open_file(input_path, encoding=encoding) as input_file:
            AssScript.from_srt_stream(input_file).to_ass_stream(output_file)
    except LookupError:
        raise PrassError("Encoding {0} doesn't exist".format(encoding))


@cli.command('copy-styles', short_help="copy styles from one ass script to another")
@click.option("-o", "--output", "output_file", default="-", type=click.File(encoding="utf-8-sig", mode='w'))
@click.option('--to', 'dst_file', required=True, type=click.File(encoding='utf-8-sig', mode='r'),
              help="File to copy the styles to")
@click.option('--from', 'src_file', required=True, type=click.File(encoding='utf-8-sig', mode='r'),
              help="File to take the styles from")
@click.option('--clean', default=False, is_flag=True,
              help="Remove all older styles in the destination file")
@click.option('--resample/--no-resample', 'resample', default=True,
              help="Resample style resolution to match output script when possible")
@click.option('--resolution', 'forced_resolution', default=None, help="Assume resolution of the destination file")
def copy_styles(dst_file, src_file, output_file, clean, resample, forced_resolution):
    """Copy styles from one ASS script to another, write the result as a third script.
    You always have to provide the "from" argument, "to" defaults to stdin and "output" defaults to stdout.

    \b
    Simple usage:
    $ prass copy-styles --from template.ass --to unstyled.ass -o styled.ass
    With pipes:
    $ cat unstyled.ass | prass copy-styles --from template.ass | prass cleanup --comments -o out.ass
    """
    src_script = AssScript.from_ass_stream(src_file)
    dst_script = AssScript.from_ass_stream(dst_file)
    if forced_resolution:
        forced_resolution = parse_resolution_string(forced_resolution)

    dst_script.append_styles(src_script, clean, resample, forced_resolution)
    dst_script.to_ass_stream(output_file)


@cli.command('sort', short_help="sort ass script events")
@click.option("-o", "--output", "output_file", default='-', type=click.File(encoding="utf-8-sig", mode='w'), metavar="<path>")
@click.argument("input_file", type=click.File(encoding="utf-8-sig"))
@click.option('--by', 'sort_by', multiple=True, default=['start'], help="Parameter to sort by",
              type=click.Choice(['time', 'start', 'end', 'style', 'actor', 'effect', 'layer']))
@click.option('--desc', 'descending', default=False, is_flag=True, help="Descending order")
def sort_script(input_file, output_file, sort_by, descending):
    """Sort script by one or more parameters.

    \b
    Sorting by time:
    $ prass sort input.ass --by time -o output.ass
    Sorting by time and then by layer, both in descending order:
    $ prass sort input.ass --by time --by layer --desc -o output.ass

    """
    script = AssScript.from_ass_stream(input_file)
    attrs_map = {
        "start": "start",
        "time": "start",
        "end": "end",
        "style": "style",
        "actor": "actor",
        "effect": "effect",
        "layer": "layer"
    }
    getter = attrgetter(*[attrs_map[x] for x in sort_by])
    script.sort_events(getter, descending)
    script.to_ass_stream(output_file)


@cli.command('tpp', short_help="timing post-processor")
@click.option("-o", "--output", "output_file", default='-', type=click.File(encoding="utf-8-sig", mode='w'), metavar="<path>")
@click.argument("input_file", type=click.File(encoding="utf-8-sig"))
@click.option("-s", "--style", "styles", multiple=True, metavar="<names>",
              help="Style names to process. All by default. Use comma to separate, or supply it multiple times")
@click.option("--lead-in", "lead_in", default=0, type=int, metavar="<ms>",
              help="Lead-in value in milliseconds")
@click.option("--lead-out", "lead_out", default=0, type=int, metavar="<ms>",
              help="Lead-out value in milliseconds")
@click.option("--overlap", "max_overlap", default=0, type=int, metavar="<ms>",
              help="Maximum overlap for two lines to be made continuous, in milliseconds")
@click.option("--gap", "max_gap", default=0, type=int, metavar="<ms>",
              help="Maximum gap between two lines to be made continuous, in milliseconds")
@click.option("--bias", "adjacent_bias", default=50, type=click.IntRange(0, 100), metavar="<percent>",
              help="How to set the adjoining of lines. "
                   "0 - change start time of the second line, 100 - end time of the first line. "
                   "Values from 0 to 100 allowed.")
@click.option("--keyframes", "keyframes_path", type=click.Path(exists=True, readable=True, dir_okay=False), metavar="<path>",
              help="Path to keyframes file")
@click.option("--timecodes", "timecodes_path", type=click.Path(readable=True, dir_okay=False), metavar="<path>",
              help="Path to timecodes file")
@click.option("--fps", "fps", metavar="<float>",
              help="Fps provided as float value, in case you don't have timecodes")
@click.option("--kf-before-start", default=0, type=float, metavar="<ms>",
              help="Max distance between a keyframe and event start for it to be snapped, when keyframe is placed before the event")
@click.option("--kf-after-start", default=0, type=float, metavar="<ms>",
              help="Max distance between a keyframe and event start for it to be snapped, when keyframe is placed after the start time")
@click.option("--kf-before-end", default=0, type=float, metavar="<ms>",
              help="Max distance between a keyframe and event end for it to be snapped, when keyframe is placed before the end time")
@click.option("--kf-after-end", default=0, type=float, metavar="<ms>",
              help="Max distance between a keyframe and event end for it to be snapped, when keyframe is placed after the event")
def tpp(input_file, output_file, styles, lead_in, lead_out, max_overlap, max_gap, adjacent_bias,
        keyframes_path, timecodes_path, fps, kf_before_start, kf_after_start, kf_before_end, kf_after_end):
    """Timing post-processor.
    It's a pretty straightforward port from Aegisub so you should be familiar with it.
    You have to specify keyframes and timecodes (either as a CFR value or a timecodes file) if you want keyframe snapping.
    All parameters default to zero so if you don't want something - just don't put it in the command line.

    \b
    To add lead-in and lead-out:
    $ prass tpp input.ass --lead-in 50 --lead-out 150 -o output.ass
    To make adjacent lines continuous, with 80% bias to changing end time of the first line:
    $ prass tpp input.ass --overlap 50 --gap 200 --bias 80 -o output.ass
    To snap events to keyframes without a timecodes file:
    $ prass tpp input.ass --keyframes kfs.txt --fps 23.976 --kf-before-end 150 --kf-after-end 150 --kf-before-start 150 --kf-after-start 150 -o output.ass
    """

    if fps and timecodes_path:
        raise PrassError('Timecodes file and fps cannot be specified at the same time')
    if fps:
        timecodes = Timecodes.cfr(parse_fps_string(fps))
    elif timecodes_path:
        timecodes = Timecodes.from_file(timecodes_path)
    elif any((kf_before_start, kf_after_start, kf_before_end, kf_after_end)):
        raise PrassError('You have to provide either fps or timecodes file for keyframes processing')
    else:
        timecodes = None

    if timecodes and not keyframes_path:
        raise PrassError('You have to specify keyframes file for keyframes processing')

    keyframes_list = parse_keyframes(keyframes_path) if keyframes_path else None

    actual_styles = []
    for style in styles:
        actual_styles.extend(x.strip() for x in style.split(','))

    script = AssScript.from_ass_stream(input_file)
    script.tpp(actual_styles, lead_in, lead_out, max_overlap, max_gap, adjacent_bias,
               keyframes_list, timecodes, kf_before_start, kf_after_start, kf_before_end, kf_after_end)
    script.to_ass_stream(output_file)


@cli.command("cleanup", short_help="remove useless data from ass scripts")
@click.option("-o", "--output", "output_file", default='-', type=click.File(encoding="utf-8-sig", mode='w'), metavar="<path>")
@click.argument("input_file", type=click.File(encoding="utf-8-sig"))
@click.option("--comments", "drop_comments", default=False, is_flag=True,
              help="Remove commented lines")
@click.option("--empty-lines", "drop_empty_lines", default=False, is_flag=True,
              help="Remove empty lines")
@click.option("--styles", "drop_unused_styles", default=False, is_flag=True,
              help="Remove unused styles")
@click.option("--actors", "drop_actors", default=False, is_flag=True,
              help="Remove actor field")
@click.option("--effects", "drop_effects", default=False, is_flag=True,
              help="Remove effects field")
@click.option("--spacing", "drop_spacing", default=False, is_flag=True,
              help="Removes double spacing and newlines")
@click.option("--sections", "drop_sections", type=click.Choice(["fonts", "graphics", "aegi", "extradata"]), multiple=True,
              help="Remove optional sections from the script")
def cleanup(input_file, output_file, drop_comments, drop_empty_lines, drop_unused_styles,
            drop_actors, drop_effects, drop_spacing, drop_sections):
    """Remove junk data from ASS script

    \b
    To remove commented and empty lines plus clear unused styles:
    $ prass cleanup input.ass --comments --empty-lines --styles output.ass
    """
    sections_map = {
        "fonts": "[Fonts]",
        "graphics": "[Graphics]",
        "aegi": "[Aegisub Project Garbage]",
        "extradata": ["Aegisub Extradata"]
    }
    drop_sections = [sections_map[x] for x in drop_sections]

    script = AssScript.from_ass_stream(input_file)
    script.cleanup(drop_comments, drop_empty_lines, drop_unused_styles, drop_actors, drop_effects, drop_spacing, drop_sections)
    script.to_ass_stream(output_file)


@cli.command("shift", short_help="shift start or end times of every event")
@click.option("-o", "--output", "output_file", default='-', type=click.File(encoding="utf-8-sig", mode='w'), metavar="<path>")
@click.argument("input_file", type=click.File(encoding="utf-8-sig"))
@click.option("--by", "shift_by", required=True, metavar="<time>",
              help="Time to shift. Might be negative. 10.5s, 150ms or 1:12.23 formats are allowed, seconds assumed by default")
@click.option("--start", "shift_start", default=False, is_flag=True, help="Shift only start time")
@click.option("--end", "shift_end", default=False, is_flag=True, help="Shift only end time")
def shift(input_file, output_file, shift_by, shift_start, shift_end):
    """Shift all lines in a script by defined amount.

    \b
    You can use one of the following formats to specify the time:
        - "1.5s" or just "1.5" means 1 second 500 milliseconds
        - "150ms" means 150 milliseconds
        - "1:7:12.55" means 1 hour, 7 minutes, 12 seconds and 550 milliseconds. All parts are optional.
    Every format allows a negative sign before the value, which means "shift back", like "-12s"

    \b
    To shift both start end end time by one minute and 15 seconds:
    $ prass shift input.ass --by 1:15 -o output.ass
    To shift only start time by half a second back:
    $ prass shift input.ass --start --by -0.5s -o output.ass
    """
    if not shift_start and not shift_end:
        shift_start = shift_end = True

    shift_ms = parse_shift_string(shift_by)
    script = AssScript.from_ass_stream(input_file)
    script.shift(shift_ms, shift_start, shift_end)
    script.to_ass_stream(output_file)


if __name__ == '__main__':
    default_map = {}
    if not sys.stdin.isatty():
        for command, arg_name in (("convert-srt", "input_path"), ("copy-styles", "dst_file"),
                                  ("sort", "input_file"), ("tpp", "input_file"), ("cleanup", "input_file"),
                                  ('shift', "input_file")):
            default_map[command] = {arg_name: '-'}

    cli(default_map=default_map)
