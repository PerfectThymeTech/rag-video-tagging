import json
import logging
from typing import Any, Dict

import azure.durable_functions as df
from models.error import ErrorModel
from models.newstagextraction import (
    ExtractTranscriptRequest,
    NewsTagExtractionOrchestratorRequest,
    VideoIndexerTranscript,
)
from pydantic import ValidationError
from shared import utils

bp = df.Blueprint()


@bp.orchestration_trigger(
    context_name="context"
)  # , orchestration="NewsTagOrchestrator")
def newstag_extraction_orchestrator(context: df.DurableOrchestrationContext):
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
        payload_obj: NewsTagExtractionOrchestratorRequest = (
            NewsTagExtractionOrchestratorRequest.model_validate(
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

    # Extract transcript from video indexer data
    logging.info("Extract transcript from video indexer data")
    utils.set_custom_status(
        context=context,
        completion_percentage=5.0,
        status="Extract transcript from video indexer data",
    )
    input_extract_transcript: ExtractTranscriptRequest = ExtractTranscriptRequest(
        storage_domain_name=payload_obj.content_url.host,
        storage_container_name=payload_obj.content_url.path.split("/")[1],
        storage_blob_name="/".join(payload_obj.content_url.path.split("/")[2:]),
        instance_id=context.instance_id,
    )
    result_extract_transcript: VideoIndexerTranscript = (
        yield context.call_activity_with_retry(
            name="extract_transcript",
            retry_options=retry_options,
            input_=input_extract_transcript,
        )
    )

    # TODO: Interact with GPT3 or GPT4
    # TODO: Generate timestamps

    # Create output
    utils.set_custom_status(
        context=context, completion_percentage=100.0, status="Completed"
    )
    result = {"error_code": 0, "text": ""}
    return result


@bp.activity_trigger(input_name="inputData")  # , activity="ExtractTranscript")
async def extract_transcript(
    inputData: ExtractTranscriptRequest,
) -> VideoIndexerTranscript:
    logging.info(f"Starting transcript extraction activity")

    # Get json from blob storage
    data = await utils.load_blob(
        storage_domain_name=inputData.storage_domain_name,
        storage_container_name=inputData.storage_container_name,
        storage_blob_name=inputData.storage_blob_name,
    )
    logging.info(f"Loaded data from storage: {data}")
    data_json = json.loads(data)
    logging.info(f"Loaded json data from storage: {data_json}")

    # Generate Transcript fom JSON
    transcript_text_list = []
    transcript = (
        data_json.get("videos", {"insights": {"transcript": []}})
        .get("insights", {"transcript": []})
        .get("transcript", [])
    )
    for item in transcript:
        text = item.get("text")
        transcript_text_list.append(text)

    transcript_text_list_cleaned = [item for item in transcript_text_list if item]
    transcript_text = " ".join(transcript_text_list_cleaned).strip()

    # Return video indexer transcript object
    video_indexer_transcript: VideoIndexerTranscript = VideoIndexerTranscript(
        transcript_text=transcript_text, transcript=transcript
    )
    return video_indexer_transcript
