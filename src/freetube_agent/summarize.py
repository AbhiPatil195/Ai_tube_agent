"""
Video Summarization Module
Generates summaries, key points, and insights from transcripts using local LLM.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from pathlib import Path

from .llm import run_ollama
from .transcribe import Transcript
from .logger import logger, error_tracker


def generate_summary(
    transcript: Transcript,
    model: str = "llama3.2",
    ollama_path: Optional[str] = None,
    style: str = "comprehensive"
) -> Dict[str, Any]:
    """
    Generate a comprehensive summary of the video transcript.
    
    Args:
        transcript: Transcript object with text and segments
        model: Ollama model to use
        ollama_path: Optional path to Ollama executable
        style: Summary style - "comprehensive", "brief", "academic", "casual"
    
    Returns:
        Dictionary with summary components
    """
    logger.info(f"Generating {style} summary (model={model})")
    text = transcript.text
    word_count = len(text.split())
    logger.debug(f"Transcript length: {word_count} words")
    
    # Build prompt based on style
    if style == "comprehensive":
        prompt = f"""Analyze this video transcript and provide a comprehensive summary.

Transcript:
{text}

Please provide:
1. A 3-5 sentence overview
2. 5-7 key points (bullet points)
3. Main topics covered
4. Target audience
5. Key takeaways

Format your response clearly with headers."""

    elif style == "brief":
        prompt = f"""Summarize this video transcript briefly.

Transcript:
{text}

Provide:
1. One paragraph summary (3-4 sentences)
2. 3 key points (bullets)

Be concise."""

    elif style == "academic":
        prompt = f"""Provide an academic summary of this video transcript.

Transcript:
{text}

Include:
1. Abstract (150 words)
2. Key concepts and definitions
3. Main arguments or findings
4. Methodology (if applicable)
5. Conclusions

Use formal academic language."""

    else:  # casual
        prompt = f"""Give a casual, friendly summary of this video.

Transcript:
{text}

Include:
1. Quick overview in simple language
2. Cool highlights (3-5 bullets)
3. Why someone should watch this

Keep it conversational and engaging."""

    try:
        logger.debug(f"Calling Ollama with {style} prompt")
        summary_text = run_ollama(model=model, prompt=prompt, ollama_path=ollama_path, timeout=300)
        logger.info(f"Summary generated successfully ({len(summary_text)} characters)")
        
        return {
            "success": True,
            "summary": summary_text,
            "style": style,
            "model": model,
            "length": len(text.split()),
        }
    
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        error_tracker.log_error(e, context=f"Generating {style} summary", module="summarize", function="generate_summary")
        return {
            "success": False,
            "error": str(e),
            "style": style,
            "model": model,
        }


def extract_key_points(
    transcript: Transcript,
    model: str = "llama3.2",
    ollama_path: Optional[str] = None,
    num_points: int = 7
) -> Dict[str, Any]:
    """
    Extract key points from the transcript.
    
    Args:
        transcript: Transcript object
        model: Ollama model
        ollama_path: Optional Ollama path
        num_points: Number of key points to extract
    
    Returns:
        Dictionary with key points
    """
    logger.info(f"Extracting {num_points} key points")
    text = transcript.text
    
    prompt = f"""Extract the {num_points} most important key points from this video transcript.

Transcript:
{text}

List exactly {num_points} key points as bullet points. Each point should be:
- One clear sentence
- Capture a distinct idea or insight
- Be specific and actionable when possible

Format: Return only the bullet points, one per line, starting with "- "."""

    try:
        response = run_ollama(model=model, prompt=prompt, ollama_path=ollama_path, timeout=180)
        
        # Parse bullet points
        lines = response.strip().split('\n')
        key_points = []
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('• ') or line.startswith('* '):
                key_points.append(line[2:].strip())
            elif line and not line.startswith('#'):
                key_points.append(line)
        
        return {
            "success": True,
            "key_points": key_points[:num_points],
            "raw_response": response,
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "key_points": [],
        }


def extract_topics(
    transcript: Transcript,
    model: str = "llama3.2",
    ollama_path: Optional[str] = None,
    max_topics: int = 5
) -> Dict[str, Any]:
    """
    Identify main topics/themes in the transcript.
    
    Args:
        transcript: Transcript object
        model: Ollama model
        ollama_path: Optional Ollama path
        max_topics: Maximum number of topics
    
    Returns:
        Dictionary with topics
    """
    text = transcript.text
    
    prompt = f"""Identify the {max_topics} main topics or themes discussed in this video transcript.

Transcript:
{text}

For each topic, provide:
- Topic name (2-4 words)
- Brief description (one sentence)

Format as:
1. Topic Name: Description
2. Topic Name: Description
etc."""

    try:
        response = run_ollama(model=model, prompt=prompt, ollama_path=ollama_path, timeout=180)
        
        # Parse topics
        lines = response.strip().split('\n')
        topics = []
        for line in lines:
            line = line.strip()
            if ':' in line:
                # Remove numbering if present
                if line[0].isdigit():
                    line = line.split('.', 1)[1].strip() if '.' in line else line
                parts = line.split(':', 1)
                if len(parts) == 2:
                    topics.append({
                        "name": parts[0].strip(),
                        "description": parts[1].strip()
                    })
        
        return {
            "success": True,
            "topics": topics[:max_topics],
            "raw_response": response,
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "topics": [],
        }


def generate_tldr(
    transcript: Transcript,
    model: str = "llama3.2",
    ollama_path: Optional[str] = None,
    max_words: int = 50
) -> Dict[str, Any]:
    """
    Generate a TL;DR (too long; didn't read) summary.
    
    Args:
        transcript: Transcript object
        model: Ollama model
        ollama_path: Optional Ollama path
        max_words: Maximum words for TL;DR
    
    Returns:
        Dictionary with TL;DR
    """
    text = transcript.text
    
    prompt = f"""Create a TL;DR (Too Long; Didn't Read) summary of this video in {max_words} words or less.

Transcript:
{text}

Requirements:
- Maximum {max_words} words
- One or two sentences
- Capture the absolute essence
- Be engaging and clear

Return only the TL;DR text, nothing else."""

    try:
        tldr = run_ollama(model=model, prompt=prompt, ollama_path=ollama_path, timeout=120)
        
        return {
            "success": True,
            "tldr": tldr.strip(),
            "word_count": len(tldr.split()),
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "tldr": "",
        }


def generate_full_analysis(
    transcript: Transcript,
    model: str = "llama3.2",
    ollama_path: Optional[str] = None,
    style: str = "comprehensive"
) -> Dict[str, Any]:
    """
    Generate complete analysis: summary, key points, topics, and TL;DR.
    
    Args:
        transcript: Transcript object
        model: Ollama model
        ollama_path: Optional Ollama path
        style: Summary style
    
    Returns:
        Dictionary with all analysis components
    """
    # Run all analyses
    summary_result = generate_summary(transcript, model, ollama_path, style)
    points_result = extract_key_points(transcript, model, ollama_path)
    topics_result = extract_topics(transcript, model, ollama_path)
    tldr_result = generate_tldr(transcript, model, ollama_path)
    
    return {
        "summary": summary_result,
        "key_points": points_result,
        "topics": topics_result,
        "tldr": tldr_result,
        "transcript_length": len(transcript.text.split()),
        "video_duration": transcript.segments[-1].end if transcript.segments else 0,
    }
