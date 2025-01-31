from download import (
    fetch_youtube_extract,
    check_youtube,
    local_file_extract,
    ensure_youtube_url
)
from diarize import (
    import_time_file,
    time_to_seconds
)
from transcribe import (
    extract_words
)
from typing import List, Optional
from os.path import exists, join
from word import Word
import time
import json
import os


def calculate_interval_overlap(start1, end1, start2, end2):
    """
    Calculates the overlap duration between two time intervals.

    :param start1: Start time of the first interval.
    :param end1: End time of the first interval.
    :param start2: Start time of the second interval.
    :param end2: End time of the second interval.
    :return: The overlap duration in the same units as the input times.
      Negative values indicate non-overlapping intervals.
    """

    if start2 > end1:
        return -(start2 - end1)
    if start1 > end2:
        return -(start1 - end2)
    maximum_start_time = max(start1, start2)
    minimum_end_time = min(end1, end2)
    return minimum_end_time - maximum_start_time


def assign_sentence_to_speakers(sentence_fragments, speakers):
    """
    Assigns each sentence fragment to the most likely
    speaker based on time overlap.

    :param sentence_fragments: List of sentence fragments,
    each with start and end times.
    :param speakers: List of speakers, each with time segments.
    """

    for sentence in sentence_fragments:
        max_overlap = 0
        assigned_speaker_index = 0

        for speaker_index, speaker in enumerate(speakers):
            for segment in speaker["segments"]:

                overlap = calculate_interval_overlap(
                    sentence["start"],
                    sentence["end"],
                    segment["start"],
                    segment["end"]
                    )

                if overlap > max_overlap:
                    max_overlap = overlap
                    assigned_speaker_index = speaker_index

        sentence["speaker_index"] = assigned_speaker_index
        print(f"Assigning {sentence['text']} to "
              f"speaker {assigned_speaker_index}"
              )


def ensure_directories(directories: List[Optional[str]]) -> None:
    """
    Creates each directory in the provided list if it does not already exist.
    """
    for directory in directories:
        if directory is not None and not os.path.exists(directory):
            os.makedirs(directory)


def get_audio_and_muted_video(
    input_video,
    download_directory,
    extract
):
    """
    Extracts audio and muted video from a given YouTube URL
    or local video file.
    """

    print("checking if url is youtube url...")
    if check_youtube(input_video):

        print("finished checking")
        input_video = ensure_youtube_url(input_video)

        print("downloading video...")
        return fetch_youtube_extract(
            input_video,
            extract=extract,
            directory=download_directory
            )
    else:
        print("extracting from local file...")
        return local_file_extract(
            input_video,
            directory=download_directory
            )


def get_extracted_words(
    transcribed_segments,
    words_file="words.txt",
    download_sub_directory="downloads",
    processing_start_time=time.time(),
    always_read=True
):
    """
    Extracts or loads words from a file, based on transcribed segments
    and specified conditions.
    """

    words_file = join(download_sub_directory, words_file)
    if not always_read and exists(words_file):

        print(f"[{(time.time() - processing_start_time):.1f}s] "
              f"words already exist, loading from {words_file}..."
              )
        with open(words_file, 'r', encoding='utf-8') as f:
            words_dicts = json.load(f)

        words = [Word(**word_dict) for word_dict in words_dicts]

        return words

    else:
        print(f"[{(time.time() - processing_start_time):.1f}s] "
              f"extracting words...", end="", flush=True
              )
        words = extract_words(transcribed_segments)

        print(f"[{(time.time() - processing_start_time):.1f}s] "
              f"saving words to {words_file}..."
              )
        with open(words_file, "w", encoding='utf-8') as f:
            json.dump([word.__dict__ for word in words], f, indent=4)

        print(f"[{(time.time() - processing_start_time):.1f}s] "
              "words saved successfully."
              )

        return words


def intervals_overlap(t1start, t1end, t2start, t2end):
    """
    Checks if two time intervals overlap.
    """

    if t1end <= t2start or t2end <= t1start:
        return False
    return True


def filter_by_time_limits(
    words,
    limit_times,
    time_handling_policy,
    word_timestamp_correction,
):
    """
    Filters words based on time limits and a specified handling policy.
    """

    if limit_times:

        print("filtering words by time file...")
        new_words = []

        for word in words:
            for time_start, time_end in limit_times:
                tstart = time_start
                tend = time_end
                tstartc = time_start - word_timestamp_correction
                tendc = time_end + word_timestamp_correction

                if time_handling_policy == "precise":
                    if word.start >= tstart and word.end <= tend:
                        new_words.append(word)
                        break
                elif time_handling_policy == "forgiving":
                    if intervals_overlap(word.start, word.end, tstartc, tendc):
                        new_words.append(word)
                        break
                elif time_handling_policy == "balanced":
                    if intervals_overlap(word.start, word.end, tstart, tend):
                        new_words.append(word)
                        break
                else:
                    if word.start >= tstartc and word.end <= tendc:
                        new_words.append(word)
                        break
        return new_words
    return words


def filter_by_speaker(
    speaker_number,
    words,
    speakers
):
    """
    Filters words based on the specified speaker number
    from a list of speakers.
    """

    if len(speaker_number) > 0:
        new_words = []
        for speaker_index, speaker in enumerate(speakers, start=1):
            if str(speaker_index) == speaker_number:

                print("filtering words by speaker number "
                      f"{speaker_number}..."
                      )
                for word in words:
                    middle_word = (word.start + word.end) / 2
                    for segment in speaker["segments"]:
                        if segment["start"] <= middle_word <= segment["end"]:
                            new_words.append(word)
                            break
        return new_words
    return words


def get_processing_times(
    time_files,
    download_sub_directory,
    limit_start_time,
    limit_end_time,
    duration
):
    """
    Determines time ranges for processing based on time files
    or specified start/end times.
    """

    limit_times = None
    processing_start = 0
    processing_end = duration

    if time_files:
        limit_times = []
        for time_file in time_files:
            time_file_path = join(download_sub_directory, time_file)

            print(f"processing time file {time_file_path}...")
            limit_times.extend(import_time_file(time_file_path))

        print("processing will be limited to the following time ranges:")
        for single_time in limit_times:
            start_time, end_time = single_time
            print(f"[{start_time}s - {end_time}s] ", end="", flush=True)

        print()
    elif limit_start_time and limit_end_time:
        limit_start_time = time_to_seconds(limit_start_time)
        limit_end_time = time_to_seconds(limit_end_time)

        processing_start = limit_start_time
        processing_end = limit_end_time

        print(f"both start and end time specified, processing from "
              f"{limit_start_time:.1f} to {limit_end_time:.1f}"
              )
        limit_times = [(limit_start_time, limit_end_time)]
    elif limit_start_time:
        limit_start_time = time_to_seconds(limit_start_time)
        processing_start = limit_start_time

        print("start time specified, processing from "
              f"{limit_start_time:.1f} "
              f"to end (duration: {duration:.1f}s)"
              )
        limit_times = [(limit_start_time, duration)]
    elif limit_end_time:
        limit_end_time = time_to_seconds(limit_end_time)
        processing_end = limit_end_time

        print("end time specified, processing from start "
              f"to {limit_end_time:.1f}"
              )
        limit_times = [(0, limit_end_time)]

    return limit_times, processing_start, processing_end


def process_filename(filename: str) -> str:
    """
    Process a given filename by removing '_audio', filtering out special
    characters, replacing spaces with underscores, and truncating to 50
    characters. Renames the file if changes are made.

    :param filename: The original filename to process.
    :return: The processed filename.
    """
    # Split basename from extension
    basename, extension = os.path.splitext(filename)

    # Remove "_audio"
    basename = basename.replace("_audio", "")

    # Filter special characters and multiple spaces
    basename = ''.join(char if char.isalnum() or char.isspace() else ' '
                       for char in basename)
    basename = ' '.join(basename.split())

    # Replace spaces with underscores
    basename = basename.replace(' ', '_')

    # Limit to 50 characters
    basename = basename[:50]

    # Recreate the new filename with extension
    new_filename = f"{basename}{extension}"

    # Rename the original file to the new filename
    if filename == new_filename:
        return filename

    if os.path.exists(new_filename):
        print(f"file '{new_filename}' already exists, "
              "skipping renaming..."
              )
        return new_filename

    print(f"renaming file '{filename}'")
    print(f"to new file name '{new_filename}'")
    os.rename(filename, new_filename)

    return new_filename

import json
from word import Word
def load_words(file_path):
    """
    从文件加载单词数据。
    
    :param file_path: 包含单词数据的文件路径
    :return: Word对象列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        words_dicts = json.load(f)
    
    return [Word(**word_dict) for word_dict in words_dicts]

from segment import Segment
def load_transcription_data(directory):
    """
    从目录中加载转录数据。
    
    :param directory: 包含转录数据的目录路径
    :return: 包含单词和转录段落的列表
    """
    
    with open(os.path.join(directory, "vocals_transcript.json"), 'r', encoding='utf-8') as f:
        transcribed_segments = json.load(f)
    keys_to_keep = ['start', 'end', 'text']
    return [Segment(**{key: seg_dict[key] for key in keys_to_keep if key in seg_dict}) for seg_dict in transcribed_segments['segments']] 

import json

def save_transcription_data(words, transcribed_segments, directory):
    with open(os.path.join(directory, "words.txt"), 'w', encoding='utf-8') as f:
        json.dump([word.__dict__ for word in words], f, ensure_ascii=False, indent=2)
    
    # 确保 transcribed_segments 是可序列化的
    serializable_segments = []
    for segment in transcribed_segments:
        if isinstance(segment, str):
            serializable_segments.append(segment)
        elif isinstance(segment, dict):
            serializable_segments.append(segment)
        else:
            serializable_segments.append({
                "text": getattr(segment, "text", ""),
                "start": getattr(segment, "start", None),
                "end": getattr(segment, "end", None),
            })
    
    with open(os.path.join(directory, "transcribed_segments.json"), 'w', encoding='utf-8') as f:
        json.dump(serializable_segments, f, ensure_ascii=False, indent=2)

# load_transcription_data 函数保持不变
