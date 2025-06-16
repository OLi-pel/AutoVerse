# core/audio_processor.py (With Stream Capture)

import logging
import os
import time

from .transcription_handler import TranscriptionHandler
from .diarization_handler import DiarizationHandler
from utils import constants
from utils.streams import TqdmSignalStream

logger = logging.getLogger(__name__)

class ProcessedAudioResult:
    def __init__(self, status: str, message: str, data: list | str | None = None, is_plain_text_output: bool = False):
        self.status = status
        self.message = message
        self.data = data
        self.is_plain_text_output = is_plain_text_output

class AudioProcessor:
    def __init__(self, config: dict, progress_callback=None,
                 enable_diarization: bool = False, include_timestamps: bool = True,
                 include_end_times: bool = False, enable_auto_merge: bool = False, cache_dir: str = None):
        
        self.device = "cpu"
        self.progress_callback = progress_callback
        self.output_enable_diarization = enable_diarization
        self.output_include_timestamps = include_timestamps
        self.output_include_end_times = include_end_times
        self.output_enable_auto_merge = enable_auto_merge
        
        logger.info(f"AudioProcessor initializing. Diarization: {self.output_enable_diarization}, Timestamps: {self.output_include_timestamps}")

        self.diarization_handler = None
        if self.output_enable_diarization:
            try:
                hf_config = config.get('huggingface', {})
                use_auth = hf_config.get('use_auth_token', 'no').lower() == 'yes'
                hf_token = hf_config.get('hf_token')
                if use_auth and hf_token:
                    # Corrected keyword from `use_auth_token` to `auth_token`
                    self.diarization_handler = DiarizationHandler(auth_token=hf_token, cache_dir=cache_dir)
                else:
                    logger.warning("Diarization requested but no Hugging Face token provided. Disabling.")
                    self.output_enable_diarization = False
            except Exception as e:
                logger.error(f"Failed to initialize DiarizationHandler: {e}", exc_info=True)
                self.output_enable_diarization = False

        self.transcription_handler = TranscriptionHandler(
            model_name=config.get('transcription', {}).get('model_name', 'large'),
            device=self.device,
            cache_dir=cache_dir
        )
        
    def are_models_loaded(self) -> bool:
        if not self.transcription_handler or not self.transcription_handler.is_model_loaded():
            return False
        if self.output_enable_diarization and (not self.diarization_handler or not self.diarization_handler.is_model_loaded()):
            return False
        return True

    def process_audio(self, audio_path: str) -> ProcessedAudioResult:
        start_time = time.time()
        diarization_was_attempted = self.output_enable_diarization and self.diarization_handler and self.diarization_handler.is_model_loaded()
        
        diarization_turns = None
        if diarization_was_attempted:
            if self.progress_callback: self.progress_callback("Diarizing speakers...", 5)
            diarization_turns = self.diarization_handler.diarize(audio_path)
            if self.progress_callback: self.progress_callback("Diarization complete.", 20)
        else:
            # If not attempting diarization, set progress to a baseline starting point
            if self.progress_callback: self.progress_callback("Starting transcription...", 5)
        
        try:
            if self.progress_callback: self.progress_callback("Transcribing...", 25)
            
            # Create the stream object to capture progress from tqdm
            tqdm_stream = TqdmSignalStream()
            
            if self.progress_callback:
                # Connect the stream's emitter signal to our main progress callback
                # This maps whisper's 0-100% to our overall progress range.
                # If diarization happened, transcription is 25%-95% of the work (70% range).
                # If no diarization, transcription is 5%-95% of the work (90% range).
                progress_start = 25 if diarization_was_attempted else 5
                progress_range = 70 if diarization_was_attempted else 90
                
                tqdm_stream.emitter.progress_updated.connect(
                    lambda percentage: self.progress_callback(f"Transcribing... {percentage}%", progress_start + int(percentage * (progress_range / 100.0)))
                )

            transcription_result = self.transcription_handler.transcribe(audio_path, tqdm_stream=tqdm_stream)
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path}: {e}", exc_info=True)
            return ProcessedAudioResult(constants.STATUS_ERROR, f"Transcription failed: {e}")
            
        if not transcription_result:
            return ProcessedAudioResult(constants.STATUS_EMPTY, "Transcription returned no result.")
            
        if self.progress_callback: self.progress_callback("Aligning results...", 95)
        aligned_segments = self._align_outputs(transcription_result, diarization_turns)
        
        if not aligned_segments:
            return ProcessedAudioResult(constants.STATUS_EMPTY, "Could not produce any segments after alignment.")
        
        if self.output_enable_auto_merge and diarization_was_attempted:
            final_segments = self._perform_auto_merge(aligned_segments)
        else:
            final_segments = aligned_segments

        if self.progress_callback: self.progress_callback("Formatting output...", 98)
        formatted_output = self._format_output(final_segments)
        
        if self.progress_callback: self.progress_callback("Processing complete!", 100)
        
        end_time = time.time()
        logger.info(f"Total audio processing for {os.path.basename(audio_path)} completed in {end_time - start_time:.2f}s.")
        
        return ProcessedAudioResult(constants.STATUS_SUCCESS, "Processing successful.", formatted_output, is_plain_text_output=False)

    def _align_outputs(self, transcription_result: list, diarization_result: list | None) -> list:
        if not diarization_result:
            logger.info("Alignment: Diarization was not performed for this run.")
            aligned_segments = []
            for seg in transcription_result:
                aligned_segments.append({
                    "start": seg['start'], "end": seg['end'],
                    "text": seg['text'].strip(), "speaker": constants.NO_SPEAKER_LABEL
                })
            return aligned_segments
        
        logger.info(f"Prepared {len(diarization_result)} diarization turns for alignment.")
        from whisper_timestamp_plus import assign_word_speakers
        
        try:
            assign_word_speakers(diarization_result, transcription_result)
            final_segments, current_segment = [], None
            if transcription_result and 'words' in transcription_result[0]:
                for seg in transcription_result:
                    for word in seg['words']:
                        speaker = word.get('speaker', constants.NO_SPEAKER_LABEL)
                        if current_segment is None:
                            current_segment = {'start': word['start'], 'end': word['end'], 'text': word['word'], 'speaker': speaker}
                        elif current_segment['speaker'] != speaker:
                            final_segments.append(current_segment)
                            current_segment = {'start': word['start'], 'end': word['end'], 'text': word['word'], 'speaker': speaker}
                        else:
                            current_segment['text'] += ' ' + word['word']
                            current_segment['end'] = word['end']
                if current_segment: final_segments.append(current_segment)
            else:
                 logger.warning("Word-level timestamps not found in transcription result. Cannot perform speaker alignment.")
                 return self._align_outputs(transcription_result, None)
            return final_segments
        except Exception as e:
            logger.error(f"Error during word-level speaker assignment: {e}", exc_info=True)
            return self._fallback_segment_alignment(transcription_result, diarization_result)

    def _fallback_segment_alignment(self, transcription_result, diarization_result):
        logger.info("Performing fallback segment-level alignment.")
        return self._align_outputs(transcription_result, None)

    def _perform_auto_merge(self, segments: list) -> list:
        if not segments: return []
        merged_segments = [segments[0]]
        for i in range(1, len(segments)):
            if segments[i]['speaker'] == merged_segments[-1]['speaker'] and segments[i]['speaker'] != constants.NO_SPEAKER_LABEL:
                merged_segments[-1]['end'] = segments[i]['end']
                merged_segments[-1]['text'] += ' ' + segments[i]['text']
            else:
                merged_segments.append(segments[i])
        logger.info(f"Auto-merge performed. Original: {len(segments)}, Merged: {len(merged_segments)}")
        return merged_segments

    def _format_output(self, segments: list) -> list[str]:
        lines = []
        for seg in segments:
            speaker_str = f"{seg['speaker']}: " if seg['speaker'] != constants.NO_SPEAKER_LABEL else ""
            ts_str = ""
            if self.output_include_timestamps:
                start = self.seconds_to_time_str(seg['start'])
                end = self.seconds_to_time_str(seg['end']) if self.output_include_end_times and 'end' in seg and seg['end'] is not None else None
                ts_str = f"[{start} - {end}] " if end else f"[{start}] "
            lines.append(f"{ts_str}{speaker_str}{seg['text']}")
        return lines

    def save_to_txt(self, output_path: str, data: list, is_plain_text: bool):
        with open(output_path, 'w', encoding='utf-8') as f:
            if is_plain_text and isinstance(data, str): f.write(data)
            else:
                for line in data: f.write(line + '\n')

    def seconds_to_time_str(self, seconds: float) -> str:
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0.0
        m, s = divmod(seconds, 60)
        return f"{int(m):02d}:{int(s):02d}.{int((s-int(s))*1000):03d}"