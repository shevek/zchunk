"""Compile a test program."""

import dataclasses
import os
import pathlib
import subprocess
import sys
import tempfile

from pychunk import common


@dataclasses.dataclass(frozen=True)
class Config(common.Config):
    """Runtime configuration."""

    # pylint: disable=too-many-instance-attributes

    tempd: pathlib.Path
    source: pathlib.Path
    obj: pathlib.Path
    program: pathlib.Path

    uncompressed: pathlib.Path


def parse_args(dirname: str) -> Config:
    """Parse the command-line arguments, deduce some things."""
    parser = common.base_parser("compile")
    parser.add_argument(
        "source", type=str, help="path to the test program source file",
    )

    args = parser.parse_args()

    tempd = pathlib.Path(dirname).absolute()
    return Config(
        tempd=tempd,
        bindir=pathlib.Path(args.bindir),
        source=pathlib.Path(args.source),
        obj=tempd / "chunk.o",
        program=tempd / "chunk",
        env=common.get_runenv(),
        orig=pathlib.Path(args.filename).absolute(),
        compressed=tempd / "words.txt.zck",
        uncompressed=tempd / "chunk.txt",
    )


def do_compile(cfg: Config) -> None:
    """Compile the test program."""
    print("Fetching the C compiler flags for zck")
    cflags = (
        subprocess.check_output(
            ["pkg-config", "--cflags", "zck"], shell=False, env=cfg.env
        )
        .decode("UTF-8")
        .rstrip("\r\n")
    )
    if "\r" in cflags or "\n" in cflags:
        sys.exit(f"`pkg-config --cflags zck` returned {cflags!r}")

    if cfg.obj.exists():
        sys.exit(f"Did not expect {cfg.obj} to exist")
    cmd = f"cc -c -o '{cfg.obj}' {cflags} '{cfg.source}'"
    print(f"Running {cmd!r}")
    subprocess.check_call(cmd, shell=True, env=cfg.env)
    if not cfg.obj.is_file():
        sys.exit(f"{cmd!r} did not create the {cfg.obj} file")

    print("Fetching the C linker flags and libraries for zck")
    libs = (
        subprocess.check_output(
            ["pkg-config", "--libs", "zck"], shell=False, env=cfg.env
        )
        .decode("UTF-8")
        .rstrip("\r\n")
    )
    if "\r" in libs or "\n" in libs:
        sys.exit(f"`pkg-config --libs zck` returned {libs!r}")

    if cfg.program.exists():
        sys.exit(f"Did not expect {cfg.program} to exist")
    cmd = f"cc -o '{cfg.program}' '{cfg.obj}' {libs}"
    print(f"Running {cmd!r}")
    subprocess.check_call(cmd, shell=True, env=cfg.env)
    if not cfg.program.is_file():
        sys.exit(f"{cmd!r} did not create the {cfg.program} file")
    if not os.access(cfg.program, os.X_OK):
        sys.exit(f"Not an executable file: {cfg.program}")
    print(f"Looks like we got {cfg.program}")


def run_program(cfg: Config) -> None:
    """Run the test program, hopefully generate the chunk file."""
    print(f"About to run {cfg.program}")
    if cfg.uncompressed.exists():
        sys.exit(f"Did not expect {cfg.uncompressed} to exist")
    subprocess.check_call(
        [cfg.program, cfg.compressed, cfg.uncompressed],
        shell=False,
        env=cfg.env,
    )
    if not cfg.uncompressed.is_file():
        sys.exit(f"{cfg.program} did not create the {cfg.uncompressed} file")


def compare_chunk(cfg: Config, second: common.Chunk, orig_size: int) -> None:
    """Read data from the input file and the chunk."""
    # OK, let's load it all into memory, mmkay?
    contents = cfg.orig.read_bytes()
    if len(contents) != orig_size:
        sys.exit(
            f"Could not read {orig_size} bytes from {cfg.orig}, "
            f"read {len(contents)}"
        )
    chunk = cfg.uncompressed.read_bytes()
    if len(chunk) != second.size:
        sys.exit(
            f"Could not read {second.size} bytes from {cfg.uncompressed}, "
            f"read {len(chunk)}"
        )

    if contents[second.start : second.start + second.size] != chunk:
        sys.exit("Mismatch!")


def main() -> None:
    """Parse arguments, compile a program, compress a file, test it."""
    with tempfile.TemporaryDirectory() as dirname:
        print(f"Using temporary directory {dirname}")
        cfg = parse_args(dirname)
        do_compile(cfg)
        orig_size = cfg.orig.stat().st_size
        print(f"Original file size: {orig_size}")
        comp_size = common.do_compress(cfg, orig_size)
        second_chunk = common.read_chunks(cfg, orig_size, comp_size)
        run_program(cfg)
        compare_chunk(cfg, second_chunk, orig_size)
        print("Seems fine!")


if __name__ == "__main__":
    main()
