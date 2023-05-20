# Underground events processor
A script to process telegram messages about some events and process them, using ChatGPT, to get information about date, type of event, its name etc

Then store everything in a `csv` file

## Usage
1. Get all the messages in a format of

```json
[
    {
        "id": 0,
        "text": "message text",
        "date": "2021-01-01 00:00:00+00:00",
        "views": 0
    }
]
```

You can do this using something like `telethon` library

2. Get an API key for openai and put in in `.env`
3. In `prob.py` change `MESSAGES_PATH`, `OUTPUT_PATH` and `RANGE` to your needs

`MESSAGES_PATH` is a path to the file with messages in json format

`OUTPUT_PATH` is a path to the file where you want to store the results

`RANGE` is a range of messages you want to process. It does not look for ids, but for indexes in the list of messages

It is recommended to process messages in batches of 50-100 messages, because ChatGPT sometimes hallucinates and gives some weird results. It allows to check every `n` messages, whether there are any anomalities and fix

AI's errors also cause sometimes the script to crash - it is another reason to process messages in batches

4. Run `prob.py` and wait for the results

If you are doing in batches, as recommended, no special actions are required. The previous results are saved and the new ones are appended to the file

## How it works
### Modules
`json` - to read json file of messages
`os` and `dotenv` - to get the API key from `.env` file
`openai` - to use ChatGPT
`pandas` - to store the results in a csv file
`re` - to process some of the ChatGPT's results
`time` - to wait when rate limit is exceeded

### Algorithm
1. Tweak some consts, if needed:
    - `EVENTS` - a list of events that will be used to find the event type by ChatGPT(1)
    - `KEYS` - a list of keys that will be in the final csv file
    - `SYSTEM_PROMPT` - a prompt that tells ChatGPT how to output
    - `BATCH_SIZE` - a number of messages to process at once

Messages are sent in batches to avoid too many requests and rate limit errors

(1): sometimes CharGPT gives some additional events, not present in the list, and it is hard to make him only use the keys provided. However, usually it sticks to the rules
Note: if you want more keys(columns), you should change the `KEYS` and change the prompt(`SYSTEM_PROMPT`)

2. `get_response` function
    - takes a text
    - sends a request to ChatGPT
    - returns the response
    - if the rate limit is exceeded, it waits for 30 seconds and tries again
    - if the error of rate limit is still present after 3 retries, it raises an exception

3. `clear_line` function
    - takes a line from ChatGPT's response
    - removes the keys from the line(for example "Тип: концерт" -> "концерт")

4. `parse_response` function
    - takes a response from ChatGPT
    - splits it by lines
    - removes the keys from the lines
    - fixes some common ChatGPT's errors
    - returns a dictionary of keys and values(like {"name": "foo", "type": "bar"})

5. `get_information_from_texts` function
    - takes a list of texts that need to be sent to ChatGPT
    - sends them all, separated by "\n\n==Text==\n" to ChatGPT
    - gets the response
    - parses it for every text
    - returns a list of dictionaries of keys and values(like [{"name": "foo", "type": "bar"}, {"name": "foo", "type": "bar"}])

The texts are sent together to ChatGPT to save the number of requests and avoid too many rate limit errors

The free plan of openai allows to send only 3 requests per minute

6. Get messages from `json` file

7. Parse messages in `BATCH_SIZE` batches
    - get the texts from messages
    - combine them into one text, also provide the year, when it was sent. It is done in order for AI to know, what date to provide in "YYYY/MM/DD" format, because the dates of events usually don't include the year
    - get the parsed responses
    - save the results to a `data` list

8. If there is no file with results, create a new one with the output
9. If there is already a file with results, read it and append the new results to it
