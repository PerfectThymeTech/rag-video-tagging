import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import azure.durable_functions as df
from models.error import ErrorModel
from models.videoextraction import (
    ContentOpenAi,
    DeleteVideoRequest,
    ExtractVideoClipRequest,
    ExtractVideoClipResponse,
    LoadOpenaiContentRequest,
    LoadOpenaiContentResponse,
    LoadVideoContentRequest,
    LoadVideoContentResponse,
    UploadVideoRequest,
    UploadVideoResponse,
    VideoExtractionOrchestratorRequest,
    VideoExtractionOrchestratorResponse,
    VideoTimestamp,
)
from moviepy.editor import VideoFileClip
from pydantic import ValidationError
from shared import utils
from shared.config import settings

bp = df.Blueprint()


@bp.orchestration_trigger(
    context_name="context"
)  # , orchestration="VideoOrchestrator")
def video_extraction_orchestrator(context: df.DurableOrchestrationContext):
    # Define retry logic
    retry_options = df.RetryOptions(
        first_retry_interval_in_milliseconds=5000, max_number_of_attempts=3
    )

    # Parse payload
    utils.set_custom_status(
        context=context, completion_percentage=0.0, status="Parse Payload"
    )
    payload: Dict[str, Any] = context.get_input()
    logging.debug(f"Input Data loaded: '{payload}'")
    try:
        payload_obj: VideoExtractionOrchestratorRequest = (
            VideoExtractionOrchestratorRequest.model_validate(
                payload.get("orchestrator_workflow_properties")
            )
        )
        logging.debug(f"Data loaded: '{payload_obj}'")
    except ValidationError as e:
        logging.error(f"Validation Error occured for orchestrator payload: {e}")
        return ErrorModel(
            error_code=10,
            error_message="Provided input is not following the expected data model",
            error_details=json.loads(e.json()),
        ).model_dump()

    # Loading open ai content
    logging.info("Loading open ai content")
    utils.set_custom_status(
        context=context, completion_percentage=5.0, status="Loading open ai content"
    )
    input_load_openai_content: LoadOpenaiContentRequest = LoadOpenaiContentRequest(
        storage_domain_name=payload_obj.content_url_openai.host,
        storage_container_name=payload_obj.content_url_openai.path.split("/")[1],
        storage_blob_name="/".join(payload_obj.content_url_openai.path.split("/")[2:]),
        instance_id=context.instance_id,
    )
    result_load_openai_content: LoadOpenaiContentResponse = (
        yield context.call_activity_with_retry(
            name="load_openai_content",
            retry_options=retry_options,
            input_=input_load_openai_content,
        )
    )

    # Download video content
    logging.info("Downloading video content")
    utils.set_custom_status(
        context=context, completion_percentage=10.0, status="Downloading Video"
    )
    input_load_video_content: LoadVideoContentRequest = LoadVideoContentRequest(
        storage_domain_name=payload_obj.content_url_video.host,
        storage_container_name=payload_obj.content_url_video.path.split("/")[1],
        storage_blob_name="/".join(payload_obj.content_url_video.path.split("/")[2:]),
        instance_id=context.instance_id,
    )
    result_load_video_content: LoadVideoContentResponse = (
        yield context.call_activity_with_retry(
            name="load_video_content",
            retry_options=retry_options,
            input_=input_load_video_content,
        )
    )

    # Extract video clips
    logging.info("Extract video clips")
    utils.set_custom_status(
        context=context, completion_percentage=25.0, status="Extracting Video Clips"
    )
    tasks_extract_video_clip = []
    for video_timestamp in result_load_openai_content.video_timestamps:
        input_extract_video_clip: ExtractVideoClipRequest = ExtractVideoClipRequest(
            video_file_path=result_load_video_content.video_file_path,
            start_time=video_timestamp.start_time,
            end_time=video_timestamp.end_time,
            instance_id=context.instance_id,
        )
        tasks_extract_video_clip.append(
            context.call_activity_with_retry(
                name="extract_video_clip",
                retry_options=retry_options,
                input_=input_extract_video_clip,
            )
        )
    results_extract_video_clip: List[ExtractVideoClipResponse] = yield context.task_all(
        tasks_extract_video_clip
    )

    # Upload video clip
    logging.info("Upload video clips")
    utils.set_custom_status(
        context=context, completion_percentage=70.0, status="Uploading Video Clips"
    )
    tasks_upload_video_clips = []
    for video_clip in results_extract_video_clip:
        input_upload_video: UploadVideoRequest = UploadVideoRequest(
            video_file_path=video_clip.video_clip_file_path,
            start_time=video_clip.start_time,
            end_time=video_clip.end_time,
            instance_id=context.instance_id,
        )
        tasks_upload_video_clips.append(
            context.call_activity_with_retry(
                name="upload_video",
                retry_options=retry_options,
                input_=input_upload_video,
            )
        )
    results_upload_video: List[UploadVideoResponse] = yield context.task_all(
        tasks_upload_video_clips
    )

    # Delete Video test
    logging.info("Deleting video")
    utils.set_custom_status(
        context=context, completion_percentage=95.0, status="Cleanup tasks"
    )
    input_delete_video: DeleteVideoRequest = DeleteVideoRequest(
        instance_id=context.instance_id,
    )
    _ = yield context.call_activity_with_retry(
        "delete_video", retry_options=retry_options, input_=input_delete_video
    )

    # Create output
    utils.set_custom_status(
        context=context, completion_percentage=100.0, status="Completed"
    )
    result = VideoExtractionOrchestratorResponse(
        error_code=0, extracted_video_clips=results_upload_video
    )
    return json.loads(result.model_dump_json())


@bp.activity_trigger(input_name="inputData")  # , activity="ExtractTranscript")
async def load_openai_content(
    inputData: LoadOpenaiContentRequest,
) -> LoadOpenaiContentResponse:
    logging.info(f"Start loading open ai content")

    # Get json from blob storage
    data = await utils.load_blob(
        storage_domain_name=inputData.storage_domain_name,
        storage_container_name=inputData.storage_container_name,
        storage_blob_name=inputData.storage_blob_name,
        encoding="utf-8-sig",
    )
    logging.info(f"Loaded data from storage: {data}")
    try:
        data_obj: ContentOpenAi = ContentOpenAi.model_validate(json.loads(data))
        logging.debug(f"Data loaded: '{data_obj}'")
    except ValidationError as e:
        logging.error(f"Validation Error occured for open ai content payload: {e}")
        data_obj: ContentOpenAi = ContentOpenAi(summary="", scenes=[])
        # TODO: Handle errors
        # ErrorModel(
        #     error_code=20,
        #     error_message="Provided json file is not following the expected data model",
        #     error_details=json.loads(e.json()),
        # )

    # Generate response
    response: LoadOpenaiContentResponse = LoadOpenaiContentResponse(video_timestamps=[])
    for scene in data_obj.scenes:
        video_timestamp = VideoTimestamp(
            start_time=scene.start_time,
            end_time=scene.end_time,
        )
        response.video_timestamps.append(video_timestamp)

    return response


@bp.activity_trigger(input_name="inputData")  # , activity="DownloadVideo")
async def load_video_content(
    inputData: LoadVideoContentRequest,
) -> LoadVideoContentResponse:
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

    # TODO: Handle errors

    # Generate response
    response = LoadVideoContentResponse(video_file_path=result_download_blob)
    return response


@bp.activity_trigger(input_name="inputData")  # , activity="ExtractVideoClip")
def extract_video_clip(inputData: ExtractVideoClipRequest) -> ExtractVideoClipResponse:
    logging.info(f"Starting video clip extraction activity")

    # Calculate start and end in secs
    start_in_secs: float = (
        datetime.combine(datetime.min, inputData.start_time) - datetime.min
    ).total_seconds()
    start_in_secs: int = int(start_in_secs)
    end_in_secs: float = (
        datetime.combine(datetime.min, inputData.end_time) - datetime.min
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

    # Generate response
    response = ExtractVideoClipResponse(
        video_clip_file_path=video_clip_file_path,
        start_time=inputData.start_time,
        end_time=inputData.end_time,
    )
    return response


@bp.activity_trigger(input_name="inputData")  # , activity="UploadVideo")
async def upload_video(inputData: UploadVideoRequest) -> UploadVideoResponse:
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

    # Generate response
    response = UploadVideoResponse(
        content_url_videoclip=result_upload_file,
        start_time=inputData.start_time,
        end_time=inputData.end_time,
    )
    return response


@bp.activity_trigger(input_name="inputData")  # , activity="DeleteVideo")
async def delete_video(inputData: DeleteVideoRequest):
    logging.info(f"Starting delete video activity")

    # Define folder path
    folder_path = os.path.join(settings.HOME_DIRECTORY, inputData.instance_id)

    # Remove folder recursively
    utils.delete_directory(directory_path=folder_path)
    return True
