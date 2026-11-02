Regex filters for ``%history``
==============================

The ``%history`` magic accepts two new regular-expression filters:

- ``-r PATTERN`` / ``--input-regex`` keeps entries whose input cell matches
  ``PATTERN`` (using :func:`re.search`).
- ``-R PATTERN`` / ``--output-regex`` keeps entries whose output matches
  ``PATTERN``; it implies ``-o`` so matching outputs are shown, and entries
  without an output never match.

The filters can be combined with each other and with ``-g``, ranges and
``-l``; all active filters must match. An invalid pattern raises a
``UsageError``.
