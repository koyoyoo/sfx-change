import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sfx_change.cli import (
    ConversionJob,
    build_jobs,
    build_jobs_for_items,
    convert_one,
    find_ogg_files,
    find_ogg_items,
)


class CliTests(unittest.TestCase):
    def test_find_ogg_files_recursively_and_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "nested"
            nested.mkdir()
            expected = [root / "a.ogg", nested / "b.OGG"]
            for path in expected:
                path.write_bytes(b"ogg")
            (nested / "ignore.mp3").write_bytes(b"mp3")

            self.assertEqual(find_ogg_files(root), sorted(expected))

    def test_build_jobs_mirrors_directory_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            output = Path(tmp) / "output"
            source = root / "voice" / "hit.ogg"

            jobs = build_jobs([source], root, output)

            self.assertEqual(jobs[0].target, output / "voice" / "hit.wav")

    def test_build_jobs_flat_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            output = Path(tmp) / "output"
            source = root / "voice" / "hit.ogg"

            jobs = build_jobs([source], root, output, flat=True)

            self.assertEqual(jobs[0].target, output / "hit.wav")

    def test_build_jobs_rejects_duplicate_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            output = Path(tmp) / "output"
            sources = [root / "a" / "hit.ogg", root / "b" / "hit.ogg"]

            with self.assertRaisesRegex(ValueError, "同一个 WAV"):
                build_jobs(sources, root, output, flat=True)

    def test_find_ogg_items_accepts_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.ogg"
            second = root / "second.OGG"
            first.write_bytes(b"ogg")
            second.write_bytes(b"ogg")

            items = find_ogg_items([first, second, first])

            self.assertEqual([item.source for item in items], [first, second])
            self.assertTrue(all(item.root is None for item in items))

    def test_build_jobs_for_items_prefixes_multiple_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_root = root / "one"
            second_root = root / "two"
            first_root.mkdir()
            second_root.mkdir()
            first = first_root / "hit.ogg"
            second = second_root / "hit.ogg"
            first.write_bytes(b"ogg")
            second.write_bytes(b"ogg")
            output = root / "output"
            items = find_ogg_items([first_root, second_root])

            jobs = build_jobs_for_items(items, output)

            self.assertEqual(
                {job.target for job in jobs},
                {output / "one" / "hit.wav", output / "two" / "hit.wav"},
            )

    def test_convert_one_invokes_ffmpeg_with_wav_pcm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "in.ogg"
            target = root / "out.wav"
            source.write_bytes(b"ogg")
            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

            with mock.patch("sfx_change.cli.subprocess.run", return_value=completed) as run:
                result = convert_one(
                    ConversionJob(source, target),
                    ffmpeg="ffmpeg",
                    overwrite=False,
                    sample_rate=48000,
                    channels=2,
                )

            self.assertTrue(result.ok)
            command = run.call_args.args[0]
            self.assertIn("pcm_s16le", command)
            self.assertIn("48000", command)
            self.assertIn("2", command)

    def test_convert_one_skips_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "in.ogg"
            target = root / "out.wav"
            source.write_bytes(b"ogg")
            target.write_bytes(b"wav")

            with mock.patch("sfx_change.cli.subprocess.run") as run:
                result = convert_one(
                    ConversionJob(source, target),
                    ffmpeg="ffmpeg",
                    overwrite=False,
                    sample_rate=None,
                    channels=None,
                )

            self.assertTrue(result.ok)
            self.assertTrue(result.skipped)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
