# core/audio_processor.py
import logging
import torch
import os
import time 

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
                 include_end_times=False, enable_auto_merge=False, cache_dir=None): # MODIFIED: Added cache_dir
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"AudioProcessor: Using device: {self.device}")

        self.progress_callback = progress_callback
        self.output_enable_diarization = enable_diarization 
        self.output_include_timestamps = include_timestamps
        self.output_include_end_times = include_end_times
        self.output_enable_auto_merge = enable_auto_merge

        self.diarization_handler = None 

        logger.info(f"AudioProcessor initializing. Output intends Diarization: {self.output_enable_diarization}, "
                    f"Timestamps: {self.output_include_timestamps}, Include End Times: {self.output_include_end_times}, "
                    f"Auto Merge: {self.output_enable_auto_merge}")

        if self.output_enable_diarization:
            huggingface_config = config.get('huggingface', {})
            use_auth_token_flag = str(huggingface_config.get('use_auth_token', 'no')).lower() == 'yes'
            hf_token_val = huggingface_config.get('hf_token') if use_auth_token_flag else None
            
            logger.info("AudioProcessor: Diarization output requested, attempting to initialize DiarizationHandler.")
            self.diarization_handler = DiarizationHandler(
                hf_token=hf_token_val,
                use_auth_token_flag=use_auth_token_flag,
                device=self.device,
                progress_callback=self.progress_callback,
                cache_dir=cache_dir # MODIFIED: Pass cache_dir
            )
            if not self.diarization_handler.is_model_loaded():
                logger.warning("AudioProcessor: DiarizationHandler initialized, but model failed to load. Diarization will be unavailable.")
        else:
            logger.info("AudioProcessor: Diarization output not requested. DiarizationHandler will not be initialized.")

        whisper_model_name = config.get('transcription', {}).get('model_name', 'large')
        self.transcription_handler = TranscriptionHandler(
            model_name=whisper_model_name,
            device=self.device,
            progress_callback=self.progress_callback,
            cache_dir=cache_dir # MODIFIED: Pass cache_dir
        )

    def _report_progress(self, message: str, percentage: int = None):
        if self.progress_callback:
            try:
                self.progress_callback(message, percentage)
            except Exception as e:
                logger.error(f"Error in AudioProcessor's progress_callback: {e}", exc_info=True)

    def are_models_loaded(self) -> bool:
        trans_loaded = self.transcription_handler.is_model_loaded()
        if not trans_loaded:
            logger.error("AudioProcessor: CRITICAL - Transcription model not loaded.")
            return False

        if self.output_enable_diarization:
            if self.diarization_handler and self.diarization_handler.is_model_loaded():
                logger.info("AudioProcessor: Diarization intended, and its model is loaded.")
            else:
                logger.warning("AudioProcessor: Diarization intended, but its model is NOT loaded. Diarization will be unavailable.")
        return True

    def _align_outputs(self, diarization_annotation, transcription_result_dict: dict, diarization_actually_performed: bool) -> list[dict]:
        if not transcription_result_dict or not transcription_result_dict.get('segments'):
            logger.error("Alignment Error: Transcription data unavailable for alignment.")
            return [{'start_time': 0, 'end_time': 0, 'speaker': 'ERROR', 'text': 'Transcription data unavailable'}]

        transcription_segments = transcription_result_dict['segments']
        aligned_segment_dicts = []
        
        diar_turns = []
        if diarization_actually_performed and diarization_annotation and diarization_annotation.labels():
            try:
                for turn, _, speaker_label in diarization_annotation.itertracks(yield_label=True):
                    diar_turns.append({'start': turn.start, 'end': turn.end, 'speaker': speaker_label})
                logger.info(f"Prepared {len(diar_turns)} diarization turns for alignment.")
            except Exception as e:
                logger.warning(f"Could not process diarization tracks for alignment: {e}. Proceeding without diarization-based speaker assignment.")
                diar_turns = [] 
        elif not diarization_actually_performed:
            logger.info("Alignment: Diarization was not performed for this run.")
        elif diarization_actually_performed and (not diarization_annotation or not diarization_annotation.labels()):
             logger.info("Alignment: Diarization was attempted, but no diarization tracks/labels found. Speakers will be UNKNOWN.")

        for t_seg in transcription_segments:
            start_time = t_seg['start'] 
            end_time = t_seg['end']     
            text_content = t_seg['text'].strip()
            
            assigned_speaker = constants.NO_SPEAKER_LABEL 
            if diarization_actually_performed and diar_turns:
                best_overlap = 0
                for d_turn in diar_turns:
                    overlap = max(0, min(end_time, d_turn['end']) - max(start_time, d_turn['start']))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        assigned_speaker = d_turn['speaker']
            
            aligned_segment_dicts.append({
                'start_time': start_time,
                'end_time': end_time,
                'speaker': assigned_speaker,
                'text': text_content
            })

        if not aligned_segment_dicts and transcription_segments:
            logger.warning("Alignment Note: Transcription processed, but alignment yielded no segment dictionaries.")
            return [{'start_time': 0, 'end_time': 0, 'speaker': 'NOTE', 'text': 'Alignment yielded no lines'}]
        return aligned_segment_dicts

    def _perform_auto_merge(self, segment_dicts: list[dict]) -> list[dict]:
        if not self.output_enable_auto_merge or not segment_dicts:
            logger.debug(f"Auto-merge skipped. OutputEnableAutoMerge: {self.output_enable_auto_merge}, Segments provided: {bool(segment_dicts)}")
            return segment_dicts

        merged_segments = []
        current_merged_segment = None
        unmergable_speaker_labels = {constants.NO_SPEAKER_LABEL} 

        for seg_dict in segment_dicts:
            if current_merged_segment is None:
                current_merged_segment = dict(seg_dict)
            else:
                can_merge = (
                    current_merged_segment['speaker'] == seg_dict['speaker'] and
                    current_merged_segment['speaker'] not in unmergable_speaker_labels
                )
                if can_merge:
                    current_merged_segment['text'] += " " + seg_dict['text']
                    current_merged_segment['end_time'] = seg_dict['end_time']
                else:
                    merged_segments.append(current_merged_segment)
                    current_merged_segment = dict(seg_dict)
        
        if current_merged_segment is not None:
            merged_segments.append(current_merged_segment)

        if len(merged_segments) < len(segment_dicts):
            logger.info(f"Auto-merge performed. Original segments: {len(segment_dicts)}, Merged segments: {len(merged_segments)}")
        else:
            logger.info(f"Auto-merge attempted, but no segments were merged. Original: {len(segment_dicts)}, Final: {len(merged_segments)}")
        return merged_segments

    def _format_segment_dictionaries_to_strings(self, segment_dicts: list[dict],
                                               include_ts_in_format: bool,
                                               include_end_ts_in_format: bool,
                                               include_speakers_in_format: bool) -> list[str]:
        output_lines = []
        if not segment_dicts:
            logger.warning("Formatting: No segment dictionaries to format.")
            return ["Error: No segment data to format."]

        for seg_dict in segment_dicts:
            parts = []
            if include_ts_in_format:
                ts_start_str = self._format_time(seg_dict['start_time'])
                if include_end_ts_in_format and seg_dict.get('end_time') is not None:
                    ts_end_str = self._format_time(seg_dict['end_time'])
                    parts.append(f"[{ts_start_str} - {ts_end_str}]")
                else:
                    parts.append(f"[{ts_start_str}]")
            
            if include_speakers_in_format and seg_dict['speaker'] != constants.NO_SPEAKER_LABEL:
                parts.append(f"{seg_dict['speaker']}:")
            
            parts.append(seg_dict['text'])
            output_lines.append(" ".join(filter(None, parts)))
        return output_lines

    def process_audio(self, audio_path: str) -> ProcessedAudioResult:
        overall_start_time = time.time()
        
        diarization_will_be_attempted = self.output_enable_diarization and \
                                        self.diarization_handler and \
                                        self.diarization_handler.is_model_loaded()

        logger.info(f"AudioProcessor: Processing file: {audio_path}. "
                    f"Output Diarization: {self.output_enable_diarization}, Diarization Will Be Attempted: {diarization_will_be_attempted}, "
                    f"Output TS: {self.output_include_timestamps}, Output EndTS: {self.output_include_end_times}, "
                    f"Output AutoMerge: {self.output_enable_auto_merge}, "
                    f"Model: {self.transcription_handler.model_name}")

        if not self.transcription_handler.is_model_loaded():
            logger.error("AudioProcessor: Cannot process audio: transcription model not loaded.")
            return ProcessedAudioResult(status=constants.STATUS_ERROR, message="Essential transcription model not loaded.")

        diarization_result_obj = None
        try:
            if diarization_will_be_attempted:
                self._report_progress("Diarization starting...", 25)
                diarization_result_obj = self.diarization_handler.diarize(audio_path)
                if diarization_result_obj is None:
                    logger.warning("Diarization process completed but returned no usable result object.")
            elif self.output_enable_diarization:
                logger.warning("Diarization was requested, but DiarizationHandler/model is not available. Skipping diarization.")
                self._report_progress("Diarization skipped (model/token issue).", 25)
            else:
                logger.info("AudioProcessor: Diarization not requested by user settings.")
                self._report_progress("Diarization skipped by user setting.", 25)

            transcription_start_progress = 50 if diarization_will_be_attempted else 25 
            self._report_progress(f"Transcription ({self.transcription_handler.model_name}) starting...", transcription_start_progress)
            transcription_output_dict = self.transcription_handler.transcribe(audio_path)

            if not transcription_output_dict or 'segments' not in transcription_output_dict:
                return ProcessedAudioResult(status=constants.STATUS_ERROR, message="Transcription failed or returned invalid data.")
            if not transcription_output_dict['segments']:
                 return ProcessedAudioResult(status=constants.STATUS_EMPTY, message="No speech detected during transcription.")

            is_plain_text_format_requested = not self.output_include_timestamps and not self.output_enable_diarization
            
            final_data_for_result: any
            is_plain_text_result = False

            if is_plain_text_format_requested:
                logger.info("Plain text output requested. Concatenating segments.")
                all_texts = [seg.get('text', '').strip() for seg in transcription_output_dict['segments']]
                final_data_for_result = " ".join(filter(None, all_texts))
                is_plain_text_result = True
                self._report_progress("Formatting as plain text...", 90)
            else:
                alignment_start_progress = 75 
                self._report_progress("Aligning outputs...", alignment_start_progress)
                
                intermediate_segment_dicts = self._align_outputs(
                    diarization_result_obj, 
                    transcription_output_dict, 
                    diarization_actually_performed=diarization_will_be_attempted
                )
                
                if intermediate_segment_dicts and isinstance(intermediate_segment_dicts[0], dict) and \
                   (intermediate_segment_dicts[0]['speaker'] == 'ERROR' or intermediate_segment_dicts[0]['speaker'] == 'NOTE'):
                    status = constants.STATUS_ERROR if intermediate_segment_dicts[0]['speaker'] == 'ERROR' else constants.STATUS_EMPTY
                    return ProcessedAudioResult(status=status, message=intermediate_segment_dicts[0]['text'])
                if not intermediate_segment_dicts:
                     return ProcessedAudioResult(status=constants.STATUS_EMPTY, message="Alignment produced no segments.")

                final_segments_to_process_further = intermediate_segment_dicts
                if self.output_enable_auto_merge and diarization_will_be_attempted:
                    logger.info("Auto-merge is enabled and diarization was attempted. Performing merge...")
                    final_segments_to_process_further = self._perform_auto_merge(intermediate_segment_dicts)
                else:
                    logger.info(f"Auto-merge skipped. OutputEnableAutoMerge: {self.output_enable_auto_merge}, DiarizationAttempted: {diarization_will_be_attempted}")

                final_data_for_result = self._format_segment_dictionaries_to_strings(
                    final_segments_to_process_further,
                    include_ts_in_format=self.output_include_timestamps,
                    include_end_ts_in_format=self.output_include_timestamps and self.output_include_end_times,
                    include_speakers_in_format=diarization_will_be_attempted
                )
                is_plain_text_result = False
                
                if not final_data_for_result or (isinstance(final_data_for_result, list) and final_data_for_result and "Error:" in final_data_for_result[0]):
                     return ProcessedAudioResult(status=constants.STATUS_EMPTY, message=final_data_for_result[0] if final_data_for_result else "Formatting produced no lines.")

            logger.info(f"Total audio processing for {audio_path} completed in {time.time() - overall_start_time:.2f}s.")
            self._report_progress("Processing complete.", 100)
            return ProcessedAudioResult(
                status=constants.STATUS_SUCCESS,
                data=final_data_for_result,
                is_plain_text_output=is_plain_text_result
            )

        except Exception as e:
            logger.exception(f"AudioProcessor: Unhandled exception during process_audio for {audio_path}")
            self._report_progress(f"Critical Error: {str(e)[:100]}...", 0)
            return ProcessedAudioResult(status=constants.STATUS_ERROR, message=f"Critical error: {str(e)}")


    def _format_time(self, seconds: float) -> str:
        if seconds is None or not isinstance(seconds, (int, float)): 
            seconds = 0.0
        seconds = max(0, seconds)
        sec_int = int(seconds)
        milliseconds = int((seconds - sec_int) * 1000)
        minutes = sec_int // 60
        sec_rem = sec_int % 60
        return f"{minutes:02d}:{sec_rem:02d}.{milliseconds:03d}"

    def save_to_txt(self, output_path: str, data_to_save: any, is_plain_text: bool):
        logger.info(f"Saving processed output to: {output_path}. Plain text: {is_plain_text}")
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                if is_plain_text:
                    if isinstance(data_to_save, str):
                        f.write(data_to_save)
                    else:
                        logger.error("save_to_txt: Expected a string for plain text, got %s", type(data_to_save))
                        f.write(str(data_to_save) if data_to_save is not None else "Error: Invalid plain text data.")
                elif isinstance(data_to_save, list):
                    for segment_line in data_to_save:
                        f.write(segment_line + '\n')
                elif data_to_save is None:
                    f.write("No transcription results or error during processing.\n")
                else:
                    logger.error("save_to_txt: Unexpected data type to save: %s", type(data_to_save))
                    f.write(str(data_to_save))

            logger.info("Output saved successfully.")
        except IOError as e:
            logger.exception(f"IOError saving to {output_path}.")
            raise
