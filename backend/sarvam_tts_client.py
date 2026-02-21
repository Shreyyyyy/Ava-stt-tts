import os
import requests
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class SarvamTTSClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        self.api_url = "https://api.sarvam.ai/text-to-speech/stream"
        
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY environment variable must be set")
    
    def stream_tts(
        self,
        text: str,
        target_language_code: str = "hi-IN",
        speaker: str = "shreya",
        model: str = "bulbul:v3",
        pace: float = 1.1,
        speech_sample_rate: int = 22050,
        output_audio_codec: str = "mp3",
        enable_preprocessing: bool = True,
        output_file: str = "output.mp3"
    ) -> str:
        """
        Stream text-to-speech conversion and save to file
        
        Args:
            text: Text to convert to speech
            target_language_code: Target language code (default: hi-IN)
            speaker: Voice speaker (default: shreya)
            model: TTS model (default: bulbul:v3)
            pace: Speech pace (default: 1.1)
            speech_sample_rate: Audio sample rate (default: 22050)
            output_audio_codec: Audio codec (default: mp3)
            enable_preprocessing: Enable text preprocessing (default: True)
            output_file: Output file path (default: output.mp3)
            
        Returns:
            Path to the generated audio file
        """
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "target_language_code": target_language_code,
            "speaker": speaker,
            "model": model,
            "pace": pace,
            "speech_sample_rate": speech_sample_rate,
            "output_audio_codec": output_audio_codec,
            "enable_preprocessing": enable_preprocessing
        }
        
        try:
            with requests.post(self.api_url, headers=headers, json=payload, stream=True) as response:
                response.raise_for_status()
                
                with open(output_file, "wb") as f:
                    total_bytes = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_bytes += len(chunk)
                            logger.debug(f"Received {len(chunk)} bytes")
                
                logger.info(f"Audio saved to {output_file}, total size: {total_bytes} bytes")
                return output_file
                
        except requests.exceptions.RequestException as e:
            logger.error(f"TTS request failed: {e}")
            raise
        except IOError as e:
            logger.error(f"Failed to write audio file: {e}")
            raise
    
    def get_supported_languages(self) -> Dict[str, Any]:
        """Get supported languages for TTS"""
        # This would typically be another API call, but for now return common languages
        return {
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
    
    def get_available_speakers(self) -> Dict[str, Any]:
        """Get available speaker voices"""
        return {
            "shreya": "Female voice - Hindi",
            "meera": "Female voice - Hindi",
            "arvind": "Male voice - Hindi",
            "kavita": "Female voice - Hindi"
        }
