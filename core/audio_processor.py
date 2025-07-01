# core/audio_processor.py
import logging
import torch
import os
import time 
import traceback # Import traceback module

from utils import constants
from .diarization_handler import DiarizationHandler
from .transcription_handler import TranscriptionHandler

logger = logging.getLogger(__name__)

class ProcessedAudioResult:
    def __init__(self, status, data=None, message=None, is_plain_text_output=False):
        self.status = status 
        self.data = data
        self.message = message
        self.is_plain_text_output = is_plain_text_output

class AudioProcessor:
    def __init__(self, config: dict, progress_callback=None, 
                 enable_diarization=True, include_timestamps=True, 
                 include_end_times=False, enable_auto_merge=False, cache_dir=None):
        
        # --- AGGRESSIVE DIAGNOSTIC WRAPPER ---
        # The entire initialization is wrapped to catch any model loading errors.
        try:
            logger = logging.getLogger(__name__)
            logger.info("--- AudioProcessor Initialization Started ---")
            
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"AudioProcessor: Using device: {self.device}")

            self.progress_callback = progress_callback
            self.output_enable_diarization = enable_diarization 
            self.output_include_timestamps = include_timestamps
            self.output_include_end_times = include_end_times
            self.output_enable_auto_merge = enable_auto_merge

            self.diarization_handler = None 

            if self.output_enable_diarization:
                logger.info("Attempting to initialize DiarizationHandler...")
                huggingface_config = config.get('huggingface', {})
                use_auth_token_flag = str(huggingface_config.get('use_auth_token', 'no')).lower() == 'yes'
                hf_token_val = huggingface_config.get('hf_token') if use_auth_token_flag else None
                self.diarization_handler = DiarizationHandler(
                    hf_token=hf_token_val, use_auth_token_flag=use_auth_token_flag, device=self.device,
                    progress_callback=self.progress_callback, cache_dir=cache_dir
                )
                logger.info("DiarizationHandler initialized successfully.")
            else:
                logger.info("AudioProcessor: Diarization output not requested.")

            logger.info("Attempting to initialize TranscriptionHandler...")
            whisper_model_name = config.get('transcription', {}).get('model_name', 'large')
            self.transcription_handler = TranscriptionHandler(
                model_name=whisper_model_name, device=self.device,
                progress_callback=self.progress_callback, cache_dir=cache_dir
            )
            logger.info("TranscriptionHandler initialized successfully.")
            
            logger.info("--- AudioProcessor Initialization Finished ---")
            
            self._initialization_error = None

        except Exception as e:
            # If ANY error happens during init, store the full traceback.
            full_traceback = traceback.format_exc()
            logger.error(f"CRITICAL FAILURE during AudioProcessor initialization:\n{full_traceback}")
            self._initialization_error = full_traceback
        # --- END DIAGNOSTIC WRAPPER ---
        
    def process_audio(self, audio_path: str) -> ProcessedAudioResult:
        # --- AGGRESSIVE DIAGNOSTIC CHECK ---
        # If the __init__ failed, immediately return the stored traceback.
        if self._initialization_error:
            return ProcessedAudioResult(status=constants.STATUS_ERROR, message=self._initialization_error)
        # --- END DIAGNOSTIC CHECK ---

        logger = logging.getLogger(__name__)
        # (The rest of the process_audio function is standard)
        overall_start_time = time.time()
        
        diarization_will_be_attempted = self.output_enable_diarization and self.diarization_handler and self.diarization_handler.is_model_loaded()
        logger.info(f"AudioProcessor: Processing file: {audio_path}. Diarization Will Be Attempted: {diarization_will_be_attempted}")

        if not self.transcription_handler.is_model_loaded():
            return ProcessedAudioResult(status=constants.STATUS_ERROR, message="Essential transcription model not loaded.")

        try:
            diarization_result_obj = None
            if diarization_will_be_attempted:
                self.progress_callback("Diarization starting...", 25) if self.progress_callback else None
                diarization_result_obj = self.diarization_handler.diarize(audio_path)
            
            self.progress_callback(f"Transcription starting...", 50) if self.progress_callback else None
            transcription_output_dict = self.transcription_handler.transcribe(audio_path)

            if not transcription_output_dict or 'segments' not in transcription_output_dict or not transcription_output_dict['segments']:
                return ProcessedAudioResult(status=constants.STATUS_EMPTY, message="No speech detected.")

            is_plain_text = not self.output_include_timestamps and not self.output_enable_diarization
            if is_plain_text:
                return ProcessedAudioResult(status=constants.STATUS_SUCCESS, data=" ".join([s['text'].strip() for s in transcription_output_dict['segments']]), is_plain_text_output=True)

            aligned_segments = self._align_outputs(diarization_result_obj, transcription_output_dict, diarization_will_be_attempted)
            
            if self.output_enable_auto_merge:
                aligned_segments = self._perform_auto_merge(aligned_segments)

            final_text = self._format_segment_dictionaries_to_strings(aligned_segments, self.output_include_timestamps, self.output_include_end_times, diarization_will_be_attempted)
            
            logger.info(f"Processing for {audio_path} completed in {time.time() - overall_start_time:.2f}s.")
            return ProcessedAudioResult(status=constants.STATUS_SUCCESS, data=final_text, is_plain_text_output=False)

        except Exception:
             # Capture the full traceback if anything fails during the main processing.
            full_traceback = traceback.format_exc()
            logger.error(f"CRITICAL FAILURE during process_audio:\n{full_traceback}")
            return ProcessedAudioResult(status=constants.STATUS_ERROR, message=full_traceback)

    # --- Other methods are standard and don't need the heavy logging ---

    def _align_outputs(self, diarization_annotation, transcription_result_dict: dict, diarization_actually_performed: bool) -> list[dict]:
        if not transcription_result_dict or not transcription_result_dict.get('segments'): return []
        transcription_segments = transcription_result_dict['segments']; aligned_segment_dicts = []
        diar_turns = []
        if diarization_actually_performed and diarization_annotation:
            for turn, _, speaker_label in diarization_annotation.itertracks(yield_label=True):
                diar_turns.append({'start': turn.start, 'end': turn.end, 'speaker': speaker_label})
        for t_seg in transcription_segments:
            start_time, end_time, text_content = t_seg['start'], t_seg['end'], t_seg['text'].strip()
            assigned_speaker = constants.NO_SPEAKER_LABEL
            if diar_turns:
                best_overlap = 0
                for d_turn in diar_turns:
                    overlap = max(0, min(end_time, d_turn['end']) - max(start_time, d_turn['start']))
                    if overlap > best_overlap:
                        best_overlap, assigned_speaker = overlap, d_turn['speaker']
            aligned_segment_dicts.append({'start_time': start_time, 'end_time': end_time, 'speaker': assigned_speaker, 'text': text_content})
        return aligned_segment_dicts

    def _perform_auto_merge(self, segment_dicts: list[dict]) -> list[dict]:
        if not segment_dicts: return []
        merged_segments, current_merged_segment = [], None
        for seg_dict in segment_dicts:
            if current_merged_segment is None: current_merged_segment = dict(seg_dict)
            else:
                can_merge = current_merged_segment['speaker'] == seg_dict['speaker'] and current_merged_segment['speaker'] != constants.NO_SPEAKER_LABEL
                if can_merge: current_merged_segment['text'] += " " + seg_dict['text']; current_merged_segment['end_time'] = seg_dict['end_time']
                else: merged_segments.append(current_merged_segment); current_merged_segment = dict(seg_dict)
        if current_merged_segment is not None: merged_segments.append(current_merged_segment)
        return merged_segments

    def _format_time(self, seconds: float) -> str:
        if seconds is None: return "00:00.000"
        m, s = divmod(abs(seconds), 60); return f"{int(m):02d}:{s:06.3f}"

    def _format_segment_dictionaries_to_strings(self, segment_dicts, include_ts, include_end_ts, include_speakers) -> list[str]:
        lines = []
        for seg_dict in segment_dicts:
            parts = []
            if include_ts:
                ts_start = self._format_time(seg_dict['start_time'])
                if include_end_ts and seg_dict.get('end_time') is not None: parts.append(f"[{ts_start} - {self._format_time(seg_dict['end_time'])}]")
                else: parts.append(f"[{ts_start}]")
            if include_speakers and seg_dict['speaker'] != constants.NO_SPEAKER_LABEL: parts.append(f"{seg_dict['speaker']}:")
            parts.append(seg_dict['text']); lines.append(" ".join(filter(None, parts)))
        return lines

    @staticmethod
    def save_to_txt(output_path, data, is_plain_text):
        with open(output_path, 'w', encoding='utf-8') as f:
            if is_plain_text: f.write(str(data))
            else: f.write('\n'.join(data))