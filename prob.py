"""Find place, date, type of event etc of messages."""
import json
import os
import re
import time

import openai
import pandas as pd
from dotenv import load_dotenv
from openai.error import RateLimitError

load_dotenv()
openai.api_key = os.getenv("OPENAI_KEY")

MESSAGES_PATH = "messages.json"
OUTPUT_PATH = "events.csv"
RANGE = (999, 999)
BATCH_SIZE = 3

EVENTS = [
    "лекція",
    "концерт",
    "фестиваль",
    "вечірка",
    "вистава",
    "виставка",
    "кіно",
    "арттерапія",
    "літвечір",
    "стендап",
    "квест",
    "дебати",
    "конференція",
    "тренінг",
    "майстер-клас",
    "гра",
    "презентація",
]
KEYS = ["name", "type", "date", "time", "place", "price"]

SYSTEM_PROMPT = f"""You have to analize a few texts about events, \
separated by "==Text=="
Write the values for these in separate lines, in the following order:
назва: The name of the event
тип: The type of an event. The type should be one of {EVENTS}. \
If the type is not close to these, write "-" as the whole line. \
Otherwise write the most close type of the list.
дата: The date should be printed in a format YYYY/MM/DD\
(separated by hyphen, if range). \
Convert to this format if needed(the default format often is DD.MM). \
If the date is not known, write "-" as the whole line.
час: The time in a format HH:MM-HH:MM. If the end time is not known, \
write just "HH:MM-...". If the start time is not known, write "...-HH:MM". \
If the time is not known, write "-" as the whole line and nothing more.
місце: The place, printed in a way nice for automated finding on a map. \
If the place is not known, write "-" as the whole line.
ціна: The price in a format "100 грн" or "100-200 грн". \
If in any way it is mentioned that you don't have to pay or you can enter freely \
or there is nothing mentioned about price - print "0 грн". \
If there is something about донат - print just "донат"

If a text is not about events or there is more than one event mentioned, \
write "NOT_EVENT" instead of the values.
Separate the sections of values for each text with a line "==Text==".
If there are different subevents in different times, \
print just the time of the whole event.
You should print in the format "key: value" for each line.
If you don't know the value, print a hyphen(-) in the line and nothing more.
Don't print anything else in the lines, no additional information.
"""


def get_response(text: str) -> str:
    """Get response from OpenAI.

    If rate limit error, wait half a minute and try again.
    After 4 fails, raise an error.

    Args:
        text (str): text to analize

    Returns:
        str: response from OpenAI

    Raises:
        RateLimitError: if too many tries already
    """
    tries = 0
    response = None
    while not response and tries < 4:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": text},
                ],
            )
        except RateLimitError:
            print("Rate limit error, waiting 30 seconds")
            time.sleep(30)
            tries += 1

    if not response:
        raise RateLimitError("Too many tries already")

    return response["choices"][0]["message"]["content"]


def clear_line(line: str) -> str:
    """Clear line from extra information.

    Sometimes OpenAI adds extra information like "Тип: " or "Дата: ".

    Args:
        line (str): line to clear

    Returns:
        str: cleared line
    """
    return (
        line.replace("Назва: ", "")
        .replace("Тип: ", "")
        .replace("Дата: ", "")
        .replace("Час: ", "")
        .replace("Місце: ", "")
        .replace("Ціна: ", "")
        .replace("назва: ", "")
        .replace("тип: ", "")
        .replace("дата: ", "")
        .replace("час: ", "")
        .replace("місце: ", "")
        .replace("ціна: ", "")
    )


def parse_response(response: str) -> dict:
    """Parse response from OpenAI.

    Args:
        response (dict): response from OpenAI

    Returns:
        dict: dictionary with date and type of event
    """
    response_lines = response.split("\n")
    response_lines = [clear_line(line) for line in response_lines if line != ""]
    response_dict: dict = {}
    print(response_lines)

    for i, key in enumerate(KEYS):
        if i >= len(response_lines):
            return response_dict

        if response_lines[i].strip().endswith("-"):
            response_dict[key] = None

        if key == "price":
            if "донат" in response_lines[i] or "будь-як" in response_lines[i]:
                response_dict[key] = "донат"
                continue

            if (
                "віль" in response_lines[i]
                or "безкошт" in response_lines[i]
                or "відкр" in response_lines[i]
            ):
                response_dict[key] = "0 грн"
                continue

        if key == "time":
            response_dict[key] = (
                response_lines[i]
                .replace("HH:MM", "")
                .replace("відкритий захід", "")
                .replace("...", "")
                .strip()
            )
            continue

        # Using regex change "YYYY-MM-DD" to "YYYY/MM/DD"
        if key == "date":
            response_dict[key] = re.sub(
                r"(\d{4})-(\d{2})-(\d{2})", r"\1/\2/\3", response_lines[i]
            ).strip()

        response_dict[key] = response_lines[i].strip()

    return response_dict


def get_information_from_texts(texts: list[str]) -> list[dict]:
    """Get information for each text.

    Args:
        texts (list[str]): list of texts to analize

    Returns:
        list[dict]: list of dictionaries with information for each text
    """
    text_to_ai = "\n\n==Text==\n".join(texts)
    print("Sending to AI")
    response = get_response(text_to_ai)
    print(response)
    print()
    print()
    return [
        parse_response(response)
        if "NOT_EVENT" not in response and "HOT_EVENT" not in response
        else {"name": "NOT_EVENT"}
        for response in response.replace("==Text==", "==")
        .replace("\n\n", "==")
        .split("==")
        if response.strip() != ""
    ]


with open(MESSAGES_PATH, "r") as f:
    messages = json.load(f)

data = []

# Parse messages in batches of BATCH_SIZE
for i in range(RANGE[0], RANGE[1], BATCH_SIZE):
    print(f"Batch {i}: {i + BATCH_SIZE}")
    batch = [
        message
        for message in messages[i : min(i + BATCH_SIZE, len(messages))]
        if message["text"] is not None
    ]
    texts = [f"{message['date'][:4]} рік.\n" + message["text"] for message in batch]
    response_dicts = get_information_from_texts(texts)
    print(response_dicts)
    for j in range(min(len(response_dicts), len(batch))):
        response_dict = response_dicts[j]
        if response_dict["name"] == "NOT_EVENT":
            continue

        response_dict["send_date"] = batch[j]["date"]
        response_dict["views"] = batch[j]["views"]
        data.append(response_dict)

    time.sleep(1)

data = [event for event in data if event["name"] != "NOT_EVENT"]

if not os.path.isfile(OUTPUT_PATH):
    merged_df = pd.DataFrame(data)
else:
    # Take existing csv file and create pd.DataFrame from it
    old_df = pd.read_csv(OUTPUT_PATH)

    # Create new DataFrame with new data
    new_df = pd.DataFrame(data)

    # Merge old and new DataFrames
    merged_df = pd.concat([old_df, new_df], ignore_index=True)

    # Drop duplicates
    merged_df = merged_df.drop_duplicates()


# If in a row name there is a word from EVENTS(in any case),
# make the value of type column equal to this word(in lower case)
if merged_df is not None:
    for event in EVENTS:
        merged_df.loc[
            merged_df["name"].str.contains(event, case=False), "type"
        ] = event.lower()

    merged_df.to_csv(OUTPUT_PATH, index=False)
