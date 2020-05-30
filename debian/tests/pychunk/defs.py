"""Definitions for the Python zchunk tests."""

import re


MAGIC = bytes([0, ord("Z"), ord("C"), ord("K"), ord("1")])

RE_DATA_SIZE = re.compile(
    r""" ^
    Data \s+ size \s* : \s*
    (?P<size> 0 | [1-9][0-9]* )
    \s*
    $ """,
    re.X,
)

RE_CHUNK_COUNT = re.compile(
    r""" ^
    Chunk \s+ count \s* : \s*
    (?P<count> 0 | [1-9][0-9]* )
    \s*
    $ """,
    re.X,
)

RE_CHUNKS = re.compile(
    r""" ^
    \s+
    Chunk \s+
    Checksum \s+
    Start \s+
    Comp \s size \s+
    Size \s*
    $ """,
    re.X,
)

RE_CHUNK = re.compile(
    r""" ^
    \s+
    (?P<idx> 0 | [1-9][0-9]* ) \s+
    (?P<cksum> \S+ ) \s+
    (?P<start> 0 | [1-9][0-9]* ) \s+
    (?P<comp_size> 0 | [1-9][0-9]* ) \s+
    (?P<size> 0 | [1-9][0-9]* ) \s*
    $ """,
    re.X,
)
