import json
import os
import tempfile

import boto3
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.models.events import Event
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from llama_index.core import PromptTemplate, StorageContext, load_index_from_storage
from llama_index.core.indices.base import BaseIndex

from openai import OpenAI

# LINE Bot SDK Documents
# https://line-bot-sdk-python.readthedocs.io/en/stable/
# https://github.com/line/line-bot-sdk-python/tree/master

# OpenAI Python
# https://github.com/openai/openai-python

# Llama Index
# https://docs.llamaindex.ai/en/latest/getting_started/starter_example.html

JSON_FILES = [
    "default__vector_store.json",
    "docstore.json",
    "graph_store.json",
    "image__vector_store.json",
    "index_store.json",
]


def get_secrets() -> dict[str, str]:
    client = boto3.client("secretsmanager")
    secretARN = os.environ["SECRET_ARN"]
    secrets = client.get_secret_value(SecretId=secretARN)
    decoded = json.loads(secrets["SecretString"])
    return decoded


def load_index() -> BaseIndex:
    vector_bucket = os.environ["VECTOR_BUCKET"]
    with tempfile.TemporaryDirectory() as tmp_dir:
        persist_dir = os.path.join(tmp_dir, "storage")
        os.makedirs(persist_dir)
        download_vector(vector_bucket, persist_dir)
        storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
        index = load_index_from_storage(storage_context)
        return index


def download_vector(bucket: str, persist_dir: str) -> None:
    client = boto3.client("s3")
    for json_file in JSON_FILES:
        resp = client.get_object(Bucket=bucket, Key=json_file)
        with open(os.path.join(persist_dir, json_file), "wb") as f:
            f.write(resp["Body"].read())


secrets = get_secrets()
os.environ["OPENAI_API_KEY"] = secrets["openai-api-key"]
line_config = Configuration(access_token=secrets["channel-access-token"])
webhook_handler = WebhookHandler(channel_secret=secrets["channel-secret"])
vector_index = load_index()


def lambda_handler(event, context) -> dict:

    @webhook_handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event: Event):
        user_message = event.message.text
        answer = generate_response(user_message)
        with ApiClient(line_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_msg_req = ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=answer)],
            )
            line_bot_api.reply_message_with_http_info(reply_msg_req)

    print(f"{event=}")
    print(f"{context=}")
    body = event["body"]
    signature = event["headers"]["x-line-signature"]
    # print(f"{body=}")  # debug
    # print(f"{signature=}")  # debug
    webhook_handler.handle(body, signature)

    return {"statusCode": 200, "body": json.dumps({"message": "ok"})}


openai_client = OpenAI(api_key=secrets["openai-api-key"])

COMMON_PROMPT = """
あなたは親切なアシスタントである。
以下が文献の情報である。

---------------------
{context_str}
---------------------

この情報を参照し、以下の質問に回答せよ。: {query_str}
"""


def generate_response(user_message: str) -> str:
    query_engine = vector_index.as_query_engine()
    default_answer = query_engine.query(user_message)
    print(f"{default_answer=}")
    custom_query_engine = vector_index.as_query_engine(
        text_qa_template=PromptTemplate(COMMON_PROMPT)
    )
    return str(custom_query_engine.query(user_message))
