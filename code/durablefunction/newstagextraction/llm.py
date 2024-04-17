import logging
import os

from azure.identity import DefaultAzureCredential
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from shared.config import settings


class LlmMessages:
    SYSTEM_MESSAGE: str = """
    You are a world class assistent for summarizing news content.
    You extract subsections from the provided news content and generate a title for each subsection.
    For each subsection you provide a score indicating how good the defined tags match the content of the subsection. 0 indicates that the tags don't match the content, and 1 means that the tags are a perfect match.
    You must include the start and end of the original text for each subsection in the response. The text snippet describing the beginning and end should include 5 words.
    You add tags to each subsection. Samples for tags are: sports, weather, international news, national news, politics, technology, celebrity, other. You add additional tags based on the content of each subsection.

    You always respond with the following JSON structure:
    [
        {
            "title": "<title of the first subsection>",
            "tags": "<tags of the first subsection>",
            "score": "<score of the first subsection>",
            "start": "<start of the text of the first subsection from the original text>",
            "end": "<end of the text of the first subsection from the original text>"
        },
        {
            "title": "<title of the second subsection>",
            "tags": "<tags of the second subsection>",
            "score": "<score of the second subsection>",
            "start": "<start of the text of the second subsection from the original text>",
            "end": "<end of the text of the second subsection from the original text>"
        },
        {
            "title": "<title of the third subsection>",
            "tags": "<tags of the third subsection>",
            "score": "<score of the third subsection>",
            "start": "<start of the text of the third subsection from the original text>",
            "end": "<end of the text of the third subsection from the original text>"
        }
    ]
    """
    USER_MESSAGE: str = """
    News Content: "{news_content}"
    ---
    Provide a summary for the provided news text. The text is about {news_show_details}
    """


class LlmInteractor:
    def __init__(
        self,
    ) -> None:
        # Create llm chain
        self.llm_chain = self._create_llm_chain()

    def _create_llm_chain(
        self,
    ):
        # Create chat prompt template
        logging.debug("Creating chat prompt template")
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=LlmMessages.SYSTEM_MESSAGE, type="system"),
                ("user", LlmMessages.USER_MESSAGE),
            ]
        )
        prompt.input_variables = ["news_content", "news_show_details"]

        # Create the llm
        logging.debug("Creating the llm")
        os.environ["OPENAI_API_TYPE"] = "azure_ad"
        llm = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_OPEN_AI_BASE_URL,
            api_version=settings.AZURE_OPEN_AI_API_VERSION,
            deployment_name=settings.AZURE_OPEN_AI_DEPLOYMENT_NAME,
        )

        # Create the output parser
        logging.debug("Creating the output parser")
        output_parser = JsonOutputParser()

        # Create chain
        logging.debug("Creating the llm chain")
        chain = prompt | llm | output_parser
        return chain

    def invoke_llm_chain(
        self,
        news_content: str,
        news_show_details: str,
    ):
        # Generate token for azure open ai and set as environment variable
        credential = DefaultAzureCredential()
        token = credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        ).token
        os.environ["OPENAI_API_KEY"] = token

        result = self.llm_chain.invoke(
            {"news_content": news_content, "news_show_details": news_show_details}
        )
        return result
