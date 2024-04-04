import logging
import os
from datetime import datetime
from typing import Any, Dict

import azure.durable_functions as df
from models.videoextraction import (
    DeleteVideoRequest,
    DownloadVideoRequest,
    ExtractVideoClipRequest,
    UploadVideoRequest,
    VideoExtractionOrchestratorRequest,
)
from moviepy.editor import VideoFileClip
from shared import utils
from shared.config import settings

bp = df.Blueprint()


@bp.orchestration_trigger(
    context_name="context"
)  # , orchestration="VideoOrchestrator")
def video_extraction_orchestrator(context: df.DurableOrchestrationContext):
    # Parse payload
    payload: Dict[str, Any] = context.get_input()
    logging.info(f"Input Data loaded: '{payload}'")
    payload_obj: VideoExtractionOrchestratorRequest = (
        VideoExtractionOrchestratorRequest.model_validate(
            payload.get("orchestrator_workflow_properties")
        )
    )
    logging.info(f"Data loaded: '{payload_obj}'")

    # Download Video Test
    logging.info("Downloading video")
    input_download_video: DownloadVideoRequest = DownloadVideoRequest(
        storage_domain_name=payload_obj.content_url.host,
        storage_container_name=payload_obj.content_url.path.split("/")[1],
        storage_blob_name="/".join(payload_obj.content_url.path.split("/")[2:]),
        instance_id=context.instance_id,
    )
    result_download_video = yield context.call_activity(
        "download_video", input_download_video
    )

    # Extract video clips
    logging.info("Extract video clips")
    tasks_extract_video_clip = []
    for timestamp in payload_obj.timestamps:
        input_extract_video_clip: ExtractVideoClipRequest = ExtractVideoClipRequest(
            video_file_path=result_download_video,
            start=timestamp.start,
            end=timestamp.end,
            instance_id=context.instance_id,
        )
        tasks_extract_video_clip.append(
            context.call_activity("extract_video_clip", input_extract_video_clip)
        )
    results_extract_video_clip = yield context.task_all(tasks_extract_video_clip)

    # Upload video clip
    logging.info("Upload video clips")
    tasks_upload_video_clips = []
    for video_clip in results_extract_video_clip:
        input_upload_video: UploadVideoRequest = UploadVideoRequest(
            video_file_path=video_clip,
            instance_id=context.instance_id,
        )
        tasks_upload_video_clips.append(
            context.call_activity("upload_video", input_upload_video)
        )
    results_upload_video = yield context.task_all(tasks_upload_video_clips)

    # Delete Video test
    logging.info("Deleting video")
    input_delete_video: DeleteVideoRequest = DeleteVideoRequest(
        instance_id=context.instance_id,
    )
    _ = yield context.call_activity("delete_video", input_delete_video)

    # Create output
    result = {"extracted_video_clips": results_upload_video}
    return result


@bp.activity_trigger(input_name="inputData")  # , activity="ExtractVideoClip")
def extract_video_clip(inputData: ExtractVideoClipRequest):
    logging.info(f"Starting video clip extraction activity")

    # Calculate start and end in secs
    start_in_secs: float = (
        datetime.combine(datetime.min, inputData.start) - datetime.min
    ).total_seconds()
    start_in_secs: int = int(start_in_secs)
    end_in_secs: float = (
        datetime.combine(datetime.min, inputData.end) - datetime.min
    ).total_seconds()
    end_in_secs: int = int(end_in_secs + 1)
    logging.info(
        f"Extracting video clip from {start_in_secs}s to {end_in_secs}s from {inputData.video_file_path}."
    )

    # Extract video clip
    video = VideoFileClip(inputData.video_file_path)
    video_clip = video.subclip(start_in_secs, end_in_secs)

    # Create folder
    video_clip_folder_path = os.path.join(
        settings.HOME_DIRECTORY, inputData.instance_id, "video_clips"
    )
    if not os.path.exists(video_clip_folder_path):
        os.makedirs(video_clip_folder_path)

    # Save video clip
    video_clip_file_type = str.split(inputData.video_file_path, ".")[-1]
    video_clip_file_name = f"video_{start_in_secs}_{end_in_secs}.{video_clip_file_type}"
    video_clip_file_path = os.path.join(video_clip_folder_path, video_clip_file_name)
    current_working_path = os.getcwd()
    os.chdir(video_clip_folder_path)
    video_clip.write_videofile(video_clip_file_name)
    os.chdir(current_working_path)

    return video_clip_file_path


@bp.activity_trigger(input_name="inputData")  # , activity="DownloadVideo")
async def download_video(inputData: DownloadVideoRequest) -> str:
    logging.info(f"Starting download video activity")

    # Create file path
    logging.info(f"Creating file path")
    blob_file_type = str.split(inputData.storage_blob_name, ".")[-1]
    download_file_name = f"video.{blob_file_type}"
    download_file_folder = os.path.join(
        settings.HOME_DIRECTORY, inputData.instance_id, "original_video"
    )
    download_file_path = os.path.join(download_file_folder, download_file_name)
    if not os.path.exists(download_file_folder):
        os.makedirs(download_file_folder)

    # Download file
    logging.info(f"Downloading video file")
    result_download_blob = await utils.download_blob(
        file_path=download_file_path,
        storage_domain_name=inputData.storage_domain_name,
        storage_container_name=inputData.storage_container_name,
        storage_blob_name=inputData.storage_blob_name,
    )

    return result_download_blob


@bp.activity_trigger(input_name="inputData")  # , activity="UploadVideo")
async def upload_video(inputData: UploadVideoRequest):
    logging.info(f"Starting upload video activity")

    # Define file name of blob
    storage_blob_name = os.path.join(
        inputData.instance_id, os.path.basename(inputData.video_file_path)
    )

    # Upload file
    result_upload_file = await utils.upload_blob(
        file_path=inputData.video_file_path,
        storage_domain_name=settings.STORAGE_DOMAIN_NAME,
        storage_container_name=settings.STORAGE_CONTAINER_NAME,
        storage_blob_name=storage_blob_name,
    )

    return result_upload_file


@bp.activity_trigger(input_name="inputData")  # , activity="DeleteVideo")
async def delete_video(inputData: DeleteVideoRequest):
    logging.info(f"Starting delete video activity")

    # Define folder path
    folder_path = os.path.join(settings.HOME_DIRECTORY, inputData.instance_id)

    # Remove folder recursively
    utils.delete_directory(directory_path=folder_path)
    return True
