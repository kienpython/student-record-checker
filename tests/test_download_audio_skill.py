from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from src.skills.download_audio_skill import DownloadAudioSkill


class DownloadAudioSkillTests(unittest.TestCase):
    def test_recognizes_youtube_links_with_and_without_scheme(self):
        with TemporaryDirectory() as directory:
            skill = DownloadAudioSkill(
                config=SimpleNamespace(CACHE_AUDIOS=Path(directory))
            )
            self.assertTrue(
                skill.is_youtube("https://www.youtube.com/watch?v=test")
            )
            self.assertTrue(skill.is_youtube("youtube.com/watch?v=test"))
            self.assertTrue(skill.is_youtube("youtu.be/test"))
            self.assertFalse(skill.is_youtube("drive.google.com/test"))

    def test_returns_cached_audio_without_downloading(self):
        with TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            record_dir = cache_dir / "rec1"
            record_dir.mkdir()
            audio = record_dir / "audio.wav"
            audio.write_bytes(b"cached")
            skill = DownloadAudioSkill(
                config=SimpleNamespace(CACHE_AUDIOS=cache_dir)
            )

            result = skill.download("youtube.com/watch?v=test", "rec1")

            self.assertEqual(result, audio)


if __name__ == "__main__":
    unittest.main()
