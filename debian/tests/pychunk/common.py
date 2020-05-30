"""Common routines for the Python zchunk tests."""

import argparse
import dataclasses
import os
import pathlib
import subprocess
import sys

from typing import Callable, Dict, List

from pychunk import defs


@dataclasses.dataclass(frozen=True)
class Config:
    """Common runtime configuration settings."""

    bindir: pathlib.Path
    env: Dict[str, str]

    orig: pathlib.Path
    compressed: pathlib.Path


@dataclasses.dataclass(frozen=True)
class Chunk:
    """A single chunk descriptor."""

    cstart: int
    start: int
    csize: int
    size: int
    cend: int
    end: int


def get_runenv() -> Dict[str, str]:
    """Set up the environment for running the zchunk programs."""
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    env["LANGUAGE"] = ""
    return env


def base_parser(prog: str) -> argparse.ArgumentParser:
    """Create a parser with the common options."""
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument(
        "-d",
        "--bindir",
        type=str,
        required=True,
        help="path to the directory containing the zchunk tools",
    )
    parser.add_argument(
        "-f",
        "--filename",
        type=str,
        required=True,
        help="path to the filename to compress",
    )

    return parser


def do_compress(cfg: Config, orig_size: int) -> int:
    """Compress the original file."""
    print(f"About to compress {cfg.orig} to {cfg.compressed}")
    if cfg.compressed.exists():
        sys.exit(f"Did not expect {cfg.compressed} to exist")
    subprocess.check_call(
        [cfg.bindir / "zck", "-o", cfg.compressed, "--", cfg.orig],
        shell=False,
        env=cfg.env,
    )
    if not cfg.compressed.is_file():
        sys.exit(f"zck did not create the {cfg.compressed} file")
    comp_size = cfg.compressed.stat().st_size
    print(f"{cfg.compressed} size is {comp_size} bytes long")
    if comp_size >= orig_size:
        sys.exit(
            f"sizeof({cfg.compressed}) == {comp_size} : "
            f"sizeof({cfg.orig}) == {orig_size}"
        )
    start = cfg.compressed.open(mode="rb").read(5)
    print(f"{cfg.compressed} starts with {start!r}")
    if start != defs.MAGIC:
        sys.exit(
            f"{cfg.compressed} does not start with {defs.MAGIC!r}: {start!r}"
        )

    return comp_size


def read_chunks(cfg: Config, orig_size: int, comp_size: int) -> Chunk:
    """Parse the chunks of the compressed file."""
    # pylint: disable=too-many-statements
    output = subprocess.check_output(
        [cfg.bindir / "zck_read_header", "-c", "--", cfg.compressed],
        shell=False,
        env=cfg.env,
    ).decode("UTF-8")

    params: Dict[str, int] = {}
    chunks: List[Chunk] = []

    def ignore_till_end(line: str) -> str:
        """Ignore anything until EOF."""
        raise NotImplementedError(line)

    def parse_chunk(line: str) -> str:
        """Parse a single chunk line."""
        # pylint: disable=too-many-branches
        data = defs.RE_CHUNK.match(line)
        if not data:
            sys.exit(f"Unexpected line for chunk {len(chunks)}: {line!r}")
        idx = int(data.group("idx"))
        start = int(data.group("start"))
        csize = int(data.group("comp_size"))
        size = int(data.group("size"))

        if idx != len(chunks):
            sys.exit(f"Expected index {len(chunks)}: {line!r}")
        if chunks:
            last_chunk = chunks[-1]
            if start != last_chunk.cend:
                sys.exit(f"Expected start {last_chunk.cend}: {line!r}")
        else:
            if start != params["size_diff"]:
                sys.exit(f"Expected start {params['size_diff']}: {line!r}")
            last_chunk = Chunk(
                cstart=0,
                start=0,
                csize=0,
                size=0,
                cend=params["size_diff"],
                end=0,
            )

        next_chunk = Chunk(
            cstart=start,
            start=last_chunk.end,
            csize=csize,
            size=size,
            cend=last_chunk.cend + csize,
            end=last_chunk.end + size,
        )
        if next_chunk.cend > comp_size:
            sys.exit(
                f"Compressed size overflow: {next_chunk.cend} > {comp_size}"
            )

        more = idx + 1 != params["chunk_count"]
        if more:
            if next_chunk.end >= orig_size:
                sys.exit(
                    f"Original size overflow: "
                    f"{next_chunk.end} >= {orig_size}"
                )
        else:
            if next_chunk.cend != comp_size:
                sys.exit(
                    f"Compressed size mismatch: "
                    f"{next_chunk.cend} != {comp_size}"
                )
            if next_chunk.end != orig_size:
                sys.exit(
                    f"Original size mismatch: "
                    f"{next_chunk.end} != {orig_size}"
                )

        print(f"- appending {next_chunk!r}")
        chunks.append(next_chunk)

        if more:
            return "parse_chunk"
        return "ignore_till_end"

    def wait_for_chunks(line: str) -> str:
        """Wait for the 'Chunks:' line."""
        if not defs.RE_CHUNKS.match(line):
            return "wait_for_chunks"

        return "parse_chunk"

    def wait_for_chunk_count(line: str) -> str:
        """Wait for the 'chunk count' line."""
        data = defs.RE_CHUNK_COUNT.match(line)
        if not data:
            return "wait_for_chunk_count"
        print(f"- got a chunk count: {data.groupdict()!r}")

        count = int(data.group("count"))
        if count < 1:
            sys.exit(f"zck_read_header said chunk count {count}")
        params["chunk_count"] = count

        return "wait_for_chunks"

    def wait_for_total_size(line: str) -> str:
        """Wait for the 'data size' line."""
        data = defs.RE_DATA_SIZE.match(line)
        if not data:
            return "wait_for_total_size"
        print(f"- got a size line: {data.groupdict()!r}")

        size = int(data.group("size"))
        if size < 1 or size > comp_size:
            sys.exit(
                f"zck_read_header said data size {size} (comp {comp_size})"
            )
        params["size_diff"] = comp_size - size

        return "wait_for_chunk_count"

    handlers: Dict[str, Callable[[str], str]] = {
        func.__name__: func
        for func in (
            wait_for_total_size,
            wait_for_chunk_count,
            wait_for_chunks,
            parse_chunk,
            ignore_till_end,
        )
    }

    handler: Callable[[str], str] = wait_for_total_size

    for line in output.splitlines():
        print(f"- read a line: {line}")
        new_handler = handler(line)
        assert new_handler in handlers, new_handler
        handler = handlers[new_handler]

    if handler != ignore_till_end:  # pylint: disable=comparison-with-callable
        sys.exit(f"handler is {handler!r} instead of {ignore_till_end!r}")

    # Now let's find the second chunk
    return next(chunk for chunk in chunks if chunk.start > 0)
