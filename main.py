import os
import json
import tempfile
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import re
import yt_dlp
from montreal_forced_aligner import aligner
from montreal_forced_aligner.command_line.mfa import mfa_align

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
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': f'{video_id}.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
    return f"{video_id}.wav"

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

    # Run MFA align
    mfa_align(corpus_dir, "english", output_dir, clean=True, verbose=False)

    # Read the TextGrid file
    textgrid_path = os.path.join(output_dir, f"{video_id}.TextGrid")
    with open(textgrid_path, 'r') as f:
        textgrid_content = f.read()

    # Clean up temporary files
    os.remove(os.path.join(corpus_dir, f"{video_id}.wav"))
    os.remove(os.path.join(corpus_dir, f"{video_id}.txt"))
    os.rmdir(corpus_dir)
    os.remove(textgrid_path)
    os.rmdir(output_dir)

    return textgrid_content

def process_alignment(textgrid_content):
    word_level_timestamps = []
    lines = textgrid_content.split('\n')
    in_word_tier = False
    for i, line in enumerate(lines):
        if 'name = "words"' in line:
            in_word_tier = True
        elif 'item [' in line:
            in_word_tier = False
        if in_word_tier and 'intervals [' in line:
            start = float(lines[i+1].split('=')[1].strip())
            end = float(lines[i+2].split('=')[1].strip())
            word = lines[i+3].split('=')[1].strip().strip('"')
            word_level_timestamps.append({
                'word': word,
                'start': start,
                'end': end
            })
    return word_level_timestamps

def get_word_level_timestamps(url):
    video_id = extract_video_id(url)
    if not video_id:
        print("Invalid YouTube URL")
        return None

    transcript = get_youtube_transcript(video_id)
    if not transcript:
        return None

    alignment = align_transcript_with_audio(video_id, transcript)
    word_level_timestamps = process_alignment(alignment)

    return word_level_timestamps

# Example usage
if __name__ == "__main__":
    given_url = "https://youtu.be/Xu8U_fOU0iU"
    result = get_word_level_timestamps(given_url)
    print(json.dumps(result, indent=2))