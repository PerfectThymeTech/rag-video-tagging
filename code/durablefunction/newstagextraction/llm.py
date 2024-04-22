import logging

from azure.identity import DefaultAzureCredential
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from models.newstagextraction import InvokeLlmResponse, LlmResponseItem


class LlmMessages:
    SYSTEM_MESSAGE: str = """
    You are a world class assistant for summarizing news content.
    You extract subsections from the provided news content and generate a title for each subsection.
    For each subsection you provide a score between 0 and 10 indicating how good the defined tags match the content of the subsection. 0 indicates that the tags don't match the content, and 10 means that the tags are a perfect match.
    You must include the start and end of the original text for each subsection in the response. The text snippet describing the beginning and end should include 5 words.
    You add tags to each subsection. Samples for tags are: sports, weather, international news, national news, politics, crime, technology, celebrity, other. You add additional tags based on the content of each subsection.

    Here is a sample JSON response:
    {format_sample}
    """
    USER_MESSAGE: str = """
    News Content: "{news_content}"
    ---
    Provide a summary for the provided news text. The text is from the following tv show: {news_show_details}
    """


class LlmInteractor:
    def __init__(
        self,
        azure_open_ai_base_url,
        azure_open_ai_api_version,
        azure_open_ai_deployment_name,
    ) -> None:
        # Create llm chain
        self.__create_llm_chain(
            azure_open_ai_base_url=azure_open_ai_base_url,
            azure_open_ai_api_version=azure_open_ai_api_version,
            azure_open_ai_deployment_name=azure_open_ai_deployment_name,
        )

    def __create_llm_chain(
        self,
        azure_open_ai_base_url,
        azure_open_ai_api_version,
        azure_open_ai_deployment_name,
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
            # "format_instructions",
            "format_sample",
            "news_content",
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
        )

        # Create the output parser
        logging.debug("Creating the output parser")
        output_parser = JsonOutputParser(pydantic_object=InvokeLlmResponse)

        # Insert partial into prompt
        item1 = LlmResponseItem(
            title="Title of the first subsection",
            tags=["tag-1", "tag-2", "tag-3"],
            score=9,
            start="Start of the first subsection",
            end="End of the first subsection",
        )
        item2 = LlmResponseItem(
            title="Title of the second subsection",
            tags=["tag-1", "tag-2", "tag-3"],
            score=7,
            start="Start of the second subsection",
            end="End of the second subsection",
        )
        item3 = LlmResponseItem(
            title="Title of the third subsection",
            tags=["tag-1", "tag-2", "tag-3"],
            score=8,
            start="Start of the third subsection",
            end="End of the third subsection",
        )
        format_sample = InvokeLlmResponse(root=[item1, item2, item3])
        prompt_partial = prompt.partial(
            # format_instructions=output_parser.get_format_instructions(),
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
    ) -> InvokeLlmResponse:
        result: InvokeLlmResponse = self.__llm_chain.invoke(
            {"news_content": news_content, "news_show_details": news_show_details}
        )
        return result
