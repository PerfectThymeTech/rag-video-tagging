import json
import logging
import os
from typing import Any, Dict

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
        result_llm=result_invoke_llm.root,
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
        storage_blob_name=os.path.join(inputData.instance_id, "transcript.json"),
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
    )
    llm_result: Dict[Any] = llm_ineractor.invoke_llm_chain(
        news_content=inputData.content_text,
        news_show_details=inputData.content_details,
    )
    logging.info(f"LLM response: {json.dumps(llm_result)}")

    # Generate response
    response: InvokeLlmResponse = InvokeLlmResponse(root=llm_result)

    # Upload result
    await utils.upload_string(
        data=response.model_dump_json(),
        storage_domain_name=settings.STORAGE_DOMAIN_NAME,
        storage_container_name=settings.STORAGE_CONTAINER_NAME,
        storage_blob_name=os.path.join(inputData.instance_id, "llm.json"),
    )

    return response


@bp.activity_trigger(input_name="inputData")  # , activity="InvokeLlm")
async def compute_timestamps(
    inputData: ComputeTimestampsRequest,
) -> ComputeTimestampsResponse:
    # Configure index
    result_llm_index = 0
    result_llm_item_start = True

    # Configure current item
    result_llm_current_words = timestamps.get_cleansed_llm_response_item(
        list=inputData.result_llm, index=result_llm_index, start=result_llm_item_start
    )

    # Generate response
    response: ComputeTimestampsResponse = ComputeTimestampsResponse(root=[])
    response_item = ComputeTimestampsItem(
        title=inputData.result_llm[result_llm_index].title,
        tags=inputData.result_llm[result_llm_index].tags,
        score=inputData.result_llm[result_llm_index].score,
        start_time="",
        end_time="",
    )

    # Loop through transcript items
    for i, item in enumerate(inputData.result_video_indexer):
        # Split item into words
        item_words = timestamps.cleanse_text(text=item.text)

        # Loop through words
        for j, item_word in enumerate(item_words):
            # print(f"Response: {response.model_dump_json()}")
            # print(f"Item: {response_item.model_dump_json()}")
            # print(f"LLM Current Words: {result_llm_current_words}")
            # print(f"item word: {item_word}")

            if item_word == result_llm_current_words[0]:
                # Create list of next words
                remaining_words = item_words[j:]
                num_words_missing = len(result_llm_current_words) - len(remaining_words)
                start_time = item.instances[0].start
                end_time = item.instances[0].end

                if num_words_missing > 0 and (i + 1) < len(
                    inputData.result_video_indexer
                ):
                    next_item = inputData.result_video_indexer[i + 1]
                    next_item_words = timestamps.cleanse_text(text=next_item.text)

                    # Update values for comparison
                    remaining_words.extend(next_item_words[:num_words_missing])
                    end_time = next_item.instances[0].end

                # print(f"Remaining: {remaining_words}")
                # Compute whether following items are identical
                identical = [
                    word_llm == remaining_words[k]
                    for k, word_llm in enumerate(result_llm_current_words)
                ]
                all_identical = all(identical)

                if all_identical:
                    # Update response & index
                    if result_llm_item_start:
                        # Update index
                        result_llm_item_start = False

                        # Update response
                        response_item.start_time = start_time
                    else:
                        # Update index
                        result_llm_item_start = True
                        result_llm_index += 1

                        # Update response
                        response_item.end_time = end_time
                        response.root.append(response_item)

                        if result_llm_index >= len(inputData.result_llm):
                            break

                        response_item = ComputeTimestampsItem(
                            title=inputData.result_llm[result_llm_index].title,
                            tags=inputData.result_llm[result_llm_index].tags,
                            score=inputData.result_llm[result_llm_index].score,
                            start_time="",
                            end_time="",
                        )

                    # Update current item
                    result_llm_current_words = (
                        timestamps.get_cleansed_llm_response_item(
                            list=inputData.result_llm,
                            index=result_llm_index,
                            start=result_llm_item_start,
                        )
                    )

        if result_llm_index >= len(inputData.result_llm):
            break

    # Upload result
    await utils.upload_string(
        data=response.model_dump_json(),
        storage_domain_name=settings.STORAGE_DOMAIN_NAME,
        storage_container_name=settings.STORAGE_CONTAINER_NAME,
        storage_blob_name=os.path.join(inputData.instance_id, "timestamps.json"),
    )
    return response
