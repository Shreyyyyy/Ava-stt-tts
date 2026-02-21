import os
from typing import List, Dict, Any, Optional
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from sarvamai import SarvamAI
except ImportError:
    logger.error("sarvamai package not installed. Install with: pip install sarvamai")
    SarvamAI = None

class SarvamSTTClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY environment variable must be set")
        
        if SarvamAI is None:
            raise ImportError("sarvamai package is required. Install with: pip install sarvamai")
        
        self.client = SarvamAI(api_subscription_key=self.api_key)
    
    def transcribe_files(
        self,
        audio_paths: List[str],
        model: str = "saaras:v3",
        mode: str = "transcribe",
        language_code: str = "unknown",
        with_diarization: bool = True,
        num_speakers: Optional[int] = None,
        output_dir: str = "./output"
    ) -> Dict[str, Any]:
        """
        Transcribe audio files using Sarvam AI Speech-to-Text
        
        Args:
            audio_paths: List of paths to audio files
            model: STT model (default: saaras:v3)
            mode: Processing mode - 'transcribe' or 'translate' (default: transcribe)
            language_code: Language code or 'unknown' for auto-detection (default: unknown)
            with_diarization: Enable speaker diarization (default: True)
            num_speakers: Number of speakers (optional)
            output_dir: Directory to save outputs (default: ./output)
            
        Returns:
            Dictionary containing transcription results and metadata
        """
        try:
            # Create batch job
            job = self.client.speech_to_text_job.create_job(
                model=model,
                mode=mode,
                language_code=language_code,
                with_diarization=with_diarization,
                num_speakers=num_speakers
            )
            
            logger.info(f"Created STT job with ID: {job.job_id}")
            
            # Upload files
            job.upload_files(file_paths=audio_paths)
            logger.info(f"Uploaded {len(audio_paths)} files for processing")
            
            # Start processing
            job.start()
            logger.info("Started STT processing")
            
            # Wait for completion
            job.wait_until_complete()
            logger.info("STT processing completed")
            
            # Get results
            file_results = job.get_file_results()
            
            # Download outputs for successful files
            successful_files = file_results.get('successful', [])
            if successful_files:
                job.download_outputs(output_dir=output_dir)
                logger.info(f"Downloaded {len(successful_files)} file(s) to: {output_dir}")
            
            return {
                "job_id": job.job_id,
                "total_files": len(audio_paths),
                "successful": len(successful_files),
                "failed": len(file_results.get('failed', [])),
                "results": file_results,
                "output_dir": output_dir
            }
            
        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            raise
    
    def transcribe_single_file(
        self,
        audio_path: str,
        model: str = "saaras:v3",
        mode: str = "transcribe",
        language_code: str = "unknown",
        with_diarization: bool = True,
        num_speakers: Optional[int] = None,
        output_dir: str = "./output"
    ) -> Dict[str, Any]:
        """
        Transcribe a single audio file
        
        Args:
            audio_path: Path to audio file
            model: STT model (default: saaras:v3)
            mode: Processing mode - 'transcribe' or 'translate' (default: transcribe)
            language_code: Language code or 'unknown' for auto-detection (default: unknown)
            with_diarization: Enable speaker diarization (default: True)
            num_speakers: Number of speakers (optional)
            output_dir: Directory to save outputs (default: ./output)
            
        Returns:
            Dictionary containing transcription result
        """
        return self.transcribe_files(
            audio_paths=[audio_path],
            model=model,
            mode=mode,
            language_code=language_code,
            with_diarization=with_diarization,
            num_speakers=num_speakers,
            output_dir=output_dir
        )
    
    def get_supported_languages(self) -> Dict[str, Any]:
        """Get supported languages for STT"""
        return {
            "unknown": "Auto-detect",
            "hi-IN": "Hindi",
            "en-IN": "English (Indian)",
            "bn-IN": "Bengali",
            "gu-IN": "Gujarati",
            "kn-IN": "Kannada",
            "ml-IN": "Malayalam",
            "mr-IN": "Marathi",
            "pa-IN": "Punjabi",
            "ta-IN": "Tamil",
            "te-IN": "Telugu"
        }
    
    def get_available_models(self) -> Dict[str, Any]:
        """Get available STT models"""
        return {
            "saaras:v3": "Latest model - Best accuracy",
            "saaras:v2": "Previous version - Faster processing"
        }
