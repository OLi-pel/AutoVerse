# core/correction_window_logic.py
import logging
import re
import uuid
from tkinter import messagebox
try:
    from utils import constants
except ImportError:
    import sys, os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path: sys.path.insert(0, project_root)
    from utils import constants

logger = logging.getLogger(__name__)

class SegmentManager:
    def __init__(self, parent_window_for_dialogs=None):
        self.segments = []; self.speaker_map = {}; self.unique_speaker_labels = set(); self.parent_window = parent_window_for_dialogs
        self.pattern_start_end_ts_speaker = re.compile(r"^\[(\d{2}:\d{2}\.\d{3})\s*-\s*(\d{2}:\d{2}\.\d{3})\]\s*([^:]+?):\s*(.*)$")
        self.pattern_start_end_ts_only = re.compile(r"^\[(\d{2}:\d{2}\.\d{3})\s*-\s*(\d{2}:\d{2}\.\d{3})\]\s*(.*)$")
        self.pattern_start_ts_speaker = re.compile(r"^\[(\d{2}:\d{2}\.\d{3})\]\s*([^:]+?):\s*(.*)$")
        self.pattern_start_ts_only = re.compile(r"^\[(\d{2}:\d{2}\.\d{3})\]\s*(.*)$")
        self.pattern_speaker_only = re.compile(r"^\s*([^:]+?):\s*(.*)$")
        logger.info("SegmentManager initialized.")

    def _generate_unique_segment_id(self) -> str: return f"seg_{uuid.uuid4().hex[:8]}"
    def time_str_to_seconds(self, time_str: str) -> float | None:
        if not time_str or not isinstance(time_str, str): return None
        try:
            parts = time_str.split(':')
            if len(parts) == 3: h, m, s_ms = parts; s, ms = s_ms.split('.'); return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
            elif len(parts) == 2: m, s_ms = parts; s, ms = s_ms.split('.'); return int(m) * 60 + int(s) + int(ms) / 1000.0
            return None
        except ValueError: return None
    def seconds_to_time_str(self, total_seconds: float | None, force_MM_SS: bool = True) -> str:
        if total_seconds is None: return "00:00.000"
        if not isinstance(total_seconds, (int, float)) or total_seconds < 0: total_seconds = 0.0
        abs_seconds = abs(total_seconds); h = 0
        if not force_MM_SS: h = int(abs_seconds // 3600); abs_seconds %= 3600
        m = int(abs_seconds // 60); s_float = abs_seconds % 60; s_int = int(s_float); ms = int((s_float - s_int) * 1000)
        sign = "-" if total_seconds < 0 else ""
        if not force_MM_SS and h > 0: return f"{sign}{h:02d}:{m:02d}:{s_int:02d}.{ms:03d}"
        if force_MM_SS and h > 0: m += h * 60
        return f"{sign}{m:02d}:{s_int:02d}.{ms:03d}"

    def parse_transcription_lines(self, text_lines: list[str]) -> bool:
        self.clear_segments(); malformed_count = 0
        for i, line_raw in enumerate(text_lines):
            line = line_raw.strip()
            if not line: continue
            start_s, end_s = 0.0, None; speaker = constants.NO_SPEAKER_LABEL; text = line; has_ts, has_explicit_end = False, False
            m_se_spk = self.pattern_start_end_ts_speaker.match(line); m_se_only = self.pattern_start_end_ts_only.match(line);
            m_s_spk = self.pattern_start_ts_speaker.match(line); m_s_only = self.pattern_start_ts_only.match(line); m_spk_only = self.pattern_speaker_only.match(line)
            parsed_ok = False
            if m_se_spk:
                s, e, spk, txt = m_se_spk.groups(); ps, pe = self.time_str_to_seconds(s), self.time_str_to_seconds(e)
                if ps is not None and pe is not None: start_s, end_s, speaker, text, has_ts, has_explicit_end, parsed_ok = ps, pe, spk.strip(), txt.strip(), True, True, True
            elif m_se_only:
                s, e, txt = m_se_only.groups(); ps, pe = self.time_str_to_seconds(s), self.time_str_to_seconds(e)
                if ps is not None and pe is not None: start_s, end_s, text, has_ts, has_explicit_end, parsed_ok = ps, pe, txt.strip(), True, True, True
            elif m_s_spk:
                s, spk, txt = m_s_spk.groups(); ps = self.time_str_to_seconds(s)
                if ps is not None: start_s, speaker, text, has_ts, parsed_ok = ps, spk.strip(), txt.strip(), True, True
            elif m_s_only:
                s, txt = m_s_only.groups(); ps = self.time_str_to_seconds(s)
                if ps is not None: start_s, text, has_ts, parsed_ok = ps, txt.strip(), True, True
            elif m_spk_only:
                spk, txt = m_spk_only.groups(); speaker, text, parsed_ok = spk.strip(), txt.strip(), True
            else: text = line; parsed_ok = True
            
            if not text.strip(): text = constants.EMPTY_SEGMENT_PLACEHOLDER

            if not parsed_ok: malformed_count += 1
            seg_id = self._generate_unique_segment_id()
            self.segments.append({"id": seg_id, "start_time": start_s, "end_time": end_s, "speaker_raw": speaker, "text": text, "text_tag_id": f"text_content_{seg_id}", "timestamp_tag_id": f"ts_content_{seg_id}", "has_timestamps": has_ts, "has_explicit_end_time": has_explicit_end})
            if speaker != constants.NO_SPEAKER_LABEL: self.unique_speaker_labels.add(speaker)
        if malformed_count > 0 and self.parent_window: messagebox.showwarning("Parsing Issues", f"{malformed_count} lines had issues.", parent=self.parent_window)
        return True
        
    def clear_segments(self): self.segments.clear(); self.speaker_map.clear(); self.unique_speaker_labels.clear()
    def get_segment_by_id(self, segment_id: str) -> dict | None: return next((s for s in self.segments if s["id"] == segment_id), None)
    def get_segment_index(self, segment_id: str) -> int: return next((i for i, s in enumerate(self.segments) if s["id"] == segment_id), -1)
    
    def update_segment_speaker(self, segment_id: str, new_speaker_raw: str):
        segment = self.get_segment_by_id(segment_id)
        if segment:
            segment["speaker_raw"] = new_speaker_raw
            if new_speaker_raw and new_speaker_raw != constants.NO_SPEAKER_LABEL:
                self.unique_speaker_labels.add(new_speaker_raw)

    def update_segment_timestamps(self, segment_id: str, new_start_time_str: str | None, new_end_time_str: str | None) -> tuple[bool, str | None]:
        segment = self.get_segment_by_id(segment_id);
        if not segment: return False, "Segment not found."
        parsed_start_time = self.time_str_to_seconds(new_start_time_str) if new_start_time_str else None
        parsed_end_time = self.time_str_to_seconds(new_end_time_str) if new_end_time_str else None
        segment["start_time"] = parsed_start_time if parsed_start_time is not None else 0.0
        segment["end_time"] = parsed_end_time
        segment["has_timestamps"] = parsed_start_time is not None
        segment["has_explicit_end_time"] = parsed_start_time is not None and parsed_end_time is not None
        return True, None

    def remove_segment_timestamp(self, segment_id: str) -> bool:
        segment = self.get_segment_by_id(segment_id)
        if not segment: return False
        segment['has_timestamps'] = False
        segment['has_explicit_end_time'] = False
        segment['start_time'] = 0.0
        segment['end_time'] = None
        return True

    def clear_segment_text(self, segment_id: str) -> bool:
        segment = self.get_segment_by_id(segment_id)
        if not segment: return False
        segment['text'] = constants.EMPTY_SEGMENT_PLACEHOLDER
        return True

    def update_segment_from_full_line(self, segment_id: str, full_line_text: str):
        segment = self.get_segment_by_id(segment_id)
        if not segment: return
        line = full_line_text.strip(); text_content = line; prefix_parts = []
        
        # Guard against saving the placeholder directly as if it's user input
        if line == constants.EMPTY_SEGMENT_PLACEHOLDER:
            segment['text'] = constants.EMPTY_SEGMENT_PLACEHOLDER
            return
            
        if segment.get("has_timestamps"): prefix_parts.append(f"[{self.seconds_to_time_str(segment.get('start_time', 0))}]")
        speaker_label = segment.get("speaker_raw")
        if speaker_label and speaker_label != constants.NO_SPEAKER_LABEL: 
            display_name = self.speaker_map.get(speaker_label, speaker_label)
            prefix_parts.append(f"{display_name}:")

        current_prefix = " ".join(filter(None, prefix_parts))
        
        # Check if the text actually starts with the current prefix before stripping it.
        if current_prefix and full_line_text.startswith(current_prefix):
             text_content = full_line_text[len(current_prefix):].lstrip()
        else: # Handle cases where the prefix was not found (e.g., manual deletion by user)
            text_content = full_line_text
            
        segment['text'] = text_content if text_content else constants.EMPTY_SEGMENT_PLACEHOLDER

    def add_segment(self, segment_data: dict, reference_segment_id: str | None, position: str) -> str | None:
        new_id = self._generate_unique_segment_id()
        final_segment_data = {
            "id": new_id, 
            "text": segment_data.get("text", constants.EMPTY_SEGMENT_PLACEHOLDER), 
            "speaker_raw": segment_data.get("speaker_raw", constants.NO_SPEAKER_LABEL), 
            "start_time": segment_data.get("start_time", 0.0), 
            "end_time": segment_data.get("end_time"), 
            "has_timestamps": segment_data.get("has_timestamps", False), 
            "has_explicit_end_time": segment_data.get("has_explicit_end_time", False), 
            "text_tag_id": f"text_content_{new_id}", 
            "timestamp_tag_id": f"ts_content_{new_id}"
        }
        if reference_segment_id: ref_index = self.get_segment_index(reference_segment_id); insert_at_index = ref_index + 1 if position == "below" else ref_index
        else: insert_at_index = len(self.segments)
        self.segments.insert(insert_at_index, final_segment_data)
        if final_segment_data["speaker_raw"] != constants.NO_SPEAKER_LABEL: self.unique_speaker_labels.add(final_segment_data["speaker_raw"])
        return new_id
        
    def split_segment(self, original_segment_id: str, text_split_index: int, new_segment_properties: dict) -> bool:
        original_segment = self.get_segment_by_id(original_segment_id)
        if not original_segment: return False
        current_text = original_segment["text"]
        text_for_original = current_text[:text_split_index].strip(); text_for_new = current_text[text_split_index:].strip()
        
        original_segment["text"] = text_for_original if text_for_original else constants.EMPTY_SEGMENT_PLACEHOLDER
        
        new_segment_data = {"text": text_for_new if text_for_new else constants.EMPTY_SEGMENT_PLACEHOLDER}
        new_segment_data.update(new_segment_properties) # Add speaker/ts properties
        
        new_segment_id = self.add_segment(new_segment_data, reference_segment_id=original_segment_id, position="below")
        return new_segment_id is not None
        
    def remove_segment(self, segment_id_to_remove: str) -> bool:
        original_len = len(self.segments)
        self.segments = [s for s in self.segments if s["id"] != segment_id_to_remove]
        return len(self.segments) < original_len
        
    def merge_segment_upwards(self, segment_id: str) -> bool:
        index = self.get_segment_index(segment_id)
        if index <= 0: return False
        current_segment = self.segments[index]; previous_segment = self.segments[index - 1]

        prev_text = previous_segment['text']
        curr_text = current_segment['text']

        # Don't add a space if one segment's text is the placeholder
        if prev_text == constants.EMPTY_SEGMENT_PLACEHOLDER:
            prev_text = ""
        if curr_text == constants.EMPTY_SEGMENT_PLACEHOLDER:
            curr_text = ""
            
        sep = " " if prev_text and curr_text else ""
        merged_text = prev_text + sep + curr_text
        previous_segment['text'] = merged_text if merged_text else constants.EMPTY_SEGMENT_PLACEHOLDER

        if current_segment.get("has_explicit_end_time") and current_segment.get("end_time") is not None:
            previous_segment["end_time"] = current_segment["end_time"]; previous_segment["has_explicit_end_time"] = True
        else:
            previous_segment["end_time"] = None; previous_segment["has_explicit_end_time"] = False
        self.segments.pop(index); return True

    def merge_multiple_segments(self, segment_ids: list[str]) -> str | None:
        if len(segment_ids) < 2: return None
        id_to_index = {seg["id"]: i for i, seg in enumerate(self.segments)}
        sorted_ids = sorted(segment_ids, key=lambda seg_id: id_to_index.get(seg_id, float('inf')))
        target_segment_id = sorted_ids[0]; target_segment = self.get_segment_by_id(target_segment_id)
        if not target_segment: return None
        ids_to_remove = set()
        for i in range(1, len(sorted_ids)):
            segment_to_merge_id = sorted_ids[i]
            segment_to_merge = self.get_segment_by_id(segment_to_merge_id)
            if not segment_to_merge: continue

            target_text = target_segment['text']
            merge_text = segment_to_merge['text']

            if target_text == constants.EMPTY_SEGMENT_PLACEHOLDER: target_text = ""
            if merge_text == constants.EMPTY_SEGMENT_PLACEHOLDER: merge_text = ""
            
            sep = " " if target_text and merge_text else "";
            merged_text = target_text + sep + merge_text
            target_segment["text"] = merged_text if merged_text else constants.EMPTY_SEGMENT_PLACEHOLDER

            if segment_to_merge.get("end_time") is not None:
                 target_segment["end_time"] = segment_to_merge["end_time"]
                 if segment_to_merge.get("has_explicit_end_time"): target_segment["has_explicit_end_time"] = True
            ids_to_remove.add(segment_to_merge_id)
        self.segments = [seg for seg in self.segments if seg["id"] not in ids_to_remove]
        return target_segment_id
        
    def format_segments_for_saving(self, include_timestamps: bool, include_end_times: bool) -> list[str]:
        output_lines = []
        for seg in self.segments:
            parts = [];
            
            text_to_save = seg['text']
            if text_to_save == constants.EMPTY_SEGMENT_PLACEHOLDER:
                text_to_save = ""

            if include_timestamps and seg.get("has_timestamps"):
                start_str = self.seconds_to_time_str(seg['start_time'])
                if include_end_times and seg.get("has_explicit_end_time") and seg['end_time'] is not None:
                    parts.append(f"[{start_str} - {self.seconds_to_time_str(seg['end_time'])}]")
                else: parts.append(f"[{start_str}]")
            if seg['speaker_raw'] != constants.NO_SPEAKER_LABEL:
                speaker_display_name = self.speaker_map.get(seg['speaker_raw'], seg['speaker_raw'])
                parts.append(f"{speaker_display_name}:")
            
            parts.append(text_to_save)
            output_lines.append(" ".join(filter(None, parts))) 
        return output_lines