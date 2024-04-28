import string
from typing import List

from models.newstagextraction import LlmResponseItem


def remove_punctuation(text: str) -> str:
    return text.translate(str.maketrans("", "", f"{string.punctuation}¿¡"))


def cleanse_text(text: str) -> List[str]:
    # Remove punctuation
    text_cleansed = remove_punctuation(text)

    # Create word list
    word_list = text_cleansed.split(" ")

    return word_list


def get_cleansed_llm_response_item(
    list: List[LlmResponseItem], index: int, start: bool
) -> List[str]:
    # Get current item
    item = list[index]

    # Get text
    text = item.get_item_text(start=start)

    # Remove punctuation
    text_cleansed = remove_punctuation(text=text)

    # Create word list
    word_list = text_cleansed.split(" ")

    return word_list
