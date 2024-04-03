import json
import logging
import os
from typing import Any, Dict

import azure.durable_functions as df
from models.videoextraction import VideoExtractionOrchestratorRequest
from moviepy.editor import VideoFileClip
from pydantic import TypeAdapter
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
    input_download_video = {
        "storage_domain_name": payload_obj.content_url.host,
        "storage_container_name": payload_obj.content_url.path.split("/")[1],
        "storage_blob_name": "/".join(payload_obj.content_url.path.split("/")[2:]),
        "instance_id": context.instance_id,
    }
    result_download_video = yield context.call_activity(
        "download_video", json.dumps(input_download_video)
    )

    # Extract video clips
    logging.info("Extract video clips")
    tasks_extract_video_clip = []
    for timestamp in payload_obj.timestamps:
        input_extract_video_clip = {
            "video_file_path": result_download_video,
            "instance_id": context.instance_id,
            "start": timestamp.start,
            "offset": timestamp.offset,
        }
        tasks_extract_video_clip.append(
            context.call_activity(
                "extract_video_clip", json.dumps(input_extract_video_clip)
            )
        )
    results_extract_video_clip = yield context.task_all(tasks_extract_video_clip)

    # Upload video clip
    logging.info("Upload video clips")
    tasks_upload_video_clips = []
    for video_clip in results_extract_video_clip:
        input_upload_video = {
            "video_file_path": video_clip,
            "instance_id": context.instance_id,
            "storage_domain_name": settings.STORAGE_DOMAIN_NAME,
            "storage_container_name": settings.STORAGE_ACCOUNT_CONTAINER,
        }
        tasks_upload_video_clips.append(
            context.call_activity("upload_video", json.dumps(input_upload_video))
        )
    results_upload_video = yield context.task_all(tasks_upload_video_clips)

    # Delete Video test
    logging.info("Deleting video")
    input_delete_video = {
        "video_file_path": result_download_video,
        "instance_id": context.instance_id,
    }
    _ = yield context.call_activity("delete_video", json.dumps(input_delete_video))

    return results_upload_video


@bp.activity_trigger(input_name="inputJson")  # , activity="ExtractVideoClip")
def extract_video_clip(inputJson: str):
    logging.info(f"Extract video input: {inputJson}")

    # Parse input
    input_data_dict = json.loads(inputJson)
    try:
        video_file_path = input_data_dict.get("video_file_path")
        instance_id = input_data_dict.get("instance_id")
        start_in_secs = int(float(input_data_dict.get("start")))
        offset_in_secs = int(float(input_data_dict.get("offset")))

        if (
            not video_file_path
            or not start_in_secs
            or not offset_in_secs
            or not instance_id
        ):
            raise ValueError()
    except ValueError:
        raise ValueError(
            "Input values provided for 'video_file_path', 'instance_id', 'start' or 'offset' are not available or cannot be converted to type int."
        )

    # Extract video clip
    video = VideoFileClip(video_file_path)
    video_clip = video.subclip(start_in_secs, start_in_secs + offset_in_secs)

    # Create folder
    video_clip_folder_path = os.path.join(
        settings.HOME_DIRECTORY, instance_id, "video_clips"
    )
    if not os.path.exists(video_clip_folder_path):
        os.makedirs(video_clip_folder_path)

    # Save video clip
    video_clip_file_type = str.split(video_file_path, ".")[-1]
    video_clip_file_name = (
        f"video_{start_in_secs}_{offset_in_secs}.{video_clip_file_type}"
    )
    video_clip_file_path = os.path.join(video_clip_folder_path, video_clip_file_name)
    current_working_path = os.getcwd()
    os.chdir(video_clip_folder_path)
    video_clip.write_videofile(video_clip_file_name)
    os.chdir(current_working_path)

    return video_clip_file_path


@bp.activity_trigger(input_name="inputJson")  # , activity="DownloadVideo")
async def download_video(inputJson: str) -> str:
    logging.info(f"Download video input: {inputJson}")

    # Parse input
    input_data_dict = json.loads(inputJson)
    try:
        storage_domain_name = input_data_dict.get("storage_domain_name")
        storage_container_name = input_data_dict.get("storage_container_name")
        storage_blob_name = input_data_dict.get("storage_blob_name")
        instance_id = input_data_dict.get("instance_id")

        if (
            not storage_domain_name
            or not storage_container_name
            or not storage_blob_name
            or not instance_id
        ):
            raise ValueError()
    except ValueError:
        raise ValueError("Input values inconsistent or not provided.")

    # Create file path
    blob_file_type = str.split(storage_blob_name, ".")[-1]
    download_file_name = f"video.{blob_file_type}"
    download_file_folder = os.path.join(
        settings.HOME_DIRECTORY, instance_id, "original_video"
    )
    download_file_path = os.path.join(download_file_folder, download_file_name)
    if not os.path.exists(download_file_folder):
        os.makedirs(download_file_folder)

    # Download file
    result_download_blob = await utils.download_blob(
        file_path=download_file_path,
        storage_domain_name=storage_domain_name,
        storage_container_name=storage_container_name,
        storage_blob_name=storage_blob_name,
    )

    return result_download_blob


@bp.activity_trigger(input_name="inputJson")  # , activity="UploadVideo")
async def upload_video(inputJson: str):
    logging.info(f"Upload video input: {inputJson}")

    # Parse input
    input_data_dict = json.loads(inputJson)
    try:
        video_file_path = input_data_dict.get("video_file_path")
        storage_domain_name = input_data_dict.get("storage_domain_name")
        storage_container_name = input_data_dict.get("storage_container_name")
        instance_id = input_data_dict.get("instance_id")

        if not storage_domain_name or not storage_container_name or not instance_id:
            raise ValueError()
    except ValueError:
        raise ValueError("Input values inconsistent or not provided.")

    # Define file name of blob
    storage_blob_name = os.path.join(instance_id, os.path.basename(video_file_path))

    # Upload file
    result_upload_file = await utils.upload_blob(
        file_path=video_file_path,
        storage_domain_name=storage_domain_name,
        storage_container_name=storage_container_name,
        storage_blob_name=storage_blob_name,
    )

    return result_upload_file


@bp.activity_trigger(input_name="inputJson")  # , activity="DeleteVideo")
async def delete_video(inputJson: str):
    logging.info(f"Delete video input: {inputJson}")

    # Parse input
    input_data_dict = json.loads(inputJson)
    try:
        video_file_path = input_data_dict.get("video_file_path")
        instance_id = input_data_dict.get("instance_id")

        if not video_file_path or not instance_id:
            raise ValueError()
    except ValueError:
        raise ValueError("Input values inconsistent or not provided.")

    # Define folder path
    folder_path = os.path.join(settings.HOME_DIRECTORY, instance_id)

    # Remove folder recursively
    utils.delete_directory(directory_path=folder_path)
    return True
