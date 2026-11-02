"""IO capturing utilities."""

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import sys
from io import StringIO
from types import TracebackType
from typing import Any

#-----------------------------------------------------------------------------
# Classes and functions
#-----------------------------------------------------------------------------


class RichOutput:
    def __init__(self, data=None, metadata=None, transient=None, update=False):
        self.data = data or {}
        self.metadata = metadata or {}
        self.transient = transient or {}
        self.update = update

    def display(self):
        from IPython.display import publish_display_data
        publish_display_data(data=self.data, metadata=self.metadata,
                             transient=self.transient, update=self.update)

    def _repr_mime_(self, mime):
        if mime not in self.data:
            return
        data = self.data[mime]
        if mime in self.metadata:
            return data, self.metadata[mime]
        else:
            return data

    def _repr_mimebundle_(self, include=None, exclude=None):
        return self.data, self.metadata

    def _repr_html_(self):
        return self._repr_mime_("text/html")

    def _repr_latex_(self):
        return self._repr_mime_("text/latex")

    def _repr_json_(self):
        return self._repr_mime_("application/json")

    def _repr_javascript_(self):
        return self._repr_mime_("application/javascript")

    def _repr_png_(self):
        return self._repr_mime_("image/png")

    def _repr_jpeg_(self):
        return self._repr_mime_("image/jpeg")

    def _repr_svg_(self):
        return self._repr_mime_("image/svg+xml")


class LimitedStringIO(StringIO):
    """StringIO that keeps only the first ``max_chars`` written characters.

    Writes always succeed and characters beyond the cap are discarded; their
    number is accumulated in ``dropped``. Because each write is truncated at
    the current boundary, one large write and several smaller writes give the
    same retained text. ``max_chars=0`` discards every character written.
    """

    def __init__(self, max_chars: int):
        super().__init__()
        self.max_chars = max_chars
        self.dropped = 0
        self._retained = 0

    def write(self, __s: str) -> int:
        remaining = self.max_chars - self._retained
        n = len(__s)
        if remaining <= 0:
            self.dropped += n
        elif n <= remaining:
            super().write(__s)
            self._retained += n
        else:
            super().write(__s[:remaining])
            self.dropped += n - remaining
            self._retained = self.max_chars
        return n


class CapturedIO:
    """Simple object for containing captured stdout/err and rich display StringIO objects

    Each instance `c` has three attributes:

    - ``c.stdout`` : standard output as a string
    - ``c.stderr`` : standard error as a string
    - ``c.outputs``: a list of rich display outputs

    When a character limit is in effect, ``c.stdout_dropped`` and
    ``c.stderr_dropped`` report how many characters of each stream were
    discarded past that limit.

    Additionally, there's a ``c.show()`` method which will print all of the
    above in the same order, and can be invoked simply via ``c()``.
    """

    def __init__(
        self,
        stdout: StringIO | None,
        stderr: StringIO | None,
        outputs: list[Any] | None = None,
    ):
        self._stdout = stdout
        self._stderr = stderr
        if outputs is None:
            outputs = []
        self._outputs = outputs

    def __str__(self):
        return self.stdout

    @property
    def stdout(self) -> str:
        "Captured standard output"
        if not self._stdout:
            return ''
        return self._stdout.getvalue()

    @property
    def stderr(self) -> str:
        "Captured standard error"
        if not self._stderr:
            return ''
        return self._stderr.getvalue()

    @property
    def stdout_dropped(self) -> int:
        "Number of stdout characters discarded past the capture limit"
        if not self._stdout:
            return 0
        return getattr(self._stdout, "dropped", 0)

    @property
    def stderr_dropped(self) -> int:
        "Number of stderr characters discarded past the capture limit"
        if not self._stderr:
            return 0
        return getattr(self._stderr, "dropped", 0)

    @property
    def outputs(self) -> list[RichOutput]:
        """A list of the captured rich display outputs, if any.

        If you have a CapturedIO object ``c``, these can be displayed in IPython
        using::

            from IPython.display import display
            for o in c.outputs:
                display(o)
        """
        return [ RichOutput(**kargs) for kargs in self._outputs ]

    def show(self):
        """write my output to sys.stdout/err as appropriate"""
        sys.stdout.write(self.stdout)
        sys.stderr.write(self.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
        for kargs in self._outputs:
            RichOutput(**kargs).display()

    __call__ = show


class capture_output:
    """context manager for capturing stdout/err"""
    stdout = True
    stderr = True
    display = True

    def __init__(
        self,
        stdout: bool=True,
        stderr: bool=True,
        display: bool=True,
        stdout_limit: int | None=None,
        stderr_limit: int | None=None,
    ):
        if stdout_limit is not None and stdout_limit < 0:
            raise ValueError(
                f"stdout_limit must be >= 0 or None, got {stdout_limit!r}"
            )
        if stderr_limit is not None and stderr_limit < 0:
            raise ValueError(
                f"stderr_limit must be >= 0 or None, got {stderr_limit!r}"
            )
        self.stdout = stdout
        self.stderr = stderr
        self.display = display
        self.stdout_limit = stdout_limit
        self.stderr_limit = stderr_limit
        self.shell = None

    def __enter__(self) -> CapturedIO:
        from IPython.core.getipython import get_ipython
        from IPython.core.displaypub import CapturingDisplayPublisher
        from IPython.core.displayhook import CapturingDisplayHook

        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr

        if self.display:
            self.shell = get_ipython()
            if self.shell is None:
                self.save_display_pub = None
                self.display = False

        stdout = stderr = outputs = None
        if self.stdout:
            if self.stdout_limit is None:
                stdout = sys.stdout = StringIO()
            else:
                stdout = sys.stdout = LimitedStringIO(self.stdout_limit)
        if self.stderr:
            if self.stderr_limit is None:
                stderr = sys.stderr = StringIO()
            else:
                stderr = sys.stderr = LimitedStringIO(self.stderr_limit)
        if self.display:
            self.save_display_pub = self.shell.display_pub
            self.shell.display_pub = CapturingDisplayPublisher()
            outputs = self.shell.display_pub.outputs
            self.save_display_hook = sys.displayhook
            sys.displayhook = CapturingDisplayHook(shell=self.shell,
                                                   outputs=outputs)

        return CapturedIO(stdout, stderr, outputs)

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        if self.display and self.shell:
            self.shell.display_pub = self.save_display_pub
            sys.displayhook = self.save_display_hook
