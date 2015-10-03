# -*- coding: utf-8 -*-
import unittest

import tools


class TestTimecodes(unittest.TestCase):
    def test_frame_number_exact(self):
        timecodes = tools.Timecodes.cfr(fps=1.0)
        self.assertEqual(0, timecodes.get_frame_number(0))
        self.assertEqual(0, timecodes.get_frame_number(999))
        self.assertEqual(1, timecodes.get_frame_number(1000))
        self.assertEqual(1, timecodes.get_frame_number(1999))
        self.assertEqual(100, timecodes.get_frame_number(100000))

    def test_get_frame_number_start(self):
        timecodes = tools.Timecodes.cfr(fps=1.0)
        self.assertEqual(0, timecodes.get_frame_number(0, timecodes.TIMESTAMP_START))
        self.assertEqual(1, timecodes.get_frame_number(1, timecodes.TIMESTAMP_START))
        self.assertEqual(1, timecodes.get_frame_number(1000, timecodes.TIMESTAMP_START))
        self.assertEqual(2, timecodes.get_frame_number(1001, timecodes.TIMESTAMP_START))
        self.assertEqual(100, timecodes.get_frame_number(100000, timecodes.TIMESTAMP_START))

    def test_get_frame_number_end(self):
        timecodes = tools.Timecodes.cfr(fps=1.0)
        self.assertEqual(-1, timecodes.get_frame_number(0, timecodes.TIMESTAMP_END))
        self.assertEqual(0, timecodes.get_frame_number(1, timecodes.TIMESTAMP_END))
        self.assertEqual(0, timecodes.get_frame_number(1000, timecodes.TIMESTAMP_END))
        self.assertEqual(1, timecodes.get_frame_number(1001, timecodes.TIMESTAMP_END))
        self.assertEqual(99, timecodes.get_frame_number(100000, timecodes.TIMESTAMP_END))

    def test_get_frame_time_exact(self):
        timecodes = tools.Timecodes.cfr(fps=1.0)
        self.assertEqual(0, timecodes.get_frame_time(0))
        self.assertEqual(1000, timecodes.get_frame_time(1))
        self.assertEqual(2000, timecodes.get_frame_time(2))

    def test_get_frame_time_start(self):
        timecodes = tools.Timecodes.cfr(fps=1.0)
        self.assertEqual(-500, timecodes.get_frame_time(0, timecodes.TIMESTAMP_START))
        self.assertEqual(500, timecodes.get_frame_time(1, timecodes.TIMESTAMP_START))
        self.assertEqual(1500, timecodes.get_frame_time(2, timecodes.TIMESTAMP_START))

    def test_get_frame_time_end(self):
        timecodes = tools.Timecodes.cfr(fps=1.0)
        self.assertEqual(500, timecodes.get_frame_time(0, timecodes.TIMESTAMP_END))
        self.assertEqual(1500, timecodes.get_frame_time(1, timecodes.TIMESTAMP_END))
        self.assertEqual(2500, timecodes.get_frame_time(2, timecodes.TIMESTAMP_END))
