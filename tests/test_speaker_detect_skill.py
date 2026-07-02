from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
import wave

from src.skills.speaker_detect_skill import SpeakerDetectSkill


class FakeDiarization:
    def labels(self):
        return ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]


class SpeakerDetectSkillTests(unittest.TestCase):
    def test_counts_and_caches_speakers(self):
        with TemporaryDirectory() as directory:
            audio = Path(directory) / "audio.wav"
            with wave.open(str(audio), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00" * 160)
            pipeline_calls = []

            def pipeline(audio_input):
                pipeline_calls.append(audio_input)
                return FakeDiarization()

            config = SimpleNamespace(
                PYANNOTE_TOKEN="hf_test",
                PYANNOTE_MODEL="pyannote/test",
                CACHE_AUDIOS=Path(directory),
                CACHE_DIR=Path(directory),
            )
            skill = SpeakerDetectSkill(config=config, pipeline=pipeline)

            first = skill.detect_speakers(audio, "rec1")
            second = skill.detect_speakers(audio, "rec1")

            self.assertEqual(first, 3)
            self.assertEqual(second, 3)
            self.assertEqual(len(pipeline_calls), 1)
            self.assertIn("waveform", pipeline_calls[0])
            self.assertEqual(pipeline_calls[0]["sample_rate"], 16000)


if __name__ == "__main__":
    unittest.main()
