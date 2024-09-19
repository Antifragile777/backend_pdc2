from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
from gentle import forced_aligner
import yt_dlp
import requests
import json
import os
import re
from urllib.parse import urlparse, parse_qs

app = FastAPI()

given_url = "https://youtu.be/Xu8U_fOU0iU"


def extract_video_id(url):
    # Patterns for video ID extraction
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
    # print(parsed_url)
    
    # Check for youtu.be domain
    if parsed_url.netloc in ['youtu.be', 'm.youtu.be']:
        return parsed_url.path[1:]
    print(parsed_url.path[1:])
    
    # Check query parameters
    if 'v' in parse_qs(parsed_url.query):
        return parse_qs(parsed_url.query)['v'][0]
    
    
    # Check for other patterns
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        
    return None

extracted_video_id = extract_video_id(given_url)
print(extract_video_id)

def get_youtube_transcript(video_id):
    try: 
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching transcript: {str(e)}")
    
transcript = get_youtube_transcript(extract_video_id)
print(transcript)

# download audio file with yt_dlp

def download_audio(video_id):
    ydl_opts = {
        'format': 'worstaudio/worst',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '48',
        }],
        'outtmpl': f'{video_id}.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
    return f"{video_id}.wav"