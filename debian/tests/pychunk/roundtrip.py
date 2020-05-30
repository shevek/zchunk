"""A very simple test for the command-line zchunk tools."""

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

    tempd: pathlib.Path

    uncompressed: pathlib.Path
    recompressed: pathlib.Path


def parse_args(dirname: str) -> Config:
    """Parse the command-line arguments, deduce some things."""
    parser = common.base_parser("roundtrip")

    args = parser.parse_args()
    bindir = pathlib.Path(args.bindir).absolute()
    if not bindir.is_dir():
        sys.exit(f"Not a directory: {bindir}")
    zck = bindir / "zck"
    if not zck.is_file() or not os.access(zck, os.X_OK):
        sys.exit(f"Not an executable file: {zck}")

    tempd = pathlib.Path(dirname).absolute()
    return Config(
        tempd=tempd,
        bindir=bindir,
        env=common.get_runenv(),
        orig=pathlib.Path(args.filename).absolute(),
        compressed=tempd / "words.txt.zck",
        uncompressed=tempd / "un/words.txt",
        recompressed=tempd / "re/words.txt.zck",
    )


def do_uncompress(cfg: Config, orig_size: int) -> None:
    """Uncompress and compare."""
    # OK, so unzck's behavior is... weird.
    cfg.uncompressed.parent.mkdir(mode=0o755)

    print(f"Extracting {cfg.compressed} to {cfg.uncompressed}")
    if cfg.uncompressed.exists():
        sys.exit(f"Did not expect {cfg.uncompressed} to exist")
    subprocess.check_call(
        [cfg.bindir / "unzck", "--", cfg.compressed],
        shell=False,
        env=cfg.env,
        cwd=cfg.uncompressed.parent,
    )
    if not cfg.uncompressed.is_file():
        subprocess.check_call(["ls", "-lt", "--", cfg.tempd], shell=False)
        sys.exit(f"unzck did not create the {cfg.uncompressed} file")

    new_size = cfg.uncompressed.stat().st_size
    print(f"Uncompressed size {new_size}")
    if new_size != orig_size:
        sys.exit(f"Uncompressed size {new_size} != original size {orig_size}")

    print(f"Comparing {cfg.orig} to {cfg.uncompressed}")
    subprocess.check_call(
        ["cmp", "--", cfg.orig, cfg.uncompressed], shell=False, env=cfg.env
    )


def do_recompress(cfg: Config, comp_size: int) -> None:
    """Recompress the file and compare."""
    # OK, so zck's behavior is also weird...
    cfg.recompressed.parent.mkdir(mode=0o755)

    print(f"Recompressing {cfg.uncompressed} to {cfg.recompressed}")
    if cfg.recompressed.exists():
        sys.exit(f"Did not expect {cfg.recompressed} to exist")
    subprocess.check_call(
        [cfg.bindir / "zck", "--", cfg.uncompressed],
        shell=False,
        env=cfg.env,
        cwd=cfg.recompressed.parent,
    )
    if not cfg.recompressed.is_file():
        sys.exit(f"zck did not create the {cfg.recompressed} file")

    new_size = cfg.recompressed.stat().st_size
    print(f"Recompressed size {new_size}")
    if new_size != comp_size:
        sys.exit(
            f"Recompressed size {new_size} != compressed size {comp_size}"
        )

    print(f"Comparing {cfg.compressed} to {cfg.recompressed}")
    subprocess.check_call(
        ["cmp", "--", cfg.compressed, cfg.recompressed],
        shell=False,
        env=cfg.env,
    )


def main() -> None:
    """Create a temporary directory, compress a file, analyze it."""
    with tempfile.TemporaryDirectory() as dirname:
        print(f"Using temporary directory {dirname}")
        cfg = parse_args(dirname)
        orig_size = cfg.orig.stat().st_size
        print(f"{cfg.orig} is {orig_size} bytes long")

        comp_size = common.do_compress(cfg, orig_size)
        common.read_chunks(cfg, orig_size, comp_size)
        do_uncompress(cfg, orig_size)
        do_recompress(cfg, comp_size)
        print("Seems fine!")


if __name__ == "__main__":
    main()
