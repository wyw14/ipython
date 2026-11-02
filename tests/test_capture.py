# encoding: utf-8
"""Tests for IPython.utils.capture"""

# -----------------------------------------------------------------------------
#  Copyright (C) 2013 The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------


import sys

import pytest

from IPython.utils import capture

# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------

_mime_map = dict(
    _repr_png_="image/png",
    _repr_jpeg_="image/jpeg",
    _repr_svg_="image/svg+xml",
    _repr_html_="text/html",
    _repr_json_="application/json",
    _repr_javascript_="application/javascript",
)

basic_data = {
    "image/png": b"binarydata",
    "text/html": "<b>bold</b>",
}
basic_metadata = {
    "image/png": {
        "width": 10,
        "height": 20,
    },
}

full_data = {
    "image/png": b"binarydata",
    "image/jpeg": b"binarydata",
    "image/svg+xml": "<svg>",
    "text/html": "<b>bold</b>",
    "application/javascript": "alert();",
    "application/json": "{}",
}
full_metadata = {
    "image/png": {"png": "exists"},
    "image/jpeg": {"jpeg": "exists"},
    "image/svg+xml": {"svg": "exists"},
    "text/html": {"html": "exists"},
    "application/javascript": {"js": "exists"},
    "application/json": {"json": "exists"},
}

hello_stdout = "hello, stdout"
hello_stderr = "hello, stderr"


# -----------------------------------------------------------------------------
# Test Functions
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("method_mime", _mime_map.items())
def test_rich_output_empty(method_mime):
    """RichOutput with no args"""
    rich = capture.RichOutput()
    method, mime = method_mime
    assert getattr(rich, method)() is None


def test_rich_output():
    """test RichOutput basics"""
    data = basic_data
    metadata = basic_metadata
    rich = capture.RichOutput(data=data, metadata=metadata)
    assert rich._repr_html_() == data["text/html"]
    assert rich._repr_png_() == (data["image/png"], metadata["image/png"])
    assert rich._repr_latex_() is None
    assert rich._repr_javascript_() is None
    assert rich._repr_svg_() is None


@pytest.mark.parametrize("method_mime", _mime_map.items())
def test_rich_output_no_metadata(method_mime):
    """test RichOutput with no metadata"""
    data = full_data
    rich = capture.RichOutput(data=data)
    method, mime = method_mime
    assert getattr(rich, method)() == data[mime]


@pytest.mark.parametrize("method_mime", _mime_map.items())
def test_rich_output_metadata(method_mime):
    """test RichOutput with metadata"""
    data = full_data
    metadata = full_metadata
    rich = capture.RichOutput(data=data, metadata=metadata)
    method, mime = method_mime
    assert getattr(rich, method)() == (data[mime], metadata[mime])


def test_rich_output_display():
    """test RichOutput.display

    This is a bit circular, because we are actually using the capture code we are testing
    to test itself.
    """
    data = full_data
    rich = capture.RichOutput(data=data)
    with capture.capture_output() as cap:
        rich.display()
    assert len(cap.outputs) == 1
    rich2 = cap.outputs[0]
    assert rich2.data == rich.data
    assert rich2.metadata == rich.metadata


def test_capture_output():
    """capture_output works"""
    rich = capture.RichOutput(data=full_data)
    with capture.capture_output() as cap:
        print(hello_stdout, end="")
        print(hello_stderr, end="", file=sys.stderr)
        rich.display()
    assert hello_stdout == cap.stdout
    assert hello_stderr == cap.stderr


def test_capture_output_no_stdout():
    """test capture_output(stdout=False)"""
    rich = capture.RichOutput(data=full_data)
    with capture.capture_output(stdout=False) as cap:
        print(hello_stdout, end="")
        print(hello_stderr, end="", file=sys.stderr)
        rich.display()
    assert "" == cap.stdout
    assert hello_stderr == cap.stderr
    assert len(cap.outputs) == 1


def test_capture_output_no_stderr():
    """test capture_output(stderr=False)"""
    rich = capture.RichOutput(data=full_data)
    # add nested capture_output so stderr doesn't make it to nose output
    with capture.capture_output(), capture.capture_output(stderr=False) as cap:
        print(hello_stdout, end="")
        print(hello_stderr, end="", file=sys.stderr)
        rich.display()
    assert hello_stdout == cap.stdout
    assert "" == cap.stderr
    assert len(cap.outputs) == 1


def test_capture_output_no_display():
    """test capture_output(display=False)"""
    data = full_data.copy()
    del data["image/png"]
    rich = capture.RichOutput(data=data)
    with capture.capture_output(display=False) as cap:
        print(hello_stdout, end="")
        print(hello_stderr, end="", file=sys.stderr)
        rich.display()
    assert hello_stdout == cap.stdout
    assert hello_stderr == cap.stderr
    assert cap.outputs == []


def test_captured_io_none_streams():
    """CapturedIO accepts None for stdout/stderr and returns empty strings."""
    cap = capture.CapturedIO(None, None)
    assert cap.stdout == ""
    assert cap.stderr == ""
    assert cap.outputs == []
    assert cap.stdout_dropped == 0
    assert cap.stderr_dropped == 0


def test_limited_string_io():
    """LimitedStringIO keeps the first N characters and counts the rest."""
    text = "abcdefghij"

    one_write = capture.LimitedStringIO(4)
    assert one_write.write(text) == len(text)
    assert one_write.getvalue() == "abcd"
    assert one_write.dropped == 6

    # many small writes must give the same result as one big write
    many_writes = capture.LimitedStringIO(4)
    for chunk in ("ab", "cd", "ef", "gh", "ij"):
        many_writes.write(chunk)
    assert many_writes.getvalue() == "abcd"
    assert many_writes.dropped == 6

    # writes straddling and landing exactly on the boundary
    boundary = capture.LimitedStringIO(4)
    for chunk in ("a", "bcde", "f"):
        boundary.write(chunk)
    assert boundary.getvalue() == "abcd"
    assert boundary.dropped == 2

    # writelines goes through write as well
    via_lines = capture.LimitedStringIO(4)
    via_lines.writelines(list(text))
    assert via_lines.getvalue() == "abcd"
    assert via_lines.dropped == 6


def test_limited_string_io_zero():
    """A limit of 0 discards every written character."""
    limited = capture.LimitedStringIO(0)
    assert limited.write("x") == 1
    limited.write("yz")
    assert limited.getvalue() == ""
    assert limited.dropped == 3


def test_capture_output_limits():
    """capture_output truncates each stream independently and keeps executing."""
    rich = capture.RichOutput(data=full_data)
    ran = []
    with capture.capture_output(stdout_limit=5, stderr_limit=3) as cap:
        print("stdout text", end="")
        print("stderr text", end="", file=sys.stderr)
        rich.display()
        ran.append(True)
    assert ran == [True]
    assert cap.stdout == "stdou"
    assert cap.stdout_dropped == 6
    assert cap.stderr == "std"
    assert cap.stderr_dropped == 8
    # rich display is unaffected by text limits
    assert len(cap.outputs) == 1

    # chunking the writes must not change the result
    with capture.capture_output(stdout_limit=5, stderr_limit=3) as cap2:
        for char in "stdout text":
            print(char, end="")
        for char in "stderr text":
            sys.stderr.write(char)
    assert cap2.stdout == cap.stdout
    assert cap2.stdout_dropped == cap.stdout_dropped
    assert cap2.stderr == cap.stderr
    assert cap2.stderr_dropped == cap.stderr_dropped


def test_capture_output_zero_limit():
    """A limit of 0 captures but discards all text."""
    with capture.capture_output(stdout_limit=0, stderr_limit=0) as cap:
        print("abc", end="")
        print("def", end="", file=sys.stderr)
    assert cap.stdout == ""
    assert cap.stderr == ""
    assert cap.stdout_dropped == 3
    assert cap.stderr_dropped == 3


def test_capture_output_negative_limit():
    """Negative limits are rejected before the body can run."""
    ran = []
    with pytest.raises(ValueError):
        with capture.capture_output(stdout_limit=-1):
            ran.append(True)
    assert ran == []
    with pytest.raises(ValueError):
        capture.capture_output(stderr_limit=-5)


def test_capture_output_limit_with_disabled_channel():
    """Limits are independent of disabling a channel entirely."""
    # nested capture keeps pass-through output out of the test run output
    with capture.capture_output(), capture.capture_output(
        stderr=False, stderr_limit=2
    ) as cap:
        print("hello stderr", end="", file=sys.stderr)
        print("hello stdout", end="")
    assert cap.stderr == ""
    assert cap.stderr_dropped == 0
    assert cap.stdout == "hello stdout"
    assert cap.stdout_dropped == 0


def test_capture_output_unlimited_reports_no_dropped():
    """Without a limit nothing is reported as dropped."""
    with capture.capture_output() as cap:
        print("abc", end="")
    assert cap.stdout == "abc"
    assert cap.stdout_dropped == 0
    assert cap.stderr_dropped == 0
