# -*- coding: utf-8 -*-
import unittest
import os
import codecs
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import subs


def get_script_path(name):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(script_dir, name)


def script_to_string(ass_script):
    buffer = StringIO()
    ass_script.to_ass_stream(buffer)
    return buffer.getvalue()


def load_script(name):
    with codecs.open(get_script_path(name), encoding="utf-8-sig") as input_file:
        return input_file.read()


class TestSubs(unittest.TestCase):
    maxDiff = None

    def test_cleanup(self):
        ass_script = subs.AssScript.from_ass_file(get_script_path("test_script.ass"))
        ass_script.cleanup(drop_actors=True, drop_comments=True, drop_effects=True,
                           drop_empty_lines=True, drop_unused_styles=True, drop_spacing=True)

        self.assertEqual(load_script("cleanup_script.ass"), script_to_string(ass_script))

    def test_noop(self):
        ass_script = subs.AssScript.from_ass_file(get_script_path("test_script.ass"))
        self.assertEqual(load_script("test_script.ass"), script_to_string(ass_script))


class TestStyles(unittest.TestCase):
    def test_resample(self):
        source = subs.AssStyle.from_string(u"Default,Arial,36,&H00FFFFFF,&H000000FF,&H00020713,&H00000000,-1,0,0,0,100,100,0,0,1,1.7,0,2,0,0,28,1")
        source.resample(from_width=848, from_height=480, to_width=1920, to_height=1080)
        self.assertEqual(source.definition, u"Arial,81,&H00FFFFFF,&H000000FF,&H00020713,&H00000000,-1,0,0,0,100,100,0,0,1,3.825,0,2,0,0,63,1")

