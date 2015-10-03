import codecs
import os
import bisect
import re
from compat import zip, itervalues, py2_unicode_compatible
from common import PrassError
from collections import OrderedDict


def parse_ass_time(string):
    hours, minutes, seconds, centiseconds = map(int, re.match(r"(\d+):(\d+):(\d+)\.(\d+)", string).groups())
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + centiseconds * 10


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
        split = text.split(u':', 1)[1].split(',', 1)
        return cls(name=split[0].strip(), definition=split[1].strip())


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
        split = text.split(u':', 1)
        kind = split[0]

        split = [x.strip() for x in split[1].split(',', 9)]
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


class AssScript(object):
    STYLES_NAME = u"[V4+ Styles]"
    EVENTS_NAME = u"[Events]"
    SCRIPT_INFO_NAME = u"[Script Info]"

    class StylesSection(object):
        def __init__(self):
            self.name = AssScript.STYLES_NAME
            self.styles = OrderedDict()

        def parse_line(self, text):
            if text.startswith(u'Format:'):
                return
            style = AssStyle.from_string(text)
            self.styles[style.name] = style

        def format_section(self):
            lines = [self.name, u'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding']
            lines.extend(u'Style: {0},{1}'.format(style.name, style.definition) for style in itervalues(self.styles))
            return lines

        def clear(self):
            self.styles = OrderedDict()

    class EventsSection(object):
        def __init__(self):
            self.name = AssScript.EVENTS_NAME
            self.events = []

        def parse_line(self, text):
            if text.startswith(u'Format:'):
                return
            self.events.append(AssEvent.from_text(text))

        def format_section(self):
            lines = [self.name, u'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
            lines.extend(u"%s" % x for x in self.events)
            return lines

    class GenericSection(object):
        def __init__(self, section_name):
            self.name = section_name
            self.lines = []

        def parse_line(self, line):
            self.lines.append(line)

        def format_section(self):
            return [self.name] + self.lines

    def __init__(self, sections_dict):
        super(AssScript, self).__init__()
        self._sections_dict = sections_dict
        self._events_section = sections_dict[self.EVENTS_NAME]
        self._styles_section = sections_dict[self.STYLES_NAME]

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
                sections[cls.STYLES_NAME] = current_section = cls.StylesSection()
            elif low == u'[events]':
                sections[cls.EVENTS_NAME] = current_section = cls.EventsSection()
            elif re.match(r'\[.+?\]', low):
                sections[line] = current_section = cls.GenericSection(line)
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
        styles_section = cls.StylesSection()
        events_section = cls.EventsSection()
        parse_time = lambda x: parse_ass_time(x.replace(',', '.'))

        for srt_event in file_object.read().replace('\r\n', '\n').split('\n\n'):
            if not srt_event:
                continue
            lines = srt_event.split('\n', 2)
            times = lines[1].split('-->')
            events_section.events.append(AssEvent(
                start=parse_time(times[0].rstrip()),
                end=parse_time(times[1].lstrip()),
                text=lines[2].replace('\n', r'\N')
            ))
        styles_section.styles[u'Default'] = AssStyle(u'Default', 'Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1')
        sections = OrderedDict()
        sections[cls.SCRIPT_INFO_NAME] = cls.GenericSection(cls.SCRIPT_INFO_NAME)
        sections[cls.SCRIPT_INFO_NAME].lines.append(u'; Script converted by Prass')
        sections[styles_section.name] = styles_section
        sections[events_section] = events_section
        return cls(sections)

    def to_ass_stream(self, file_object):
        lines = []
        for section in itervalues(self._sections_dict):
            lines.extend(section.format_section())
            lines.append(u"")

        file_object.write(os.linesep.join(lines))

    def to_ass_file(self, path):
        with codecs.open(path, encoding='utf-8-sig', mode='w') as script:
            self.to_ass_stream(script)

    def append_styles(self, other_script, clean):
        if clean:
            self._styles_section.clear()
        for style in itervalues(other_script._styles_section.styles):
            self._styles_section.styles[style.name] = style

    def sort_events(self, key, descending):
        self._events_section.events.sort(key=key, reverse=descending)

    def tpp(self, styles, lead_in, lead_out, max_overlap, max_gap, adjacent_bias,
            keyframes_list, timecodes, kf_before_start, kf_after_start, kf_before_end, kf_after_end):

        def get_closest_kf(frame, keyframes):
            idx = bisect.bisect_left(keyframes, frame)
            if idx == len(keyframes):
                return keyframes[-1]
            if idx == 0 or keyframes[idx] - frame < frame - (keyframes[idx-1]):
                return keyframes[idx]
            return keyframes[idx-1]


        events_iter = (e for e in self._events_section.events if not e.is_comment)
        if styles:
            styles = set(s.lower() for s in styles)
            events_iter = (e for e in events_iter if e.style.lower() in styles)

        events_list = sorted(events_iter, key=lambda x: x.start)
        broken = next((e for e in events_list if e.start > e.end), None)
        if broken:
            raise PrassError("One of the lines in the file ({0}) has negative duration. Aborting.".format(broken))

        # all times are converted to seconds because that's how we roll
        if lead_in:
            sorted_by_end = sorted(events_list, key=lambda x: x.end)
            for idx, event in enumerate(sorted_by_end):
                initial = event.start - lead_in
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
            bias = adjacent_bias/100.0

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

    def cleanup(self, drop_comments, drop_empty_lines, drop_unused_styles, drop_actors, drop_effects):
        if drop_comments:
            self._events_section.events = [e for e in self._events_section.events if not e.is_comment]

        if drop_empty_lines:
            self._events_section.events = [e for e in self._events_section.events if e.text]

        if drop_unused_styles:
            used_styles = set()

            for event in self._events_section.events:
                used_styles.add(event.style)
                if '\\r' in event.text:  # fast dirty check because these lines are very rare
                    for override_block in re.findall(r"{([^{}]*\\r[^{}]*)}", event.text):
                        for style in re.findall(r"\\r([^}\\]+)", override_block):
                            used_styles.add(style)

            for style_name in self._styles_section.styles.keys():
                if style_name not in used_styles:
                    del self._styles_section.styles[style_name]

        if drop_actors:
            for event in self._events_section.events:
                event.actor = ''

        if drop_effects:
            for event in self._events_section.events:
                event.effect = ''

    def shift(self, shift, shift_start, shift_end):
        for event in self._events_section.events:
            if shift_start:
                event.start = max(event.start + shift, 0)
            if shift_end:
                event.end = max(event.end + shift, 0)
