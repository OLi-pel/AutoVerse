# core/correction_window_logic.py
import logging
import re
from tkinter import messagebox # For showing warnings during parsing
import uuid # For unique segment IDs

# Assuming constants.py is in the utils directory, a sibling to core and ui
try:
    from utils import constants
except ImportError:
    # Fallback for different execution contexts or project structures
    import sys
    import os
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_script_dir) 
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from utils import constants

logger = logging.getLogger(__name__)

class SegmentManager:
    def __init__(self, parent_window_for_dialogs=None):
        self.segments = []  # List of segment dicts
        self.speaker_map = {}  # Maps raw speaker labels to custom display names
        self.unique_speaker_labels = set()
        self.parent_window = parent_window_for_dialogs

        # Regex patterns (remain the same for parsing initial files)
        self.pattern_start_end_ts_speaker = re.compile(
            r"^\[(\d{2}:\d{2}\.\d{3})\s*-\s*(\d{2}:\d{2}\.\d{3})\]\s*([^:]+?):\s*(.*)$"
        )
        self.pattern_start_end_ts_only = re.compile(
            r"^\[(\d{2}:\d{2}\.\d{3})\s*-\s*(\d{2}:\d{2}\.\d{3})\]\s*(.*)$"
        )
        self.pattern_start_ts_speaker = re.compile(
            r"^\[(\d{2}:\d{2}\.\d{3})\]\s*([^:]+?):\s*(.*)$"
        )
        self.pattern_start_ts_only = re.compile(
            r"^\[(\d{2}:\d{2}\.\d{3})\]\s*(.*)$"
        )
        self.pattern_speaker_only = re.compile(
            r"^\s*([^:]+?):\s*(.*)$"
        )
        logger.info("SegmentManager initialized.")

    def _generate_unique_segment_id(self) -> str:
        """Generates a unique ID for a new segment."""
        return f"seg_{uuid.uuid4().hex[:8]}"

    def time_str_to_seconds(self, time_str: str) -> float | None:
        if not time_str or not isinstance(time_str, str): return None
        try:
            parts = time_str.split(':')
            if len(parts) == 3:  # HH:MM:SS.mmm
                h, m, s_ms = parts; s, ms = s_ms.split('.')
                return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
            elif len(parts) == 2:  # MM:SS.mmm
                m, s_ms = parts; s, ms = s_ms.split('.')
                return int(m) * 60 + int(s) + int(ms) / 1000.0
            return None
        except ValueError: return None

    def seconds_to_time_str(self, total_seconds: float | None, force_MM_SS: bool = True) -> str:
        if total_seconds is None: return "00:00.000" # Default for unset timestamps
        if not isinstance(total_seconds, (int, float)) or total_seconds < 0: total_seconds = 0.0
        
        abs_seconds = abs(total_seconds)
        h = 0
        if not force_MM_SS: h = int(abs_seconds // 3600); abs_seconds %= 3600
        m = int(abs_seconds // 60); s_float = abs_seconds % 60
        s_int = int(s_float); ms = int((s_float - s_int) * 1000)
        sign = "-" if total_seconds < 0 else ""
        
        if not force_MM_SS and h > 0: return f"{sign}{h:02d}:{m:02d}:{s_int:02d}.{ms:03d}"
        if force_MM_SS and h > 0: m += h * 60 
        return f"{sign}{m:02d}:{s_int:02d}.{ms:03d}"

    def parse_transcription_lines(self, text_lines: list[str]) -> bool:
        self.clear_segments()
        malformed_count = 0
        logger.debug(f"Parsing {len(text_lines)} lines.")

        for i, line_raw in enumerate(text_lines):
            line = line_raw.strip()
            if not line: continue

            start_s, end_s = 0.0, None # Default to 0.0 for start if no timestamp
            speaker = constants.NO_SPEAKER_LABEL; text = line
            has_ts, has_explicit_end = False, False

            m_se_ts_spk = self.pattern_start_end_ts_speaker.match(line)
            m_se_ts_only = self.pattern_start_end_ts_only.match(line)
            m_s_ts_spk = self.pattern_start_ts_speaker.match(line)
            m_s_ts_only = self.pattern_start_ts_only.match(line)
            m_spk_only = self.pattern_speaker_only.match(line)

            parsed_ok = False
            if m_se_ts_spk:
                s, e, spk, txt = m_se_ts_spk.groups()
                ps, pe = self.time_str_to_seconds(s), self.time_str_to_seconds(e)
                if ps is not None and pe is not None and ps <= pe:
                    start_s, end_s, speaker, text, has_ts, has_explicit_end, parsed_ok = ps, pe, spk.strip(), txt.strip(), True, True, True
            elif m_se_ts_only:
                s, e, txt = m_se_ts_only.groups()
                ps, pe = self.time_str_to_seconds(s), self.time_str_to_seconds(e)
                if ps is not None and pe is not None and ps <= pe:
                    start_s, end_s, text, has_ts, has_explicit_end, parsed_ok = ps, pe, txt.strip(), True, True, True
            elif m_s_ts_spk:
                s, spk, txt = m_s_ts_spk.groups()
                ps = self.time_str_to_seconds(s)
                if ps is not None:
                    start_s, speaker, text, has_ts, parsed_ok = ps, spk.strip(), txt.strip(), True, True
            elif m_s_ts_only:
                s, txt = m_s_ts_only.groups()
                ps = self.time_str_to_seconds(s)
                if ps is not None:
                    start_s, text, has_ts, parsed_ok = ps, txt.strip(), True, True
            elif m_spk_only:
                spk, txt = m_spk_only.groups()
                speaker, text, parsed_ok = spk.strip(), txt.strip(), True
            else: 
                text = line # Ensure text is the full line if no pattern matches
                parsed_ok = True
            
            if not parsed_ok : malformed_count +=1; logger.warning(f"L{i+1} Malformed: {line}")
            
            seg_id = self._generate_unique_segment_id()
            self.segments.append({
                "id": seg_id, "start_time": start_s, "end_time": end_s,
                "speaker_raw": speaker, "text": text, "original_line_num": i + 1,
                "text_tag_id": f"text_content_{seg_id}", # Use unique part of seg_id
                "timestamp_tag_id": f"ts_content_{seg_id}", # For double-click on timestamp
                "has_timestamps": has_ts, "has_explicit_end_time": has_explicit_end
            })
            if speaker != constants.NO_SPEAKER_LABEL: self.unique_speaker_labels.add(speaker)
        
        logger.info(f"Parsing done. {len(self.segments)} segments. {malformed_count} warnings.")
        if not self.segments and any(l.strip() for l in text_lines):
            if self.parent_window: messagebox.showerror("Parsing Error", "Could not parse segments.", parent=self.parent_window)
            return False
        if malformed_count > 0 and self.parent_window:
             messagebox.showwarning("Parsing Issues", f"{malformed_count} lines had issues.", parent=self.parent_window)
        return True

    def clear_segments(self):
        self.segments.clear(); self.speaker_map.clear(); self.unique_speaker_labels.clear()
        logger.info("Segment data cleared.")

    def get_segment_by_id(self, segment_id: str) -> dict | None:
        return next((s for s in self.segments if s["id"] == segment_id), None)

    def get_segment_index(self, segment_id: str) -> int:
        return next((i for i, s in enumerate(self.segments) if s["id"] == segment_id), -1)

    def update_segment_text(self, segment_id: str, new_text: str) -> bool:
        segment = self.get_segment_by_id(segment_id)
        if segment:
            if segment["text"] != new_text:
                segment["text"] = new_text
                logger.debug(f"Segment {segment_id} text updated.")
                return True
        return False


    def update_segment_from_full_line(self, segment_id: str, full_line_text: str):
        segment = self.get_segment_by_id(segment_id)
        if not segment:
            logger.warning(f"Could not find segment {segment_id} to update.")
            return

        line = full_line_text.strip()
        text_content = line
        
        # Re-build the prefix based on the segment's actual data
        prefix_parts = []
        if segment.get("has_timestamps"):
            prefix_parts.append(f"[{self.seconds_to_time_str(segment.get('start_time', 0))}]")
        
        speaker_label = segment.get("speaker_raw")
        if speaker_label and speaker_label != constants.NO_SPEAKER_LABEL:
            display_name = self.speaker_map.get(speaker_label, speaker_label)
            prefix_parts.append(f"{display_name}:")

        # Join parts and see if the line starts with it
        # This handles cases with and without timestamps/speakers gracefully.
        if prefix_parts:
            # We must be careful about space handling
            prefix_str = " ".join(prefix_parts)
            if line.startswith(prefix_str):
                 # +1 to account for the space after the prefix
                text_content = line[len(prefix_str):].lstrip()
            
        segment['text'] = text_content
        logger.info(f"Updated segment {segment_id} with new text: '{segment['text']}'")

    def _validate_timestamp_values(self, segment_id_being_edited: str, 
                                   new_start_time: float | None, 
                                   new_end_time: float | None) -> tuple[bool, str | None]:
        """Validates new timestamp values for a segment against itself and adjacent segments."""
        
        # 1. Internal consistency: start <= end (if both are provided)
        if new_start_time is not None and new_end_time is not None:
            if new_start_time > new_end_time:
                return False, "Start time cannot be after end time."

        current_segment_index = self.get_segment_index(segment_id_being_edited)
        if current_segment_index == -1:
            return False, "Segment not found for timestamp validation." # Should not happen

        # 2. Check against previous segment (if any and if it has timestamps)
        if new_start_time is not None and current_segment_index > 0:
            prev_segment = self.segments[current_segment_index - 1]
            if prev_segment.get("has_timestamps") and prev_segment.get("end_time") is not None:
                if new_start_time < prev_segment["end_time"]:
                    msg = (f"Warning: New start time ({self.seconds_to_time_str(new_start_time)}) overlaps "
                           f"with previous segment's end time ({self.seconds_to_time_str(prev_segment['end_time'])}).")
                    # This is a warning, not a hard block, but could be made one.
                    logger.warning(msg) 
                    # For now, let's return True but with a warning message that the UI can choose to show.
                    # Or, make it a hard block: return False, msg
            elif prev_segment.get("has_timestamps") and prev_segment.get("start_time") is not None and prev_segment.get("end_time") is None: # Prev has only start
                if new_start_time < prev_segment["start_time"]:
                     msg = (f"Warning: New start time ({self.seconds_to_time_str(new_start_time)}) is before "
                           f"previous segment's start time ({self.seconds_to_time_str(prev_segment['start_time'])}).")
                     logger.warning(msg)


        # 3. Check against next segment (if any and if it has timestamps)
        if new_end_time is not None and current_segment_index < len(self.segments) - 1:
            next_segment = self.segments[current_segment_index + 1]
            if next_segment.get("has_timestamps") and next_segment.get("start_time") is not None:
                if new_end_time > next_segment["start_time"]:
                    msg = (f"Warning: New end time ({self.seconds_to_time_str(new_end_time)}) overlaps "
                           f"with next segment's start time ({self.seconds_to_time_str(next_segment['start_time'])}).")
                    logger.warning(msg)
                    # Similar to above, this is a warning.

        # 4. Check for exact start time overlap with ANY other segment (excluding itself)
        if new_start_time is not None:
            for i, seg in enumerate(self.segments):
                if seg["id"] != segment_id_being_edited and seg.get("has_timestamps") and seg.get("start_time") == new_start_time:
                    msg = (f"Warning: New start time ({self.seconds_to_time_str(new_start_time)}) is identical "
                           f"to segment {i+1}'s start time.")
                    logger.warning(msg)
                    break # One warning is enough

        return True, None # No hard blocking errors found, possibly some warnings logged.

    def update_segment_timestamps(self, segment_id: str, new_start_time_str: str | None, new_end_time_str: str | None) -> tuple[bool, str | None]:
        """
        Updates timestamps for a segment. Accepts time strings.
        Returns (success_boolean, error_message_or_none).
        """
        segment = self.get_segment_by_id(segment_id)
        if not segment:
            return False, "Segment not found."

        parsed_start_time = None
        if new_start_time_str:
            parsed_start_time = self.time_str_to_seconds(new_start_time_str)
            if parsed_start_time is None:
                return False, "Invalid start time format. Use MM:SS.mmm or HH:MM:SS.mmm."
        
        parsed_end_time = None
        if new_end_time_str:
            parsed_end_time = self.time_str_to_seconds(new_end_time_str)
            if parsed_end_time is None:
                return False, "Invalid end time format. Use MM:SS.mmm or HH:MM:SS.mmm."

        # Perform validation
        is_valid, validation_msg = self._validate_timestamp_values(segment_id, parsed_start_time, parsed_end_time)
        if not is_valid: # If _validate_timestamp_values returns False, it's a hard block
            return False, validation_msg
        # If is_valid is True but validation_msg is not None, it's a warning that was logged.

        # Update segment
        segment["start_time"] = parsed_start_time if parsed_start_time is not None else 0.0
        segment["end_time"] = parsed_end_time # Can be None

        segment["has_timestamps"] = parsed_start_time is not None
        segment["has_explicit_end_time"] = parsed_start_time is not None and parsed_end_time is not None
        
        logger.debug(f"Segment {segment_id} timestamps updated: S={segment['start_time']} E={segment['end_time']}")
        return True, validation_msg # Return True, and any warning message from validation

    def update_segment_speaker(self, segment_id: str, new_speaker_raw: str):
        segment = self.get_segment_by_id(segment_id)
        if segment:
            segment["speaker_raw"] = new_speaker_raw
            if new_speaker_raw != constants.NO_SPEAKER_LABEL:
                self.unique_speaker_labels.add(new_speaker_raw) 
            logger.debug(f"Segment {segment_id} speaker updated to {new_speaker_raw}")

    def remove_segment(self, segment_id_to_remove: str) -> bool:
        original_len = len(self.segments)
        self.segments = [s for s in self.segments if s["id"] != segment_id_to_remove]
        if len(self.segments) < original_len:
            logger.info(f"Segment {segment_id_to_remove} removed.")
            return True
        logger.warning(f"Attempted to remove non-existent segment {segment_id_to_remove}.")
        return False

    def add_segment(self, segment_data: dict, reference_segment_id: str | None = None, position: str = "below") -> str | None:
        """
        Adds a new segment to the list.
        segment_data should be a dictionary with keys like 'text', 'speaker_raw', 
                         'start_time', 'end_time', 'has_timestamps', 'has_explicit_end_time'.
        Returns the ID of the newly added segment or None on failure.
        """
        new_id = self._generate_unique_segment_id()
        
        # Ensure essential keys are present, provide defaults if not
        final_segment_data = {
            "id": new_id,
            "text": segment_data.get("text", ""),
            "speaker_raw": segment_data.get("speaker_raw", constants.NO_SPEAKER_LABEL),
            "start_time": segment_data.get("start_time", 0.0), # Default to 0.0 if not provided
            "end_time": segment_data.get("end_time", None),    # Default to None if not provided
            "has_timestamps": segment_data.get("has_timestamps", False),
            "has_explicit_end_time": segment_data.get("has_explicit_end_time", False),
            "original_line_num": -1, # Indicates manually added
            "text_tag_id": f"text_content_{new_id}",
            "timestamp_tag_id": f"ts_content_{new_id}"
        }

        insert_at_index = -1
        if reference_segment_id:
            ref_index = self.get_segment_index(reference_segment_id)
            if ref_index != -1:
                insert_at_index = ref_index + 1 if position == "below" else ref_index
            else:
                logger.warning(f"add_segment: Reference segment ID '{reference_segment_id}' not found. Adding to end.")
                insert_at_index = len(self.segments)
        else: # No reference ID, add to end
            insert_at_index = len(self.segments)

        if 0 <= insert_at_index <= len(self.segments):
            self.segments.insert(insert_at_index, final_segment_data)
            if final_segment_data["speaker_raw"] != constants.NO_SPEAKER_LABEL:
                self.unique_speaker_labels.add(final_segment_data["speaker_raw"])
            logger.info(f"Added new segment {new_id} at index {insert_at_index}.")
            return new_id
        else:
            logger.error(f"Failed to add new segment: Invalid insert index {insert_at_index}.")
            return None

    def split_segment(self, original_segment_id: str, text_split_index: int, 
                      new_segment_speaker: str, 
                      new_segment_ts_type: str) -> tuple[str | None, str | None]:
        """
        Splits a segment into two.
        original_segment_id: ID of the segment to split.
        text_split_index: Character index in the original segment's text where the split occurs.
        new_segment_speaker: Speaker for the new (second) segment.
        new_segment_ts_type: Timestamp type for the new segment ('none', 'start_only', 'start_end').
        Returns: (original_segment_id, new_segment_id) or (None, None) on failure.
        """
        original_segment = self.get_segment_by_id(original_segment_id)
        if not original_segment:
            logger.error(f"split_segment: Original segment {original_segment_id} not found.")
            return None, None

        original_text = original_segment["text"]
        text_for_original = original_text[:text_split_index].strip()
        text_for_new = original_text[text_split_index:].strip()

        # Update original segment's text
        original_segment["text"] = text_for_original
        # Timestamps of original segment remain, but end_time might need adjustment if it was based on full text.
        # For now, we leave original timestamps as they were, user can edit.

        # Prepare data for the new segment
        new_seg_start_time = 0.0
        new_seg_end_time = None
        new_seg_has_ts = False
        new_seg_has_explicit_end = False

        if new_segment_ts_type == "start_only":
            new_seg_has_ts = True
            # Optionally, try to set a sensible default start time, e.g., original's end time
            # if original_segment.get("end_time") is not None:
            #    new_seg_start_time = original_segment["end_time"]
            # else:
            #    new_seg_start_time = original_segment.get("start_time", 0.0)
        elif new_segment_ts_type == "start_end":
            new_seg_has_ts = True
            new_seg_has_explicit_end = True # Even if values are 0.0 and None initially

        new_segment_data = {
            "text": text_for_new,
            "speaker_raw": new_segment_speaker,
            "start_time": new_seg_start_time,
            "end_time": new_seg_end_time,
            "has_timestamps": new_seg_has_ts,
            "has_explicit_end_time": new_seg_has_explicit_end
        }

        new_segment_id = self.add_segment(new_segment_data, reference_segment_id=original_segment_id, position="below")
        if new_segment_id:
            logger.info(f"Segment {original_segment_id} split. New segment {new_segment_id} created.")
            return original_segment_id, new_segment_id
        else:
            logger.error(f"Failed to add new segment during split of {original_segment_id}.")
            # Revert original segment's text if add failed? For now, no.
            return original_segment_id, None


    def merge_segment_with_previous(self, current_segment_id: str) -> bool:
        current_segment_index = self.get_segment_index(current_segment_id)

        if current_segment_index <= 0:
            logger.warning(f"Cannot merge segment {current_segment_id}: no previous segment or it's the first.")
            return False
            
        current_segment = self.segments[current_segment_index]
        previous_segment = self.segments[current_segment_index - 1]

        if previous_segment["speaker_raw"] != current_segment["speaker_raw"] or \
           previous_segment["speaker_raw"] == constants.NO_SPEAKER_LABEL:
            logger.warning(f"Cannot merge {current_segment_id}: speakers differ or previous has no speaker.")
            return False 

        if current_segment["end_time"] is not None:
            if previous_segment["end_time"] is None or current_segment["end_time"] > previous_segment["end_time"]:
                 previous_segment["end_time"] = current_segment["end_time"]
            if current_segment.get("has_explicit_end_time"):
                 previous_segment["has_explicit_end_time"] = True
        
        sep = " " if previous_segment["text"] and current_segment["text"] and \
                     not previous_segment["text"].endswith(" ") and \
                     not current_segment["text"].startswith(" ") else ""
        previous_segment["text"] += sep + current_segment["text"]
        
        if not previous_segment.get("has_timestamps") and current_segment.get("has_timestamps"):
            previous_segment["has_timestamps"] = True
            if current_segment.get("has_explicit_end_time"):
                 previous_segment["has_explicit_end_time"] = True


        logger.info(f"Merged segment {current_segment['id']} into {previous_segment['id']}.")
        self.segments.pop(current_segment_index) 
        return True

    def format_segments_for_saving(self, include_timestamps: bool, include_end_times: bool) -> list[str]:
        output_lines = []
        for seg in self.segments:
            parts = []
            if include_timestamps and seg.get("has_timestamps"):
                start_str = self.seconds_to_time_str(seg['start_time'])
                if include_end_times and seg.get("has_explicit_end_time") and seg['end_time'] is not None:
                    end_str = self.seconds_to_time_str(seg['end_time'])
                    parts.append(f"[{start_str} - {end_str}]")
                else: 
                    parts.append(f"[{start_str}]")
            
            if seg['speaker_raw'] != constants.NO_SPEAKER_LABEL:
                speaker_display_name = self.speaker_map.get(seg['speaker_raw'], seg['speaker_raw'])
                parts.append(f"{speaker_display_name}:")
            
            parts.append(seg['text'])
            output_lines.append(" ".join(filter(None, parts))) 
        return output_lines

