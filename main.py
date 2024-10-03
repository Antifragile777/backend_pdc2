import os
import json
import tempfile
import subprocess
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import re
import yt_dlp
import textgrid

def extract_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|v\/|vi\/|youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})',
        r'(?:www\.|m\.)?youtube\.com\/watch\?v=([0-9A-Za-z_-]{11})',
        r'(?:www\.|m\.)?youtube(?:-nocookie)?\.com\/embed\/([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/shorts\/([0-9A-Za-z_-]{11})',
        r'm\.youtube\.com\/watch\?v=([0-9A-Za-z_-]{11})',
        r'm\.youtube\.com\/shorts\/([0-9A-Za-z_-]{11})'
    ]
    
    parsed_url = urlparse(url)
    
    if parsed_url.netloc in ['youtu.be', 'm.youtu.be']:
        return parsed_url.path[1:]
    
    if 'v' in parse_qs(parsed_url.query):
        return parse_qs(parsed_url.query)['v'][0]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        
    return None

def get_youtube_transcript(video_id):
    try: 
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        print(f"Error fetching transcript: {str(e)}")
        return None

def download_audio(video_id):
    output_filename = f'{video_id}.flac'
    ydl_opts = {
        'format': 'worstaudio/worst',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'flac',
            'preferredquality': '0', # Fastest but largest FLAC compression
        }],
        'outtmpl': f'{video_id}.%(ext)s',
        'keepvideo': True,
        'verbose': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
        
        # Check if the file exists and has a non-zero size
        if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
            print(f"Audio file successfully downloaded: {output_filename}")
            return output_filename
        else:
            print(f"Error: Audio file not found or empty: {output_filename}")
            return None
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return None   

def prepare_transcript_for_mfa(transcript):
    return " ".join([item['text'] for item in transcript])

def align_transcript_with_audio(video_id, transcript):
    audio_file = download_audio(video_id)
    transcript_text = prepare_transcript_for_mfa(transcript)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_transcript:
        temp_transcript.write(transcript_text)
        temp_transcript_path = temp_transcript.name

    corpus_dir = tempfile.mkdtemp()
    os.rename(audio_file, os.path.join(corpus_dir, f"{video_id}.wav"))
    os.rename(temp_transcript_path, os.path.join(corpus_dir, f"{video_id}.txt"))

    output_dir = tempfile.mkdtemp()
    textgrid_path = os.path.join(output_dir, f"{video_id}.TextGrid")

    try:
        # Run MFA align using subprocess
        command = ["mfa", "align", corpus_dir, "english_mfa", "english_mfa", output_dir]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error during MFA alignment: {result.stderr}")
            return None

        # Check if TextGrid file was created
        if not os.path.exists(textgrid_path):
            print(f"TextGrid file not created. MFA output: {result.stdout}")
            return None

        # Read the TextGrid file
        tg = textgrid.TextGrid.fromFile(textgrid_path)

        # Process the TextGrid to extract word-level timestamps
        word_tier = tg[0]  # Assuming the word tier is the first tier
        word_level_timestamps = []
        for interval in word_tier:
            if interval.mark:  # Exclude silent intervals
                word_level_timestamps.append({
                    'word': interval.mark,
                    'start': interval.minTime,
                    'end': interval.maxTime
                })

        return word_level_timestamps

    except Exception as e:
        print(f"Error during MFA alignment: {str(e)}")
        return None

    finally:
        # Clean up temporary files
        if os.path.exists(os.path.join(corpus_dir, f"{video_id}.wav")):
            os.remove(os.path.join(corpus_dir, f"{video_id}.wav"))
        if os.path.exists(os.path.join(corpus_dir, f"{video_id}.txt")):
            os.remove(os.path.join(corpus_dir, f"{video_id}.txt"))
        os.rmdir(corpus_dir)
        if os.path.exists(textgrid_path):
            os.remove(textgrid_path)
        os.rmdir(output_dir)

def get_word_level_timestamps(url):
    video_id = extract_video_id(url)
    if not video_id:
        print("Invalid YouTube URL")
        return None

    transcript = get_youtube_transcript(video_id)
    if not transcript:
        return None

    word_level_timestamps = align_transcript_with_audio(video_id, transcript)
    return word_level_timestamps

# Example usage
if __name__ == "__main__":
    given_url = "https://www.youtube.com/watch?v=Mcotl9HSo4U"
    result = get_word_level_timestamps(given_url)
    print(json.dumps(result, indent=2))