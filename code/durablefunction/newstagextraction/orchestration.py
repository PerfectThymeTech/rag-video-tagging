import itertools
import json
import logging
import os
from typing import Any, Dict, List

import azure.durable_functions as df
from models.error import ErrorModel
from models.newstagextraction import (
    ComputeTimestampsItem,
    ComputeTimestampsRequest,
    ComputeTimestampsResponse,
    InvokeLlmRequest,
    InvokeLlmResponse,
    LoadVideoindexerContentRequest,
    LoadVideoindexerContentResponse,
    NewsTagExtractionOrchestratorRequest,
)
from newstagextraction import timestamps
from newstagextraction.llm import LlmInteractor
from pydantic import ValidationError
from shared import utils
from shared.config import settings

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
    input_load_videoindexer_content: LoadVideoindexerContentRequest = (
        LoadVideoindexerContentRequest(
            storage_domain_name=payload_obj.content_url_videoindexer.host,
            storage_container_name=payload_obj.content_url_videoindexer.path.split("/")[
                1
            ],
            storage_blob_name="/".join(
                payload_obj.content_url_videoindexer.path.split("/")[2:]
            ),
            instance_id=context.instance_id,
        )
    )
    result_load_videoindexer_content: LoadVideoindexerContentResponse = (
        yield context.call_activity_with_retry(
            name="load_videoindexer_content",
            retry_options=retry_options,
            input_=input_load_videoindexer_content,
        )
    )

    # Invoke LLM to detect news scenes
    logging.info("Invoke LLM to detect news scenes")
    utils.set_custom_status(
        context=context,
        completion_percentage=15.0,
        status="Detect scenes using Azure Open AI",
    )
    input_invoke_llm: InvokeLlmRequest = InvokeLlmRequest(
        content_text=result_load_videoindexer_content.transcript_text,
        content_details="This is a tv news show.",
        instance_id=context.instance_id,
    )
    result_invoke_llm: InvokeLlmResponse = yield context.call_activity_with_retry(
        name="invoke_llm",
        retry_options=retry_options,
        input_=input_invoke_llm,
    )

    # Compute timestamps
    logging.info("Compute timestamps")
    utils.set_custom_status(
        context=context,
        completion_percentage=15.0,
        status="Compute timestamps",
    )
    input_compute_timestamps: ComputeTimestampsRequest = ComputeTimestampsRequest(
        result_video_indexer=result_load_videoindexer_content.transcript,
        result_llm=result_invoke_llm.sections,
        instance_id=context.instance_id,
    )
    result_compute_timestamps: ComputeTimestampsResponse = (
        yield context.call_activity_with_retry(
            name="compute_timestamps",
            retry_options=retry_options,
            input_=input_compute_timestamps,
        )
    )

    # TODO: Get scene images from Video Indexer

    # Create output
    utils.set_custom_status(
        context=context, completion_percentage=100.0, status="Completed"
    )
    result = {"error_code": 0, "text": result_compute_timestamps.model_dump()}
    return result


@bp.activity_trigger(input_name="inputData")  # , activity="ExtractTranscript")
async def load_videoindexer_content(
    inputData: LoadVideoindexerContentRequest,
) -> LoadVideoindexerContentResponse:
    logging.info(f"Starting transcript extraction activity")

    # Get json from blob storage
    data = await utils.load_blob(
        storage_domain_name=inputData.storage_domain_name,
        storage_container_name=inputData.storage_container_name,
        storage_blob_name=inputData.storage_blob_name,
        encoding="utf-8-sig",
    )
    logging.info(f"Loaded data from storage: {data}")
    data_json = json.loads(data)
    logging.info(f"Loaded json data from storage: {data_json}")

    # TODO: Handle errors

    # Generate Transcript fom JSON
    transcript_text_list = []
    transcript_list = []
    try:
        transcript = (
            data_json.get("videos", [{"insights": {"transcript": []}}])
            .pop(0)
            .get("insights", {"transcript": []})
            .get("transcript", [])
        )
    except IndexError as e:
        logging.error(
            f"Index error when loading the video indexer data, so setting empty transcript: '{e}'"
        )
        transcript = []

    # Filter items in transcript
    for item in transcript:
        if item.get("speakerId", None):
            text = item.get("text")
            transcript_text_list.append(text)
            transcript_list.append(item)

    transcript_text_list_cleaned = [item for item in transcript_text_list if item]
    transcript_text = " ".join(transcript_text_list_cleaned).strip()

    # Generate response: video indexer transcript object
    logging.info(f"Loaded transcript text: {transcript_text}")
    logging.info(f"Loaded transcript items: {len(transcript_list)}")
    response: LoadVideoindexerContentResponse = LoadVideoindexerContentResponse(
        transcript_text=transcript_text, transcript=transcript_list
    )

    # Upload result
    await utils.upload_string(
        data=response.model_dump_json(),
        storage_domain_name=settings.STORAGE_DOMAIN_NAME,
        storage_container_name=settings.STORAGE_CONTAINER_NAME,
        storage_blob_name=os.path.join(
            settings.NEWSTAGEXTRACTION_ROOT_FOLDER_NAME,
            inputData.instance_id,
            "transcript.json",
        ),
    )

    return response


@bp.activity_trigger(input_name="inputData")  # , activity="InvokeLlm")
async def invoke_llm(inputData: InvokeLlmRequest) -> InvokeLlmResponse:
    # Invoke llm
    logging.info("Starting to invoke llm")
    llm_ineractor = LlmInteractor(
        azure_open_ai_base_url=settings.AZURE_OPEN_AI_BASE_URL,
        azure_open_ai_api_version=settings.AZURE_OPEN_AI_API_VERSION,
        azure_open_ai_deployment_name=settings.AZURE_OPEN_AI_DEPLOYMENT_NAME,
        azure_open_ai_temperature=settings.AZURE_OPEN_AI_TEMPERATURE,
    )
    llm_result: Dict[Any] = llm_ineractor.invoke_llm_chain(
        news_content=inputData.content_text,
        news_show_details=inputData.content_details,
    )
    logging.info(f"LLM response: {json.dumps(llm_result)}")

    # Generate response
    response: InvokeLlmResponse = InvokeLlmResponse.model_validate(llm_result)

    # Upload result
    await utils.upload_string(
        data=response.model_dump_json(),
        storage_domain_name=settings.STORAGE_DOMAIN_NAME,
        storage_container_name=settings.STORAGE_CONTAINER_NAME,
        storage_blob_name=os.path.join(
            settings.NEWSTAGEXTRACTION_ROOT_FOLDER_NAME,
            inputData.instance_id,
            "llm.json",
        ),
    )

    return response


@bp.activity_trigger(input_name="inputData")  # , activity="InvokeLlm")
async def compute_timestamps(
    inputData: ComputeTimestampsRequest,
) -> ComputeTimestampsResponse:
    # Generate response
    response: ComputeTimestampsResponse = ComputeTimestampsResponse(root=[])

    # Preprocess video indexer result
    for vi_item in inputData.result_video_indexer:
        vi_item.text = timestamps.remove_punctuation(vi_item.text)

    # Loop through llm results
    for llm_item in inputData.result_llm:
        # Loop through scenes
        llm_item_start = timestamps.remove_punctuation(llm_item.start)
        llm_item_end = timestamps.remove_punctuation(llm_item.end)
        start_time = "None"
        end_time = "None"

        # Check start time
        start_res = [
            False
            for val in itertools.takewhile(
                lambda vi_item: llm_item_start not in vi_item.text,
                inputData.result_video_indexer,
            )
        ]
        index_start_res = len(start_res)

        # Check end time
        end_res = [
            False
            for val in itertools.takewhile(
                lambda vi_item: llm_item_end not in vi_item.text,
                inputData.result_video_indexer[index_start_res:],
            )
        ]
        index_end_res = len(end_res)

        # Update timestamps
        if index_start_res < len(
            inputData.result_video_indexer
        ) and index_start_res + index_end_res < len(inputData.result_video_indexer):
            start_time = (
                inputData.result_video_indexer[index_start_res].instances[0].start
            )
            end_time = (
                inputData.result_video_indexer[index_start_res + index_end_res]
                .instances[0]
                .end
            )

        # Add item to response
        response_item = ComputeTimestampsItem(
            title=llm_item.title,
            tags=llm_item.tags,
            score=llm_item.score,
            start_time=start_time,
            end_time=end_time,
        )
        response.root.append(response_item)

    # Upload result
    await utils.upload_string(
        data=response.model_dump_json(),
        storage_domain_name=settings.STORAGE_DOMAIN_NAME,
        storage_container_name=settings.STORAGE_CONTAINER_NAME,
        storage_blob_name=os.path.join(
            settings.NEWSTAGEXTRACTION_ROOT_FOLDER_NAME,
            inputData.instance_id,
            "timestamps.json",
        ),
    )
    return response
