import codecs
import os
import bisect
import re
import copy
import logging
from collections import OrderedDict

from common import PrassError, zip, map, itervalues, iterkeys, iteritems, py2_unicode_compatible


STYLES_SECTION = u"[V4+ Styles]"
EVENTS_SECTION = u"[Events]"
SCRIPT_INFO_SECTION = u"[Script Info]"


def parse_ass_time(string):
    hours, minutes, seconds, centiseconds = map(int, re.match(r"(\d+):(\d+):(\d+)\.(\d+)", string).groups())
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + centiseconds * 10


def parse_srt_time(string):
    hours, minutes, seconds, milliseconds = map(int, re.match(r"(\d+):(\d+):(\d+)\,(\d+)", string).groups())
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + milliseconds


def format_time(ms):
    cs = int(ms / 10.0)
    return u'{0}:{1:02d}:{2:02d}.{3:02d}'.format(
            int(cs // 360000),
            int((cs // 6000) % 60),
            int((cs // 100) % 60),
            int(cs % 100))


class AssStyle(object):
    def __init__(self, name, definition):
        self.name = name
        self.definition = definition

    @classmethod
    def from_string(cls, text):
        name, definition = text.split(',', 1)
        return cls(name=name.strip(), definition=definition.strip())

    def resample(self, from_width, from_height, to_width, to_height):
        scale_height = to_height / float(from_height)
        scale_width = to_width / float(from_width)
        old_ar = from_width / float(from_height)
        new_ar = to_width / float(to_height)
        horizontal_stretch = 1.0
        if abs(old_ar - new_ar) / new_ar > 0.01:
            horizontal_stretch = new_ar / old_ar

        parts = self.definition.split(",")
        parts[1] = "%i" % (round(int(parts[1]) * scale_height))  # font size
        parts[10] = "%g" % (float(parts[10]) * horizontal_stretch)  # scale x
        parts[12] = "%g" % (float(parts[12]) * scale_width)  # spacing
        parts[15] = "%g" % (float(parts[15]) * scale_height)  # outline
        parts[16] = "%g" % (float(parts[16]) * scale_height)  # shadow
        parts[18] = "%i" % (round(float(parts[18]) * scale_width))  # margin l
        parts[19] = "%i" % (round(float(parts[19]) * scale_width))  # margin r
        parts[20] = "%i" % (round(float(parts[20]) * scale_width))  # margin v

        self.definition = u",".join(parts)


@py2_unicode_compatible
class AssEvent(object):
    __slots__ = (
        "kind",
        "layer",
        "start",
        "end",
        "style",
        "actor",
        "margin_left",
        "margin_right",
        "margin_vertical",
        "effect",
        "text"
    )

    def __init__(self, start, end, text, kind='Dialogue', layer=0, style='Default', actor='',
                 margin_left=0, margin_right=0, margin_vertical=0, effect=''):
        self.kind = kind
        self.layer = layer
        self.start = start
        self.end = end
        self.style = style
        self.actor = actor
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_vertical = margin_vertical
        self.effect = effect
        self.text = text

    @classmethod
    def from_text(cls, text):
        kind, _, rest = text.partition(u":")
        split = [x.strip() for x in rest.split(',', 9)]
        return cls(
            kind=kind,
            layer=int(split[0]),
            start=parse_ass_time(split[1]),
            end=parse_ass_time(split[2]),
            style=split[3],
            actor=split[4],
            margin_left=split[5],
            margin_right=split[6],
            margin_vertical=split[7],
            effect=split[8],
            text=split[9]
        )

    def __str__(self):
        return u'{0}: {1},{2},{3},{4},{5},{6},{7},{8},{9},{10}'.format(self.kind, self.layer,
                                                                       format_time(self.start),
                                                                       format_time(self.end),
                                                                       self.style, self.actor,
                                                                       self.margin_left, self.margin_right,
                                                                       self.margin_vertical, self.effect,
                                                                       self.text)

    @property
    def is_comment(self):
        return self.kind.lower() == u'comment'

    def collides_with(self, other):
        if self.start < other.start:
            return self.end > other.start
        return self.start < other.end


class StylesSection(object):
    def __init__(self):
        self.styles = OrderedDict()

    def parse_line(self, text):
        if text.startswith(u'Format:'):
            return
        style = AssStyle.from_string(text.partition(u":")[2])
        self.styles[style.name] = style

    def format_section(self):
        lines = [u'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding']
        lines.extend(u'Style: {0},{1}'.format(style.name, style.definition) for style in itervalues(self.styles))
        return lines


class EventsSection(object):
    def __init__(self):
        self.events = []

    def parse_line(self, text):
        if text.startswith(u'Format:'):
            return
        self.events.append(AssEvent.from_text(text))

    def format_section(self):
        lines = [u'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
        lines.extend(u"%s" % x for x in self.events)
        return lines


class ScriptInfoSection(object):
    class PropertyLine(object):
        def __init__(self, name, value):
            self.name = name
            self.value = value

        @classmethod
        def from_string(cls, string_value):
            if string_value.startswith(';'):
                return cls(string_value, None)
            else:
                name, _, value = string_value.partition(':')
                return cls(name, value.strip())

        def to_string(self):
            if self.value is None:
                return self.name
            return "{0}: {1}".format(self.name, self.value)

    def __init__(self):
        self._lines_dict = OrderedDict()

    def parse_line(self, text):
        prop = self.PropertyLine.from_string(text)
        self._lines_dict[prop.name] = prop

    def format_section(self):
        return [x.to_string() for x in itervalues(self._lines_dict)]

    def get_property(self, name):
        if name not in self._lines_dict:
            raise KeyError("Property {0} not found".format(name))
        return self._lines_dict[name].value

    def set_property(self, name, value):
        if name not in self._lines_dict:
            self._lines_dict[name] = self.PropertyLine(name, str(value))
        else:
            self._lines_dict[name].value = str(value)

    def get_resolution(self):
        try:
            width = int(self.get_property("PlayResX"))
            height = int(self.get_property("PlayResY"))
            return width, height
        except KeyError:
            return None, None

    def set_resolution(self, width, height):
        self.set_property("PlayResX", width)
        self.set_property("PlayResY", height)


class GenericSection(object):
    def __init__(self):
        self.lines = []

    def parse_line(self, line):
        self.lines.append(line)

    def format_section(self):
        return self.lines


class AssScript(object):
    def __init__(self, sections_dict):
        super(AssScript, self).__init__()
        self._sections_dict = sections_dict

    @property
    def _events(self):
        return self._sections_dict[EVENTS_SECTION].events

    @_events.setter
    def _events(self, value):
        self._sections_dict[EVENTS_SECTION].events = value

    @property
    def _styles(self):
        return self._sections_dict[STYLES_SECTION].styles

    @classmethod
    def from_ass_stream(cls, file_object):
        sections = OrderedDict()
        current_section = None
        for idx, line in enumerate(file_object):
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            if low == u'[v4+ styles]':
                sections[STYLES_SECTION] = current_section = StylesSection()
            elif low == u'[events]':
                sections[EVENTS_SECTION] = current_section = EventsSection()
            elif low == u'[script info]':
                sections[SCRIPT_INFO_SECTION] = current_section = ScriptInfoSection()
            elif re.match(r'\[.+?\]', low):
                sections[line] = current_section = GenericSection()
            elif not current_section:
                raise PrassError(u"That's some invalid ASS script (no parse function at line {0})".format(idx))
            else:
                try:
                    current_section.parse_line(line)
                except Exception as e:
                    raise PrassError(u"That's some invalid ASS script: {0}".format(e.message))
        return cls(sections)

    @classmethod
    def from_ass_file(cls, path):
        try:
            with codecs.open(path, encoding='utf-8-sig') as script:
                return cls.from_ass_stream(script)
        except IOError:
            raise PrassError("Script {0} not found".format(path))

    @classmethod
    def from_srt_stream(cls, file_object):
        styles_section = StylesSection()
        events_section = EventsSection()

        for srt_event in file_object.read().replace('\r\n', '\n').split('\n\n'):
            if not srt_event:
                continue
            lines = srt_event.split('\n', 2)
            times = lines[1].split('-->')
            events_section.events.append(AssEvent(
                start=parse_srt_time(times[0].rstrip()),
                end=parse_srt_time(times[1].lstrip()),
                text=lines[2].replace('\n', r'\N')
            ))
        styles_section.styles[u'Default'] = AssStyle(u'Default', 'Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1')
        sections = OrderedDict()
        sections[SCRIPT_INFO_SECTION] = ScriptInfoSection()
        sections[SCRIPT_INFO_SECTION].parse_line(u'; Script converted by Prass')
        sections[STYLES_SECTION] = styles_section
        sections[EVENTS_SECTION] = events_section
        return cls(sections)

    def to_ass_stream(self, file_object):
        lines = []
        for name, section in iteritems(self._sections_dict):
            lines.append(name)
            lines.extend(section.format_section())
            lines.append(u"")

        file_object.write(os.linesep.join(lines))

    def to_ass_file(self, path):
        with codecs.open(path, encoding='utf-8-sig', mode='w') as script:
            self.to_ass_stream(script)

    def append_styles(self, other_script, clean, resample, forced_resolution=None):
        if clean:
            self._styles.clear()
        for style in itervalues(other_script._styles):
            self._styles[style.name] = copy.deepcopy(style)

        if not resample:
            return
        src_width, src_height = self._sections_dict[SCRIPT_INFO_SECTION].get_resolution()
        if forced_resolution:
            dst_width, dst_height = forced_resolution
        else:
            dst_width, dst_height = other_script._sections_dict[SCRIPT_INFO_SECTION].get_resolution()
        if all((src_width, src_height, dst_width, dst_height)):
            for style in itervalues(self._styles):
                style.resample(src_width, src_height, dst_width, dst_height)
            self._sections_dict[SCRIPT_INFO_SECTION].set_resolution(dst_width, dst_height)
        else:
            logging.info("Couldn't determine resolution, resampling disabled")

    def sort_events(self, key, descending):
        self._events.sort(key=key, reverse=descending)

    def tpp(self, styles, lead_in, lead_out, max_overlap, max_gap, adjacent_bias,
            keyframes_list, timecodes, kf_before_start, kf_after_start, kf_before_end, kf_after_end):

        def get_closest_kf(frame, keyframes):
            idx = bisect.bisect_left(keyframes, frame)
            if idx == len(keyframes):
                return keyframes[-1]
            if idx == 0 or keyframes[idx] - frame < frame - (keyframes[idx-1]):
                return keyframes[idx]
            return keyframes[idx-1]

        events_iter = (e for e in self._events if not e.is_comment)
        if styles:
            styles = set(s.lower() for s in styles)
            events_iter = (e for e in events_iter if e.style.lower() in styles)

        events_list = sorted(events_iter, key=lambda x: x.start)
        broken = next((e for e in events_list if e.start > e.end), None)
        if broken:
            raise PrassError("One of the lines in the file ({0}) has negative duration. Aborting.".format(broken))

        if lead_in:
            sorted_by_end = sorted(events_list, key=lambda x: x.end)
            for idx, event in enumerate(sorted_by_end):
                initial = max(event.start - lead_in, 0)
                for other in reversed(sorted_by_end[:idx]):
                    if other.end <= initial:
                        break
                    if not event.collides_with(other):
                        initial = max(initial, other.end)
                event.start = initial

        if lead_out:
            for idx, event in enumerate(events_list):
                initial = event.end + lead_out
                for other in events_list[idx:]:
                    if other.start > initial:
                        break
                    if not event.collides_with(other):
                        initial = min(initial, other.start)
                event.end = initial

        if max_overlap or max_gap:
            bias = adjacent_bias / 100.0

            for previous, current in zip(events_list, events_list[1:]):
                distance = current.start - previous.end
                if (distance < 0 and -distance <= max_overlap) or (distance > 0 and distance <= max_gap):
                    new_time = previous.end + distance * bias
                    current.start = new_time
                    previous.end = new_time

        if kf_before_start or kf_after_start or kf_before_end or kf_after_end:
            for event in events_list:
                start_frame = timecodes.get_frame_number(event.start, timecodes.TIMESTAMP_START)
                end_frame = timecodes.get_frame_number(event.end, timecodes.TIMESTAMP_END)

                closest_frame = get_closest_kf(start_frame, keyframes_list)
                closest_time = timecodes.get_frame_time(closest_frame, timecodes.TIMESTAMP_START)

                if (closest_frame > start_frame and closest_time - event.start <= kf_before_start) or \
                        (closest_frame < start_frame and event.start - closest_time <= kf_after_start):
                    event.start = closest_time

                closest_frame = get_closest_kf(end_frame, keyframes_list) - 1
                closest_time = timecodes.get_frame_time(closest_frame, timecodes.TIMESTAMP_END)
                if (closest_frame > end_frame and closest_time - event.end <= kf_before_end) or \
                        (closest_frame < end_frame and event.end - closest_time <= kf_after_end):
                    event.end = closest_time

    def cleanup(self, drop_comments, drop_empty_lines, drop_unused_styles, drop_actors, drop_effects, drop_spacing):
        if drop_comments:
            self._events = [e for e in self._events if not e.is_comment]

        if drop_empty_lines:
            self._events = [e for e in self._events if e.text]

        if drop_unused_styles:
            used_styles = set()

            for event in self._events:
                used_styles.add(event.style)
                for override_block in re.findall(r"{([^{}]*\\r[^{}]*)}", event.text):
                    for style in re.findall(r"\\r([^}\\]+)", override_block):
                        used_styles.add(style)

            for style_name in list(iterkeys(self._styles)):
                if style_name not in used_styles:
                    del self._styles[style_name]

        if drop_actors:
            for event in self._events:
                event.actor = ''

        if drop_effects:
            for event in self._events:
                event.effect = ''

        if drop_spacing:
            for event in self._events:
                event.text = re.sub(r"(\s|\\N|\\n)+", " ", event.text)

    def shift(self, shift, shift_start, shift_end):
        for event in self._events:
            if shift_start:
                event.start = max(event.start + shift, 0)
            if shift_end:
                event.end = max(event.end + shift, 0)
