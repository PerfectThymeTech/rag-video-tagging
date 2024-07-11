import logging

from azure.identity import DefaultAzureCredential
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from models.newstagextraction import InvokeLlmResponse, LlmResponseItem
from shared.config import settings


class LlmMessages:
    SYSTEM_MESSAGE: str = settings.NEWSTAGEXTRACTION_SYSTEM_PROMPT
    USER_MESSAGE: str = settings.NEWSTAGEXTRACTION_USER_PROMPT


class LlmInteractor:
    def __init__(
        self,
        azure_open_ai_base_url: str,
        azure_open_ai_api_version: str,
        azure_open_ai_deployment_name: str,
        azure_open_ai_temperature: float,
    ) -> None:
        # Create llm chain
        self.__create_llm_chain(
            azure_open_ai_base_url=azure_open_ai_base_url,
            azure_open_ai_api_version=azure_open_ai_api_version,
            azure_open_ai_deployment_name=azure_open_ai_deployment_name,
            azure_open_ai_temperature=azure_open_ai_temperature,
        )

    def __create_llm_chain(
        self,
        azure_open_ai_base_url: str,
        azure_open_ai_api_version: str,
        azure_open_ai_deployment_name: str,
        azure_open_ai_temperature: float,
    ) -> None:
        # Create chat prompt template
        logging.debug("Creating chat prompt template")
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=LlmMessages.SYSTEM_MESSAGE, type="system"),
                ("user", LlmMessages.USER_MESSAGE),
            ],
        )
        prompt.input_variables = [
            "format_sample",
            "news_content",
            "language",
            "news_show_details",
        ]

        # Create the llm
        logging.debug("Creating the llm")

        def entra_id_token_provider():
            credential = DefaultAzureCredential()
            token = credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            ).token
            return token

        llm = AzureChatOpenAI(
            azure_endpoint=azure_open_ai_base_url,
            api_version=azure_open_ai_api_version,
            deployment_name=azure_open_ai_deployment_name,
            azure_ad_token_provider=entra_id_token_provider,
            temperature=azure_open_ai_temperature,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

        # Create the output parser
        logging.debug("Creating the output parser")
        output_parser = JsonOutputParser(pydantic_object=InvokeLlmResponse)

        # Insert partial into prompt
        item1 = LlmResponseItem(
            id=1,
            title="Title of the first section",
            tags=["tag-1", "tag-2", "tag-3"],
            score=9,
            start="First sentence of the first section",
            end="Last sentence of the first section",
        )
        item2 = LlmResponseItem(
            id=2,
            title="Title of the second section",
            tags=["tag-1", "tag-2", "tag-3"],
            score=7,
            start="First sentence of the second section",
            end="Last sentence of the second section",
        )
        item3 = LlmResponseItem(
            id=3,
            title="Title of the third section",
            tags=["tag-1", "tag-2", "tag-3"],
            score=8,
            start="First sentence of the third section",
            end="Last sentence of the third section",
        )
        format_sample = InvokeLlmResponse(root=[item1, item2, item3])
        prompt_partial = prompt.partial(
            format_sample=format_sample.model_dump_json(),
        )
        logging.debug(f"Prompt: {prompt.json()}")

        # Create chain
        logging.debug("Creating the llm chain")
        self.__llm_chain = prompt_partial | llm | output_parser

    def invoke_llm_chain(
        self,
        news_content: str,
        news_show_details: str,
        language: str,
    ) -> InvokeLlmResponse:
        result: InvokeLlmResponse = self.__llm_chain.invoke(
            {
                "news_content": news_content,
                "news_show_details": news_show_details,
                "language": language,
            },
        )
        return result
