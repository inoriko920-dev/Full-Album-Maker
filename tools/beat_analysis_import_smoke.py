from full_album_maker.audio_analysis_contract import SAMPLE_RATE, HOP_LENGTH, TICKS_PER_FRAME
from full_album_maker.audio_analysis_fingerprint import AnalyzerSettings
from full_album_maker.audio_analysis_cache import AudioAnalysisCache
from full_album_maker.audio_analysis_service import AudioAnalysisService

assert SAMPLE_RATE == 24000
assert HOP_LENGTH == 512
assert TICKS_PER_FRAME == 5120
assert len(AnalyzerSettings().signature()) == 64
print("STEP04_AUDIO_ANALYSIS_IMPORT_SMOKE_OK")
