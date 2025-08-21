# utils/audio_utils.py
import logging
import os
import tempfile
import numpy as np

logger = logging.getLogger(__name__)

def preprocess_audio_for_diarization(audio_path: str, target_sr: int = 16000, chunk_size: int = 160000):
    """
    Preprocess audio to handle tensor size mismatches in pyannote.audio pipeline.
    
    Args:
        audio_path: Path to the input audio file
        target_sr: Target sample rate (default: 16000 Hz)
        chunk_size: Expected chunk size for the model (default: 160000 samples = 10 seconds at 16kHz)
    
    Returns:
        str: Path to the preprocessed temporary audio file, or None if preprocessing failed
    """
    try:
        import librosa
        import soundfile as sf
        
        # Load audio with librosa to normalize it
        audio, sr = librosa.load(audio_path, sr=target_sr, mono=True)
        logger.debug(f"Loaded audio: {len(audio)} samples at {sr} Hz")
        
        # Ensure minimum length and pad if necessary
        min_duration = 1.0  # 1 second minimum
        min_samples = int(min_duration * sr)
        
        if len(audio) < min_samples:
            # Pad short audio files
            padding_needed = min_samples - len(audio)
            audio = np.pad(audio, (0, padding_needed), mode='constant', constant_values=0)
            logger.info(f"Padded short audio from {len(audio) - padding_needed} to {len(audio)} samples")
        
        # Ensure the audio length is divisible by chunk_size to prevent tensor size mismatches
        if len(audio) % chunk_size != 0:
            # Pad to make it divisible by chunk_size
            padding_needed = chunk_size - (len(audio) % chunk_size)
            audio = np.pad(audio, (0, padding_needed), mode='constant', constant_values=0)
            logger.debug(f"Padded audio to align with chunk size: {len(audio)} samples")
        
        # Create a temporary file with the preprocessed audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
            sf.write(temp_path, audio, sr)
            logger.debug(f"Saved preprocessed audio to: {temp_path}")
        
        return temp_path
        
    except ImportError as e:
        logger.error(f"Required audio processing libraries not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in audio preprocessing: {e}", exc_info=True)
        return None

def cleanup_temp_file(file_path: str):
    """
    Safely remove a temporary file.
    
    Args:
        file_path: Path to the temporary file to remove
    """
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.debug(f"Cleaned up temporary file: {file_path}")
        except OSError as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")

def get_audio_info(audio_path: str):
    """
    Get basic information about an audio file.
    
    Args:
        audio_path: Path to the audio file
    
    Returns:
        dict: Audio information including duration, sample rate, channels, etc.
    """
    try:
        import librosa
        import soundfile as sf
        
        # Get basic info using soundfile
        info = sf.info(audio_path)
        
        # Get duration using librosa for more accuracy
        duration = librosa.get_duration(path=audio_path)
        
        return {
            'duration': duration,
            'sample_rate': info.samplerate,
            'channels': info.channels,
            'frames': info.frames,
            'format': info.format,
            'subtype': info.subtype
        }
    except Exception as e:
        logger.error(f"Error getting audio info for {audio_path}: {e}")
        return None