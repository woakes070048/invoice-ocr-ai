
from langchain_openai import ChatOpenAI
from .prompts import HEADER_PROMPT, ITEMS_PROMPT, TAX_PROMPT
from .confidence import calculate_confidence

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

def extract_header(state):
    response = llm.invoke(
        HEADER_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )
    state["header"] = response.content
    return state

def extract_items(state):
    response = llm.invoke(
        ITEMS_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )
    state["items"] = response.content
    return state

def extract_taxes(state):
    response = llm.invoke(
        TAX_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )
    state["taxes"] = response.content
    return state

def score_confidence(state):
    state["confidence"] = calculate_confidence(state)
    return state
